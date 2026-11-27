"""Huấn luyện ứng viên E1 (TF-IDF + Logistic Regression) và ghi artifact schemaVersion 2.

Chạy ngoài image runtime (TL05 §1–3, TL06 §3–4). Trainer kiểm dữ liệu trước khi huấn luyện
và từ chối khi sai. Chỉ fit trên `train`, chọn siêu tham số trên `validation`. `test` và
`challenge` chỉ được đọc để kiểm rò rỉ nhóm, không dùng để fit hay chọn mô hình.

Lượt này chỉ có Logistic Regression và không hiệu chuẩn. Provider cần `predict_proba`, nên
LinearSVC và hiệu chuẩn thuộc PR-3. Artifact không có khóa `calibration`, nên điểm luôn là `null`.

Chạy từ gốc repo:
    python -m training.classifier.train --dataset <thư mục dữ liệu> --out <thư mục artifact>
Thêm `--status candidate --category-threshold <τ>` khi đã có phê duyệt AI-06 và giá trị AI-07.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

from supportflow_ai.adapters.classifiers.ml.artifact import MANIFEST_NAME, SCHEMA_VERSION
from supportflow_ai.adapters.classifiers.ml.contract_pin import CONTRACT_SHA256
from supportflow_ai.adapters.classifiers.ml.provider import MODEL_FILE
from supportflow_ai.adapters.classifiers.ml.text import PREPROCESSING_VERSION, model_input
from supportflow_ai.domain.classification import Category

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_MANIFEST = "MANIFEST.json"
SPLITS = frozenset({"train", "validation", "calibration", "test", "challenge"})
STATUSES = frozenset({"dev-stub", "candidate"})
# Dữ liệu dịch hoặc tổng hợp chỉ được vào train (TL04 §1–2, ml-classifier-plan.md mục 6.1).
TRAIN_ONLY_SOURCES = frozenset({"synthetic", "public_translated"})
GOVERNANCE_FIELDS = (
    "version", "guidelineVersion", "source", "licenseOrApproval",
    "owner", "access", "retention", "deidentification",
)
TAXONOMY = frozenset(item.value for item in Category)
SEVERITY_VALUES = frozenset({"Low", "Medium", "High"})
SEALED = "CHƯA ĐO"
DEFAULT_SEED = 20261120
# Ngưỡng tạm cho dev-stub: 0.0 nghĩa là không bỏ gợi ý. Ngưỡng thật do AI-07 quyết (PR-3).
DEV_STUB_THRESHOLD = 0.0
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")  # cùng quy tắc với artifact.py
# Lưới siêu tham số chọn trên validation. Thứ tự cố định để kết quả tái lập.
_GRID = tuple(
    (word, char, c, weight)
    for word in ((1, 1), (1, 2))
    for char in ((2, 4), (1, 3))
    for c in (0.5, 2.0, 8.0)
    for weight in (None, "balanced")
)


class TrainingError(ValueError):
    """Dữ liệu hoặc tham số không đạt kiểm tra. Mã lỗi không chứa nội dung phiếu."""


def train_classifier(
    dataset_dir: Path,
    out_dir: Path,
    *,
    source_sha: str,
    seed: int = DEFAULT_SEED,
    status: str = "dev-stub",
    name: str = "tfidf-lr",
    artifact_version: str = "dev-0",
    category_threshold: float | None = None,
) -> dict[str, Any]:
    """Kiểm dữ liệu, huấn luyện, ghi `model.joblib` và `manifest.json`. Trả về manifest đã ghi."""
    if status not in STATUSES:
        raise TrainingError("status_invalid")
    if not _GIT_SHA.fullmatch(source_sha):
        raise TrainingError("source_sha_invalid")
    if not _IDENTIFIER.fullmatch(name) or not _IDENTIFIER.fullmatch(artifact_version):
        raise TrainingError("artifact_identity_invalid")
    candidate = status == "candidate"
    dataset_manifest, manifest_bytes = _read_dataset_manifest(dataset_dir)
    _check_governance(dataset_manifest, candidate=candidate)
    rows = _load_rows(dataset_dir, dataset_manifest)
    _check_rows(rows)
    _check_coverage(rows)
    threshold = _threshold(category_threshold, candidate=candidate)

    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    pipeline, validation_score = _select(train_rows, validation_rows, seed)
    model_bytes = _dump(pipeline)
    summary = f"{status}: validation macro-F1 {validation_score:.3f}, n={len(validation_rows)}"
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "name": name,
        "version": artifact_version,
        "status": status,
        "preprocessingVersion": PREPROCESSING_VERSION,
        "sourceSha": source_sha,
        "classificationContractSha256": CONTRACT_SHA256,
        "environment": {
            "python": platform.python_version(),
            "sklearn": version("scikit-learn"),
            "numpy": version("numpy"),
            "joblib": version("joblib"),
        },
        "dataset": {
            "version": dataset_manifest["version"],
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        },
        "splitSha256": _split_sha256(rows),
        "guidelineVersion": dataset_manifest["guidelineVersion"],
        "model": {"family": "tfidf-logreg", "revision": "n/a", "seed": seed},
        "thresholds": {"category": threshold},
        "files": {MODEL_FILE: hashlib.sha256(model_bytes).hexdigest()},
        "evaluation": {"development": summary, "sealed": SEALED},
    }
    _write(out_dir, model_bytes, manifest)
    return manifest


def _read_dataset_manifest(dataset_dir: Path) -> tuple[dict[str, Any], bytes]:
    path = dataset_dir / DATASET_MANIFEST
    if not path.is_file():
        raise TrainingError("dataset_manifest_missing")
    data = path.read_bytes()
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingError("dataset_manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise TrainingError("dataset_manifest_invalid")
    return manifest, data


def _check_governance(manifest: dict[str, Any], *, candidate: bool) -> None:
    for field in GOVERNANCE_FIELDS:
        if not _is_text(manifest.get(field)):
            raise TrainingError(f"dataset_governance_missing:{field}")
    # artifact.py giới hạn 128 ký tự cho hai trường này; vượt quá thì artifact sẽ không nạp được.
    if any(len(manifest[field]) > 128 for field in ("version", "guidelineVersion")):
        raise TrainingError("dataset_governance_too_long")
    if candidate and not _is_text(manifest.get("approvalAI06")):
        raise TrainingError("candidate_requires_ai06_approval")


def _load_rows(dataset_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise TrainingError("dataset_files_invalid")
    for path in dataset_dir.glob("*.jsonl"):
        if path.name not in files:
            raise TrainingError("dataset_unlisted_file")
    rows: list[dict[str, Any]] = []
    for name in sorted(files):
        info = files[name]
        if (
            PurePosixPath(name).name != name
            or not name.endswith(".jsonl")
            or not isinstance(info, dict)
            or not isinstance(info.get("sha256"), str)
        ):
            raise TrainingError("dataset_files_invalid")
        path = dataset_dir / name
        if not path.is_file():
            raise TrainingError("dataset_file_missing")
        # Băm và phân tích cùng một lần đọc, không đọc lại sau khi băm (như artifact.py).
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise TrainingError("dataset_sha_mismatch")
        file_rows = _parse_jsonl(data, name)
        if "samples" in info and info["samples"] != len(file_rows):
            raise TrainingError("dataset_sample_count_mismatch")
        rows.extend(file_rows)
    return rows


def _parse_jsonl(data: bytes, name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise TrainingError(f"dataset_encoding_invalid:{name}") from exc
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TrainingError(f"row_json_invalid:{name}:{number}") from exc
        if not isinstance(row, dict):
            raise TrainingError(f"row_json_invalid:{name}:{number}")
        rows.append(row)
    return rows


def _check_rows(rows: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        row_id, split, group = row.get("id"), row.get("split"), row.get("split_group_id")
        category, source = row.get("category"), row.get("source", "")
        if not _is_text(row_id) or row_id in seen_ids:
            raise TrainingError("row_id_invalid")
        seen_ids.add(row_id)
        if not _is_text(split) or split not in SPLITS:
            raise TrainingError("row_split_invalid")
        if not _is_text(group):
            raise TrainingError("row_group_missing")
        groups[group].add(split)
        if not isinstance(row.get("title"), str) or not isinstance(row.get("description"), str):
            raise TrainingError("row_text_invalid")
        if not _is_text(category) or category not in TAXONOMY:
            raise TrainingError("row_category_invalid")
        for field in ("impact", "urgency"):
            value = row.get(field)
            if value is not None and (not isinstance(value, str) or value not in SEVERITY_VALUES):
                raise TrainingError("row_severity_invalid")
        if not isinstance(source, str):
            raise TrainingError("row_source_invalid")
        if source in TRAIN_ONLY_SOURCES and split != "train":
            raise TrainingError("train_only_source_outside_train")
    if any(len(splits) > 1 for splits in groups.values()):
        raise TrainingError("split_group_leak")


def _check_coverage(rows: list[dict[str, Any]]) -> None:
    # Dữ liệu tổng hợp chỉ ở train nên validation luôn có dữ liệu không tổng hợp. Vì vậy "candidate
    # chỉ có tổng hợp" không cần nhánh riêng: không thể đạt tới đây.
    splits = {row["split"] for row in rows}
    if not {"train", "validation"} <= splits:
        raise TrainingError("split_missing")
    train_categories = {row["category"] for row in rows if row["split"] == "train"}
    if len(train_categories) < 2:
        raise TrainingError("train_classes_insufficient")


def _threshold(value: float | None, *, candidate: bool) -> float:
    if value is None:
        if candidate:
            raise TrainingError("candidate_requires_threshold")
        return DEV_STUB_THRESHOLD
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise TrainingError("threshold_invalid")
    return float(value)


def _select(
    train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]], seed: int,
) -> tuple[Pipeline, float]:
    """Chọn cấu hình có macro-F1 cao nhất trên validation. Hòa thì lấy cấu hình đứng trước."""
    best_pipeline: Pipeline | None = None
    best_score = -1.0
    for word_range, char_range, c, weight in _GRID:
        pipeline = _fit(train_rows, word_range, char_range, c, weight, seed)
        score = _macro_f1(pipeline, validation_rows)
        if best_pipeline is None or score > best_score:
            best_pipeline, best_score = pipeline, score
    return best_pipeline, best_score  # type: ignore[return-value]


def _fit(
    train_rows: list[dict[str, Any]],
    word_range: tuple[int, int],
    char_range: tuple[int, int],
    c: float,
    weight: str | None,
    seed: int,
) -> Pipeline:
    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=word_range)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=char_range)),
    ])
    classifier = LogisticRegression(C=c, class_weight=weight, max_iter=2000, random_state=seed)
    pipeline = Pipeline([("features", features), ("clf", classifier)])
    pipeline.fit(_texts(train_rows), [row["category"] for row in train_rows])
    return pipeline


def _macro_f1(pipeline: Pipeline, rows: list[dict[str, Any]]) -> float:
    predicted = pipeline.predict(_texts(rows))
    truth = [row["category"] for row in rows]
    return float(f1_score(truth, predicted, average="macro", zero_division=0))


def _texts(rows: list[dict[str, Any]]) -> list[str]:
    # Cùng hàm với provider ml khi suy luận: đây là đầu vào duy nhất của mô hình.
    return [model_input(row["title"], row["description"]) for row in rows]


def _split_sha256(rows: list[dict[str, Any]]) -> str:
    table = {row["split_group_id"]: row["split"] for row in rows}
    canonical = json.dumps(sorted(table.items()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dump(pipeline: Pipeline) -> bytes:
    buffer = io.BytesIO()
    joblib.dump(pipeline, buffer)
    return buffer.getvalue()


def _write(out_dir: Path, model_bytes: bytes, manifest: dict[str, Any]) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise TrainingError("output_dir_not_empty")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MODEL_FILE).write_bytes(model_bytes)
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (out_dir / MANIFEST_NAME).write_text(text, encoding="utf-8")


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _git_state(repo_root: Path) -> tuple[str, bool]:
    """SHA HEAD và cờ có thay đổi chưa commit. Lỗi git thì từ chối, không đoán SHA."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TrainingError("git_state_unavailable") from exc
    return head, bool(status.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Huấn luyện ứng viên E1 (TF-IDF + LR).")
    parser.add_argument("--dataset", required=True, type=Path, help="Thư mục có MANIFEST.json")
    parser.add_argument("--out", required=True, type=Path, help="Thư mục artifact (phải trống)")
    parser.add_argument("--status", choices=sorted(STATUSES), default="dev-stub")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--artifact-version", default="dev-0")
    parser.add_argument(
        "--category-threshold", type=float, default=None,
        help="Ngưỡng Category theo AI-07. Bắt buộc khi --status candidate.",
    )
    args = parser.parse_args(argv)
    try:
        head, dirty = _git_state(REPO_ROOT)
        if dirty:
            if args.status == "candidate":
                raise TrainingError("candidate_requires_clean_tree")
            print("warning: working tree has uncommitted changes; sourceSha does not cover them",
                  file=sys.stderr)
        manifest = train_classifier(
            args.dataset, args.out, source_sha=head, seed=args.seed, status=args.status,
            artifact_version=args.artifact_version, category_threshold=args.category_threshold,
        )
    except TrainingError as exc:
        print(f"training rejected: {exc}", file=sys.stderr)
        return 2
    print(f"status={manifest['status']} version={manifest['version']} "
          f"sourceSha={manifest['sourceSha']} {manifest['evaluation']['development']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
