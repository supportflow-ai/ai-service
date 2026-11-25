import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from supportflow_ai.config import Settings
from supportflow_ai.main import create_app
from tests.unit.ml_artifact_helper import capture_logs, write_artifact

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "contracts/ai/v1/openapi.yaml").read_text(encoding="utf-8"))
TOKEN = "synthetic-test-service-token-at-least-32-characters"
MARKER = "PHIEU-MARKER-7731"
PAYLOAD = {
    "requestId": "00000000-0000-0000-0000-000000000001",
    "ticketId": "00000000-0000-0000-0000-000000000002",
    "ticketRevision": 1,
    "inputHash": "e737e044b7ef976a6f2f2e97f1f2aaee633a2205cc16d051316bf2139d5dc02c",
    "title": "vpn không kết nối được",
    "description": "máy tính không kết nối được",
}
ROUTE_LOGGER = "supportflow_ai.api.routes.classification"


def _schema(name: str):
    return {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]}


def _ml_app(model_dir, **overrides):
    settings = {
        "_env_file": None,
        "auth_enabled": False,
        "classifier_provider": "ml",
        "classifier_model_dir": str(model_dir),
        **overrides,
    }
    return create_app(Settings(**settings))


def test_ml_route_echoes_ids_and_returns_schema_valid_category(tmp_path):
    write_artifact(tmp_path, status="dev-stub", thresholds={"category": 0.0})
    client = TestClient(_ml_app(tmp_path, allow_dev_stub=True))
    response = client.post("/v1/ticket-classifications", json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(
        _schema("ClassificationResponse"), format_checker=FormatChecker(),
    ).validate(body)
    for key in ("requestId", "ticketId", "ticketRevision", "inputHash"):
        assert body[key] == PAYLOAD[key]
    (suggestion,) = body["suggestions"]
    assert suggestion["field"] == "category"
    assert suggestion["value"] in {"VPN", "PRINT", "ACC"}
    assert suggestion["score"] is None  # dev-stub không phát điểm
    assert "priority" not in body


def test_ml_route_returns_503_when_artifact_is_missing(tmp_path):
    client = TestClient(_ml_app(tmp_path / "missing"))
    response = client.post("/v1/ticket-classifications", json=PAYLOAD)
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "provider_unavailable"}}


def test_ml_route_keeps_bearer_and_body_limit_checks(tmp_path):
    client = TestClient(
        _ml_app(tmp_path / "missing", auth_enabled=True, service_token=TOKEN),
    )
    assert client.post("/v1/ticket-classifications", json=PAYLOAD).status_code == 401
    oversized = {**PAYLOAD, "description": "a" * 70_000}
    response = client.post(
        "/v1/ticket-classifications",
        json=oversized,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 413


def test_ml_route_logs_never_contain_ticket_text(tmp_path):
    write_artifact(tmp_path, status="candidate", thresholds={"category": 0.0})
    client = TestClient(_ml_app(tmp_path))
    payload = {
        **PAYLOAD,
        "title": f"vpn {MARKER}",
        "description": f"không kết nối {MARKER}",
    }
    with capture_logs(ROUTE_LOGGER) as logs:
        assert client.post("/v1/ticket-classifications", json=payload).status_code == 200
    # Phải thấy log hoàn tất của route (chứng minh route đã chạy) và không có nội dung phiếu.
    assert "classification_completed" in logs.messages()
    assert MARKER not in logs.text()
