"""Đọc và kiểm chứng artifact mô hình trước khi nạp (ml-classifier-plan.md mục 4.4, K4).

Artifact không nằm trong Git; Dockerfile tải lúc build. Thư mục mô hình có `manifest.json`:

    {
      "schemaVersion": 1,
      "name": "tfidf-lr",
      "version": "2026.12.1",
      "preprocessingVersion": "1",
      "files": {"model.npz": "<sha256 hex>", "vocabulary.json": "<sha256 hex>"},
      "thresholds": {"category": 0.62, "impact": 0.55, "urgency": 0.55},
      "datasetVersion": "v1",
      "trainingCodeSha": "<git sha>"
    }

`thresholds` là ngưỡng abstain theo từng trường; trường vắng mặt nghĩa là mô hình không gợi ý trường
đó. Thiếu file, lệch SHA hay sai định dạng thì từ chối nạp: provider báo chưa sẵn sàng, không giả
lập dự đoán. Chỉ nạp file đã khớp SHA, kể cả khi buộc dùng định dạng pickle/joblib.
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
SCHEMA_VERSION = 1
FIELDS = frozenset({"category", "impact", "urgency"})

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
    files: Mapping[str, str]
    thresholds: Mapping[str, float]
    dataset_version: str | None
    training_code_sha: str | None

    @property
    def model_version(self) -> str:
        return f"{self.name}@{self.version}"

    def path(self, relative: str) -> Path:
        """Đường dẫn của một file đã được kiểm SHA; từ chối file không có trong manifest."""
        if relative not in self.files:
            raise ArtifactError("artifact_file_not_in_manifest")
        return self.root / relative


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
    name, version = raw.get("name"), raw.get("version")
    if not all(isinstance(item, str) and _IDENTIFIER.match(item) for item in (name, version)):
        raise ArtifactError("artifact_identity_invalid")
    if raw.get("preprocessingVersion") != PREPROCESSING_VERSION:
        raise ArtifactError("artifact_preprocessing_mismatch")

    files = _verified_files(root, raw.get("files"))
    thresholds = _thresholds(raw.get("thresholds"))
    return ArtifactManifest(
        root=root,
        name=name,
        version=version,
        files=MappingProxyType(files),
        thresholds=MappingProxyType(thresholds),
        dataset_version=_optional_str(raw.get("datasetVersion")),
        training_code_sha=_optional_str(raw.get("trainingCodeSha")),
    )


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
        if not _SHA256.match(expected):
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
    if not isinstance(value, dict) or not value or not set(value) <= FIELDS:
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


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ArtifactError("artifact_metadata_invalid")
    return value
