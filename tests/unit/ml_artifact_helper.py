"""Dựng artifact tí hon đúng schemaVersion 2 bằng lớp sklearn thật. Chỉ dùng trong tests/."""

from __future__ import annotations

import functools
import hashlib
import io
import json
import logging
import platform
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.pipeline import Pipeline

from supportflow_ai.adapters.classifiers.ml.artifact import MANIFEST_NAME
from supportflow_ai.adapters.classifiers.ml.contract_pin import CONTRACT_SHA256
from supportflow_ai.adapters.classifiers.ml.provider import MODEL_FILE
from supportflow_ai.adapters.classifiers.ml.text import PREPROCESSING_VERSION, model_input

TRAINING_PAIRS = (
    ("vpn không kết nối được", "VPN"),
    ("cisco anyconnect bị lỗi", "VPN"),
    ("máy in bị kẹt giấy", "PRINT"),
    ("máy in không in được", "PRINT"),
    ("quên mật khẩu đăng nhập", "ACC"),
    ("tài khoản bị khóa", "ACC"),
)


def build_model_bytes(
    pairs=TRAINING_PAIRS, *, calibrated: bool = False, estimator: str = "logreg",
) -> bytes:
    """Pipeline sklearn thuần (Pipeline, TfidfVectorizer, LogisticRegression, CalibratedClassifier).

    Đầu vào huấn luyện là `model_input(title, "")`, cùng hàm mà provider dùng khi suy luận.
    """
    if estimator == "hinge":
        classifier = SGDClassifier(loss="hinge", random_state=0)  # không có predict_proba
    else:
        classifier = LogisticRegression(max_iter=1000, random_state=0)
        if calibrated:
            classifier = CalibratedClassifierCV(classifier, cv=2)
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))),
        ("clf", classifier),
    ])
    pipeline.fit([model_input(text, "") for text, _ in pairs], [label for _, label in pairs])
    buffer = io.BytesIO()
    joblib.dump(pipeline, buffer)
    return buffer.getvalue()


@functools.cache
def tiny_model_bytes() -> bytes:
    return build_model_bytes()


def manifest_for(model_bytes: bytes, *, status: str = "dev-stub", calibrated: bool = False) -> dict:
    """Manifest hợp lệ cho `model_bytes`. Test sửa một trường rồi ghi lại bằng save_manifest."""
    manifest = {
        "schemaVersion": 2,
        "name": "tfidf-lr",
        "version": "2026.12.1",
        "status": status,
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
    if calibrated:
        manifest["calibration"] = {"method": "sigmoid", "splitOrFolds": "cv-2"}
    return manifest


def save_manifest(model_dir: Path, manifest: dict) -> None:
    text = json.dumps(manifest, ensure_ascii=False)
    (model_dir / MANIFEST_NAME).write_text(text, encoding="utf-8")


def write_artifact(
    model_dir: Path,
    *,
    model_bytes: bytes | None = None,
    status: str = "dev-stub",
    calibrated: bool = False,
    **overrides,
) -> dict:
    """Ghi model + manifest vào `model_dir`; `overrides` thay thế các khóa cấp cao nhất."""
    model_dir.mkdir(parents=True, exist_ok=True)
    data = tiny_model_bytes() if model_bytes is None else model_bytes
    (model_dir / MODEL_FILE).write_bytes(data)
    manifest = manifest_for(data, status=status, calibrated=calibrated) | overrides
    save_manifest(model_dir, manifest)
    return manifest


class LogCapture(logging.Handler):
    """Gắn trực tiếp vào logger: không bị `configure_logging` xóa như handler của caplog."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def text(self) -> str:
        return "\n".join(f"{record.getMessage()} {record.__dict__}" for record in self.records)

    def messages(self) -> list[str]:
        return [record.getMessage() for record in self.records]


@contextmanager
def capture_logs(logger_name: str) -> Iterator[LogCapture]:
    logger = logging.getLogger(logger_name)
    handler = LogCapture()
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
