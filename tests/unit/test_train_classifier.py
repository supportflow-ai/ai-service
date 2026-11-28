"""Trainer E1: kiểm dữ liệu trước khi huấn luyện; artifact schemaVersion 2 do provider nạp được."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest

from supportflow_ai.adapters.classifiers.ml.artifact import MANIFEST_NAME
from supportflow_ai.adapters.classifiers.ml.provider import MODEL_FILE, MlClassifier
from supportflow_ai.domain.classification import SuggestionField
from training.classifier.train import TrainingError, train_classifier

SHA = "a" * 40
GOVERNANCE = {
    "version": "v1-test",
    "guidelineVersion": "CAT-2026-01",
    "source": "tình huống nhóm tự viết, revision test",
    "licenseOrApproval": "nội bộ, do người viết cung cấp",
    "owner": "nhóm AI",
    "access": "nhóm AI",
    "retention": "xóa sau 1 năm",
    "deidentification": "không có dữ liệu thật",
}
TRAIN = [
    ("vpn không kết nối được", "VPN"),
    ("cisco anyconnect bị lỗi", "VPN"),
    ("không vào được vpn công ty", "VPN"),
    ("máy in bị kẹt giấy", "PRINT"),
    ("máy in không in được", "PRINT"),
    ("máy in báo hết mực", "PRINT"),
    ("quên mật khẩu đăng nhập", "ACC"),
    ("tài khoản bị khóa", "ACC"),
    ("không đăng nhập được tài khoản", "ACC"),
]
VALIDATION = [
    ("vpn bị ngắt liên tục", "VPN"),
    ("máy in kẹt giấy khay 2", "PRINT"),
    ("quên mật khẩu email", "ACC"),
]


def _rows(pairs, split: str, prefix: str, source: str = "") -> list[dict]:
    return [
        {
            "id": f"{prefix}-{index}", "title": title, "description": "", "category": category,
            "split": split, "split_group_id": f"{prefix}-g{index}", "source": source,
        }
        for index, (title, category) in enumerate(pairs)
    ]


def make_dataset(root: Path, files: dict[str, list[dict]], **overrides) -> Path:
    """Ghi JSONL và MANIFEST.json. Giá trị `None` trong `overrides` nghĩa là bỏ khóa đó."""
    root.mkdir(parents=True, exist_ok=True)
    listing = {}
    for name, rows in files.items():
        data = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
        (root / name).write_bytes(data)
        listing[name] = {"sha256": hashlib.sha256(data).hexdigest(), "samples": len(rows)}
    manifest = {**GOVERNANCE, "files": listing, **overrides}
    manifest = {key: value for key, value in manifest.items() if value is not None}
    (root / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return root


def standard_dataset(root: Path, **overrides) -> Path:
    files = {
        "train.jsonl": _rows(TRAIN, "train", "t"),
        "dev.jsonl": _rows(VALIDATION, "validation", "v"),
    }
    return make_dataset(root, files, **overrides)


def _train(dataset: Path, out: Path, **kwargs) -> dict:
    return train_classifier(dataset, out, source_sha=SHA, **kwargs)


def _provider(model_dir: Path, *, allow_dev_stub: bool) -> MlClassifier:
    return MlClassifier(
        model_dir=str(model_dir), allow_dev_stub=allow_dev_stub,
        max_concurrency=1, max_queue=0, queue_timeout_s=1.0,
    )


async def test_dev_stub_artifact_loads_in_ml_provider(tmp_path):
    out = tmp_path / "model"
    _train(standard_dataset(tmp_path / "data"), out)

    classifier = _provider(out, allow_dev_stub=True)
    try:
        assert classifier.ready
        prediction = await classifier.classify(title="vpn không kết nối được", description="")
    finally:
        classifier.close()
    category = prediction.suggestions[0]
    assert category.field is SuggestionField.CATEGORY
    assert category.value == "VPN"
    assert category.score is None  # dev-stub không phát điểm


def test_manifest_is_schema_v2_and_sealed(tmp_path):
    out = tmp_path / "model"
    dataset = standard_dataset(tmp_path / "data")
    manifest = _train(dataset, out)

    on_disk = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert manifest["schemaVersion"] == 2
    assert manifest["status"] == "dev-stub"
    assert "calibration" not in manifest  # chưa hiệu chuẩn, điểm vẫn null
    assert manifest["evaluation"]["sealed"] == "CHƯA ĐO"
    assert manifest["sourceSha"] == SHA
    model_sha = hashlib.sha256((out / MODEL_FILE).read_bytes()).hexdigest()
    assert manifest["files"] == {MODEL_FILE: model_sha}
    manifest_bytes = (dataset / "MANIFEST.json").read_bytes()
    assert manifest["dataset"]["sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    assert len(manifest["splitSha256"]) == 64


def test_same_seed_gives_same_probabilities(tmp_path):
    dataset = standard_dataset(tmp_path / "data")
    _train(dataset, tmp_path / "first", seed=7)
    _train(dataset, tmp_path / "second", seed=7)

    first = joblib.load(tmp_path / "first" / MODEL_FILE)
    second = joblib.load(tmp_path / "second" / MODEL_FILE)
    probes = ["máy in bị kẹt", "không vào được mạng", "quên mật khẩu"]
    np.testing.assert_allclose(first.predict_proba(probes), second.predict_proba(probes))


def test_rejects_group_leak_between_splits(tmp_path):
    validation = _rows(VALIDATION, "validation", "v")
    validation[0]["split_group_id"] = "t-g0"  # cùng nhóm với một mẫu train
    dataset = make_dataset(tmp_path / "data", {
        "train.jsonl": _rows(TRAIN, "train", "t"), "dev.jsonl": validation,
    })
    with pytest.raises(TrainingError, match="split_group_leak"):
        _train(dataset, tmp_path / "model")


def test_rejects_synthetic_row_outside_train(tmp_path):
    validation = _rows(VALIDATION, "validation", "v", source="synthetic")
    dataset = make_dataset(tmp_path / "data", {
        "train.jsonl": _rows(TRAIN, "train", "t"), "dev.jsonl": validation,
    })
    with pytest.raises(TrainingError, match="train_only_source_outside_train"):
        _train(dataset, tmp_path / "model")


def test_rejects_file_changed_after_manifest(tmp_path):
    dataset = standard_dataset(tmp_path / "data")
    with (dataset / "train.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_rows([("thêm dòng", "NET")], "train", "x")[0]) + "\n")
    with pytest.raises(TrainingError, match="dataset_sha_mismatch"):
        _train(dataset, tmp_path / "model")


def test_rejects_missing_governance_field(tmp_path):
    dataset = standard_dataset(tmp_path / "data", owner=None)
    with pytest.raises(TrainingError, match="dataset_governance_missing:owner"):
        _train(dataset, tmp_path / "model")


def test_rejects_jsonl_not_listed_in_manifest(tmp_path):
    dataset = standard_dataset(tmp_path / "data")
    (dataset / "stale.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(TrainingError, match="dataset_unlisted_file"):
        _train(dataset, tmp_path / "model")


def test_rejects_category_outside_taxonomy(tmp_path):
    bad = _rows([("lỗi lạ", "XYZ")], "train", "b")
    dataset = make_dataset(tmp_path / "data", {
        "train.jsonl": _rows(TRAIN, "train", "t") + bad,
        "dev.jsonl": _rows(VALIDATION, "validation", "v"),
    })
    with pytest.raises(TrainingError, match="row_category_invalid"):
        _train(dataset, tmp_path / "model")


def test_rejects_non_empty_output_dir(tmp_path):
    out = tmp_path / "model"
    out.mkdir()
    (out / "keep.txt").write_text("không ghi đè", encoding="utf-8")
    with pytest.raises(TrainingError, match="output_dir_not_empty"):
        _train(standard_dataset(tmp_path / "data"), out)


def test_candidate_needs_ai06_approval_and_threshold(tmp_path):
    dataset = standard_dataset(tmp_path / "data")
    with pytest.raises(TrainingError, match="candidate_requires_ai06_approval"):
        _train(dataset, tmp_path / "no-approval", status="candidate", category_threshold=0.5)

    approved = standard_dataset(tmp_path / "approved", approvalAI06="AI-06-test-001")
    with pytest.raises(TrainingError, match="candidate_requires_threshold"):
        _train(approved, tmp_path / "no-threshold", status="candidate")


async def test_candidate_artifact_loads_without_dev_stub_flag(tmp_path):
    dataset = standard_dataset(tmp_path / "data", approvalAI06="AI-06-test-001")
    out = tmp_path / "model"
    manifest = _train(dataset, out, status="candidate", category_threshold=0.0)
    assert manifest["status"] == "candidate"
    assert manifest["thresholds"] == {"category": 0.0}

    classifier = _provider(out, allow_dev_stub=False)
    try:
        assert classifier.ready
        prediction = await classifier.classify(title="máy in kẹt giấy", description="")
    finally:
        classifier.close()
    assert prediction.suggestions[0].score is None  # chưa có hiệu chuẩn, không phát điểm
