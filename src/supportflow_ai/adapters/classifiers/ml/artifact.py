"""Đọc và kiểm chứng artifact mô hình trước khi nạp (ml-classifier-plan.md mục 4.4, K4).

Artifact không nằm trong Git; Dockerfile tải và kiểm SHA lúc build (AGENTS.md mục 3).
Thư mục mô hình có `manifest.json` schemaVersion 2 (mẫu đầy đủ: `tests/unit/ml_artifact_helper.py`):

    {
      "schemaVersion": 2, "name": "tfidf-lr", "version": "2026.12.1",
      "status": "dev-stub",                       # dev-stub | candidate
      "preprocessingVersion": "1",
      "sourceSha": "<40 ký tự, commit mã huấn luyện>",
      "classificationContractSha256": "<SHA-256 của contracts/ai/v1/openapi.yaml>",
      "environment": {"python": "...", "sklearn": "...", "numpy": "...", "joblib": "..."},
      "dataset": {"version": "v1", "sha256": "<hex>"},
      "splitSha256": "<hex>", "guidelineVersion": "CAT-2026-01",
      "model": {"family": "...", "revision": "...", "seed": 20261120},
      "calibration": {"method": "sigmoid", "splitOrFolds": "groupkfold-5"},   # tùy chọn
      "thresholds": {"category": 0.62},           # bắt buộc category; impact, urgency tùy chọn
      "files": {"model.joblib": "<sha256 hex>"},
      "evaluation": {"development": "...", "sealed": "CHƯA ĐO"}
    }

`load_manifest` kiểm cấu trúc và băm mọi file để báo lỗi sớm lúc khởi động. `load_verified_bytes`
đọc đúng một lần, băm chính các byte đó rồi trả về để nạp từ BytesIO. Không băm rồi đọc lại file
(TOCTOU). Lỗi thì từ chối nạp: provider báo chưa sẵn sàng, không giả lập dự đoán.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from supportflow_ai.adapters.classifiers.ml.text import PREPROCESSING_VERSION

MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = 2
FIELDS = frozenset({"category", "impact", "urgency"})
STATUSES = frozenset({"dev-stub", "candidate"})
ENVIRONMENT_KEYS = frozenset({"python", "sklearn", "numpy", "joblib"})

_REQUIRED_KEYS = frozenset({
    "schemaVersion", "name", "version", "status", "preprocessingVersion", "sourceSha",
    "classificationContractSha256", "environment", "dataset", "splitSha256", "guidelineVersion",
    "model", "thresholds", "files", "evaluation",
})
_OPTIONAL_KEYS = frozenset({"calibration"})

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")


class ArtifactError(ValueError):
    """Artifact không dùng được. `code` là mã ngắn, an toàn để ghi log."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    root: Path
    name: str
    version: str
    status: str
    thresholds: Mapping[str, float]
    files: Mapping[str, str]
    environment: Mapping[str, str]
    calibrated: bool

    @property
    def model_version(self) -> str:
        return f"{self.name}@{self.version}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(model_dir: str | Path) -> ArtifactManifest:
    root = Path(model_dir).resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ArtifactError("artifact_manifest_missing")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("artifact_manifest_invalid") from exc
    if not isinstance(raw, dict):
        raise ArtifactError("artifact_manifest_invalid")
    if raw.get("schemaVersion") != SCHEMA_VERSION:
        raise ArtifactError("artifact_schema_unsupported")
    keys = set(raw)
    if _REQUIRED_KEYS - keys or keys - (_REQUIRED_KEYS | _OPTIONAL_KEYS):
        raise ArtifactError("artifact_manifest_invalid")

    name, version = raw["name"], raw["version"]
    if not all(isinstance(item, str) and _IDENTIFIER.fullmatch(item) for item in (name, version)):
        raise ArtifactError("artifact_identity_invalid")
    if raw["preprocessingVersion"] != PREPROCESSING_VERSION:
        raise ArtifactError("artifact_preprocessing_mismatch")
    if raw["status"] not in STATUSES:
        raise ArtifactError("artifact_status_invalid")
    environment = _check_metadata(raw)
    if "calibration" in raw:
        calibration = _mapping(
            raw["calibration"], {"method", "splitOrFolds"}, "artifact_calibration_invalid",
        )
        for value in calibration.values():
            _text(value, "artifact_calibration_invalid")

    files = _verified_files(root, raw["files"])
    return ArtifactManifest(
        root=root,
        name=name,
        version=version,
        status=raw["status"],
        thresholds=MappingProxyType(_thresholds(raw["thresholds"])),
        files=MappingProxyType(files),
        environment=MappingProxyType(environment),
        calibrated="calibration" in raw,
    )


