"""Dựng artifact tí hon đúng schemaVersion 2 cho test. Chỉ dùng trong tests/, không vào runtime."""

from __future__ import annotations

import functools
import hashlib
import io
import json
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from supportflow_ai.adapters.classifiers.ml.artifact import MANIFEST_NAME
from supportflow_ai.adapters.classifiers.ml.text import PREPROCESSING_VERSION, normalize

MODEL_FILE = "model.joblib"
# SHA-256 của contracts/ai/v1/openapi.yaml (ghim trong contract.lock.json).
CONTRACT_SHA256 = "ad1d93230158b9ee66c6e3d0843edafcadde97b01bd2adef62265e4cf7f16428"
_TRAINING_PAIRS = (
    ("vpn không kết nối được", "VPN"),
    ("cisco anyconnect bị lỗi", "VPN"),
    ("máy in bị kẹt giấy", "PRINT"),
    ("máy in không in được", "PRINT"),
    ("quên mật khẩu đăng nhập", "ACC"),
    ("tài khoản bị khóa", "ACC"),
)


@functools.cache
def tiny_model_bytes() -> bytes:
    """Pipeline sklearn nhỏ, serialize bằng joblib vào bộ nhớ (đúng đường nạp của provider)."""
    pipeline = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)),
        LogisticRegression(max_iter=1000, random_state=0),
    )
    pipeline.fit([normalize(text) for text, _ in _TRAINING_PAIRS],
                 [label for _, label in _TRAINING_PAIRS])
    buffer = io.BytesIO()
    joblib.dump(pipeline, buffer)
    return buffer.getvalue()


def manifest_for(model_bytes: bytes) -> dict:
    """Manifest hợp lệ cho `model_bytes`. Test sửa một trường rồi ghi lại bằng save_manifest."""
    return {
        "schemaVersion": 2,
        "name": "tfidf-lr",
        "version": "2026.12.1",
        "status": "dev-stub",
        "preprocessingVersion": PREPROCESSING_VERSION,
        "sourceSha": "a" * 40,
        "classificationContractSha256": CONTRACT_SHA256,
        "environment": {
            "python": platform.python_version(),
            "sklearn": version("scikit-learn"),
            "numpy": version("numpy"),
            "joblib": version("joblib"),
        },
        "dataset": {"version": "v1", "sha256": "1" * 64},
        "splitSha256": "2" * 64,
        "guidelineVersion": "CAT-2026-01",
        "model": {"family": "tfidf-logreg", "revision": "n/a", "seed": 20261120},
        "thresholds": {"category": 0.6},
        "files": {MODEL_FILE: hashlib.sha256(model_bytes).hexdigest()},
        "evaluation": {
            "development": "dev-stub, không phải kết quả của nhóm",
            "sealed": "CHƯA ĐO",
        },
    }


def save_manifest(model_dir: Path, manifest: dict) -> None:
    text = json.dumps(manifest, ensure_ascii=False)
    (model_dir / MANIFEST_NAME).write_text(text, encoding="utf-8")


def write_artifact(model_dir: Path, *, model_bytes: bytes | None = None, **overrides) -> dict:
    """Ghi model + manifest vào `model_dir`; `overrides` thay thế các khóa cấp cao nhất."""
    model_dir.mkdir(parents=True, exist_ok=True)
    data = tiny_model_bytes() if model_bytes is None else model_bytes
    (model_dir / MODEL_FILE).write_bytes(data)
    manifest = manifest_for(data) | overrides
    save_manifest(model_dir, manifest)
    return manifest
