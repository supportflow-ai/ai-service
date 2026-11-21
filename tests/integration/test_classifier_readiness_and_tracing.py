"""K4: `/health/ready` theo `classifier.ready`; K5: log ghi provider và phiên bản mô hình."""

import json
import logging

from fastapi.testclient import TestClient

from supportflow_ai.application.classification.service import ClassifyTicket
from supportflow_ai.config import Settings
from supportflow_ai.domain.classification import (
    Category,
    ClassificationPrediction,
    Suggestion,
    SuggestionField,
)
from supportflow_ai.main import create_app
from supportflow_ai.observability.logging import JsonFormatter

PAYLOAD = {
    "requestId": "00000000-0000-0000-0000-000000000001",
    "ticketId": "00000000-0000-0000-0000-000000000002",
    "ticketRevision": 1,
    "inputHash": "e737e044b7ef976a6f2f2e97f1f2aaee633a2205cc16d051316bf2139d5dc02c",
    "title": "VPN issue",
    "description": "Cisco AnyConnect cannot connect",
}


class _ArtifactClassifier:
    """Giả lập provider dùng artifact: tên khác `noop` nhưng có thể chưa sẵn sàng."""

    def __init__(self, *, ready: bool) -> None:
        self._ready = ready

    @property
    def name(self) -> str:
        return "ml"

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def model_version(self) -> str | None:
        return "tfidf-lr@2026.12.1"

    async def classify(self, *, title: str, description: str) -> ClassificationPrediction:
        return ClassificationPrediction(
            suggestions=(Suggestion(SuggestionField.CATEGORY, Category.VPN, 0.91),)
        )


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(JsonFormatter().format(record))


def _app_with(classifier):
    app = create_app(Settings(environment="test", auth_enabled=False, classifier_provider="rule"))
    app.state.classifier = classifier
    app.state.classify_ticket = ClassifyTicket(classifier)
    return app


def test_ready_depends_on_classifier_readiness_not_on_provider_name():
    with TestClient(_app_with(_ArtifactClassifier(ready=False))) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "classifier": "ml"}

    with TestClient(_app_with(_ArtifactClassifier(ready=True))) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "classifier": "ml"}


def test_rule_and_noop_keep_the_health_body_that_smoke_http_expects():
    for provider, code, body in (
        ("rule", 200, {"status": "ready", "classifier": "rule"}),
        ("noop", 503, {"status": "degraded", "classifier": "noop"}),
    ):
        app = create_app(
            Settings(environment="test", auth_enabled=False, classifier_provider=provider)
        )
        with TestClient(app) as client:
            response = client.get("/health/ready")
        assert (response.status_code, response.json()) == (code, body)


def _completed_log(app) -> dict:
    handler = _Capture()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with TestClient(app) as client:
            response = client.post("/v1/ticket-classifications", json=PAYLOAD)
    finally:
        root.removeHandler(handler)
    assert response.status_code == 200
    lines = [json.loads(line) for line in handler.lines]
    return next(line for line in lines if line["message"] == "classification_completed")


def test_completed_log_records_provider_and_model_version():
    entry = _completed_log(_app_with(_ArtifactClassifier(ready=True)))
    assert entry["provider"] == "ml"
    assert entry["model_version"] == "tfidf-lr@2026.12.1"


def test_completed_log_omits_model_version_for_rule_provider():
    app = create_app(Settings(environment="test", auth_enabled=False, classifier_provider="rule"))
    entry = _completed_log(app)
    assert entry["provider"] == "rule"
    assert "model_version" not in entry


def test_tracing_does_not_change_the_response_body_or_headers():
    with TestClient(_app_with(_ArtifactClassifier(ready=True))) as client:
        response = client.post("/v1/ticket-classifications", json=PAYLOAD)
    assert set(response.json()) == {
        "requestId", "ticketId", "ticketRevision", "inputHash", "suggestions",
    }
    # Header X-SupportFlow-Model chưa được Backend duyệt (ml-classifier-plan.md mục 4.3).
    assert not any(name.lower().startswith("x-supportflow") for name in response.headers)


class _BrokenClassifier(_ArtifactClassifier):
    def __init__(self, result) -> None:
        super().__init__(ready=True)
        self._result = result

    async def classify(self, *, title: str, description: str):
        return self._result()


def _broken_invariant():
    # Category trong trường impact: Suggestion.__post_init__ ném ValueError.
    return ClassificationPrediction(
        suggestions=(Suggestion(SuggestionField.IMPACT, Category.VPN),)
    )


def test_provider_breaking_domain_invariants_gets_controlled_503_not_500():
    for result in (_broken_invariant, lambda: {"suggestions": []}):
        with TestClient(_app_with(_BrokenClassifier(result))) as client:
            response = client.post("/v1/ticket-classifications", json=PAYLOAD)
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "invalid_provider_output"}}