def load_verified_bytes(manifest: ArtifactManifest, relative: str) -> bytes:
    """Đọc đúng một lần, băm chính các byte đó và trả về để nạp. Không đọc lại file sau khi băm."""
    expected = manifest.files.get(relative)
    if expected is None:
        raise ArtifactError("artifact_file_not_in_manifest")
    path = (manifest.root / relative).resolve()
    # Kiểm lại tại thời điểm đọc: symlink có thể được đặt sau lúc load_manifest.
    if not path.is_relative_to(manifest.root):
        raise ArtifactError("artifact_path_invalid")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ArtifactError("artifact_file_missing") from exc
    if hashlib.sha256(data).hexdigest() != expected:
        raise ArtifactError("artifact_sha_mismatch")
    return data


def _check_metadata(raw: dict) -> dict[str, str]:
    _text(raw["sourceSha"], "artifact_source_sha_invalid", _GIT_SHA, limit=40)
    _text(raw["classificationContractSha256"], "artifact_contract_sha_invalid", _SHA256, limit=64)
    _text(raw["splitSha256"], "artifact_split_sha_invalid", _SHA256, limit=64)
    _text(raw["guidelineVersion"], "artifact_metadata_invalid")
    dataset = _mapping(raw["dataset"], {"version", "sha256"}, "artifact_dataset_invalid")
    _text(dataset["version"], "artifact_dataset_invalid")
    _text(dataset["sha256"], "artifact_dataset_invalid", _SHA256, limit=64)
    model = _mapping(raw["model"], {"family", "revision", "seed"}, "artifact_model_invalid")
    _text(model["family"], "artifact_model_invalid", limit=64)
    _text(model["revision"], "artifact_model_invalid", limit=64)
    if isinstance(model["seed"], bool) or not isinstance(model["seed"], int):
        raise ArtifactError("artifact_model_invalid")
    evaluation = _mapping(
        raw["evaluation"], {"development", "sealed"}, "artifact_evaluation_invalid",
    )
    _text(evaluation["development"], "artifact_evaluation_invalid")
    _text(evaluation["sealed"], "artifact_evaluation_invalid")
    environment = _mapping(raw["environment"], ENVIRONMENT_KEYS, "artifact_environment_invalid")
    return {key: _text(value, "artifact_environment_invalid", limit=64)
            for key, value in environment.items()}


def _verified_files(root: Path, files: object) -> dict[str, str]:
    if not isinstance(files, dict) or not files:
        raise ArtifactError("artifact_files_invalid")
    verified: dict[str, str] = {}
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ArtifactError("artifact_files_invalid")
        pure = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or pure.is_absolute()
            or ".." in pure.parts
            or relative == MANIFEST_NAME
        ):
            raise ArtifactError("artifact_path_invalid")
        if not _SHA256.fullmatch(expected):
            raise ArtifactError("artifact_sha_invalid")
        path = (root / relative).resolve()
        # Chặn symlink trỏ ra ngoài thư mục mô hình.
        if not path.is_relative_to(root):
            raise ArtifactError("artifact_path_invalid")
        if not path.is_file():
            raise ArtifactError("artifact_file_missing")
        if file_sha256(path) != expected:
            raise ArtifactError("artifact_sha_mismatch")
        verified[relative] = expected
    return verified


def _thresholds(value: object) -> dict[str, float]:
    if not isinstance(value, dict) or "category" not in value or not set(value) <= FIELDS:
        raise ArtifactError("artifact_thresholds_invalid")
    result: dict[str, float] = {}
    for field, threshold in value.items():
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, int | float)
            or not math.isfinite(threshold)
            or not 0.0 <= threshold <= 1.0
        ):
            raise ArtifactError("artifact_thresholds_invalid")
        result[field] = float(threshold)
    return result


def _mapping(value: object, expected: frozenset[str] | set[str], code: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ArtifactError(code)
    return value


def _text(
    value: object, code: str, pattern: re.Pattern[str] | None = None, *, limit: int = 128,
) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ArtifactError(code)
    if pattern is not None and not pattern.fullmatch(value):
        raise ArtifactError(code)
    return value
