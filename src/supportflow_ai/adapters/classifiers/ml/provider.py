"""Provider phân loại bằng mô hình sklearn nạp từ artifact (ml-classifier-plan.md mục 4, PR-4).

Chỉ phát gợi ý Category. Lỗi artifact hoặc môi trường làm `ready` = False: app vẫn khởi động,
`/health/ready` trả 503 và `classify` báo ProviderUnavailableError như NoOp. Lý do chỉ ghi vào log,
không ghi vào body. Gói này không import joblib hay scikit-learn ở mức module; chỉ import trong hàm.
"""

from __future__ import annotations

import io
import logging
import sys
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from supportflow_ai.adapters.classifiers.ml.artifact import (
    ArtifactError,
    ArtifactManifest,
    load_manifest,
    load_verified_bytes,
)
from supportflow_ai.adapters.classifiers.ml.contract_pin import CONTRACT_SHA256
from supportflow_ai.adapters.classifiers.ml.inference import BoundedInference
from supportflow_ai.adapters.classifiers.ml.text import model_input, normalize
from supportflow_ai.adapters.classifiers.severity_rules import infer_severity
from supportflow_ai.domain.classification import (
    Category,
    ClassificationPrediction,
    Suggestion,
    SuggestionField,
)
from supportflow_ai.domain.errors import ProviderUnavailableError

logger = logging.getLogger(__name__)

MODEL_FILE = "model.joblib"
_TAXONOMY = frozenset(item.value for item in Category)
_PACKAGES = (("scikit-learn", "sklearn"), ("numpy", "numpy"), ("joblib", "joblib"))


class _NotReady(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class MlClassifier:
    def __init__(
        self,
        *,
        model_dir: str | None,
        allow_dev_stub: bool,
        max_concurrency: int,
        max_queue: int,
        queue_timeout_s: float,
    ) -> None:
        self._runner = BoundedInference(
            max_concurrency=max_concurrency, max_queue=max_queue, queue_timeout_s=queue_timeout_s,
        )
        self._manifest: ArtifactManifest | None = None
        self._model: Any = None
        self._reason: str | None = None
        self._closed = False
        try:
            self._manifest, self._model = _load(model_dir, allow_dev_stub)
        except ArtifactError as exc:
            self._reason = exc.code
        except _NotReady as exc:
            self._reason = exc.reason
        except Exception:
            # Pickle hoặc thư viện lỗi: không nạp, không ghi chi tiết (có thể chứa đường dẫn).
            self._reason = "model_load_failed"
        if self._reason is not None:
            logger.warning("ml_provider_not_ready reason=%s", self._reason)

    @property
    def name(self) -> str:
        return "ml"

    @property
    def ready(self) -> bool:
        return self._reason is None

    @property
    def model_version(self) -> str | None:
        return self._manifest.model_version if self.ready and self._manifest else None

    async def classify(self, *, title: str, description: str) -> ClassificationPrediction:
        if not self.ready or self._closed:
            raise ProviderUnavailableError("classification_provider_not_ready")
        text = model_input(title, description)
        # Impact/Urgency theo rubric E0 (chỉ High), độc lập với model Category.
        severity = infer_severity(normalize(f"{title}\n{description}"))
        try:
            label, probability = await self._runner.run(self._predict, text)
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError("classification_inference_failed") from exc
        manifest = self._manifest
        if manifest is None:
            raise ProviderUnavailableError("classification_provider_not_ready")
        if probability < manifest.thresholds["category"]:
            return ClassificationPrediction(suggestions=severity)
        # Dev-stub không bao giờ phát điểm; candidate chỉ phát điểm khi đã hiệu chỉnh.
        score = probability if manifest.calibrated and manifest.status == "candidate" else None
        suggestion = Suggestion(SuggestionField.CATEGORY, Category(label), score)
        return ClassificationPrediction(suggestions=(suggestion, *severity))

    def close(self) -> None:
        self._closed = True
        self._runner.close()

    def _predict(self, text: str) -> tuple[str, float]:
        probabilities = self._model.predict_proba([text])[0]
        index = int(probabilities.argmax())
        return str(self._model.classes_[index]), float(probabilities[index])


def _load(model_dir: str | None, allow_dev_stub: bool) -> tuple[ArtifactManifest, Any]:
    if not model_dir:
        raise _NotReady("classifier_model_dir_missing")
    manifest = load_manifest(model_dir)
    if manifest.contract_sha256 != CONTRACT_SHA256:
        raise _NotReady("contract_sha_mismatch")
    if manifest.status == "dev-stub" and not allow_dev_stub:
        raise _NotReady("dev_stub_not_allowed")
    _check_environment(manifest.environment)
    data = load_verified_bytes(manifest, MODEL_FILE)
    # Import muộn: runtime không có joblib và scikit-learn (requirements-ml.txt).
    import joblib

    model = joblib.load(io.BytesIO(data))
    _check_model(model)
    return manifest, model


def _check_environment(environment: Mapping[str, str]) -> None:
    running_python = [str(part) for part in sys.version_info[:2]]
    if environment["python"].split(".")[:2] != running_python:
        raise _NotReady("environment_mismatch")
    for package, key in _PACKAGES:
        try:
            installed = version(package)
        except PackageNotFoundError as exc:
            raise _NotReady("environment_mismatch") from exc
        if installed != environment[key]:
            raise _NotReady("environment_mismatch")


def _check_model(model: Any) -> None:
    if not callable(getattr(model, "predict_proba", None)) or not hasattr(model, "classes_"):
        raise _NotReady("model_interface_invalid")
    if not {str(label) for label in model.classes_} <= _TAXONOMY:
        raise _NotReady("model_label_invalid")
