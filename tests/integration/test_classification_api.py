import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from supportflow_ai.config import Settings
from supportflow_ai.main import create_app

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "contracts/ai/v1/openapi.yaml").read_text(encoding="utf-8"))


def _schema(name: str):
    return {
        "$ref": f"#/components/schemas/{name}",
        "components": SPEC["components"],
    }


VALID_REQUEST = {
    "requestId": "00000000-0000-0000-0000-000000000001",
    "ticketId": "00000000-0000-0000-0000-000000000002",
    "ticketRevision": 1,
    "inputHash": "e737e044b7ef976a6f2f2e97f1f2aaee633a2205cc16d051316bf2139d5dc02c",
    "title": "VPN issue",
    "description": "Cisco AnyConnect cannot connect",
}


def test_rule_provider_response_conforms_to_backend_contract():
    app = create_app(
        Settings(
            auth_enabled=False,
            classifier_provider="rule",
        )
    )
    client = TestClient(app)

    response = client.post("/v1/ticket-classifications", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.json()
    Draft202012Validator(
        _schema("ClassificationResponse"),
        format_checker=FormatChecker(),
    ).validate(body)
    assert body["requestId"] == VALID_REQUEST["requestId"]
    assert body["ticketId"] == VALID_REQUEST["ticketId"]
    assert body["ticketRevision"] == VALID_REQUEST["ticketRevision"]
    assert body["inputHash"] == VALID_REQUEST["inputHash"]
    assert body["suggestions"] == [{"field": "category", "value": "VPN", "score": None}]
    assert "priority" not in body
    assert "actions" not in body


def test_request_with_extra_business_field_is_rejected_as_400():
    app = create_app(Settings(auth_enabled=False, classifier_provider="rule"))
    client = TestClient(app)

    payload = {**VALID_REQUEST, "priority": "P1"}
    response = client.post("/v1/ticket-classifications", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_snapshot"


def test_service_bearer_is_enforced_when_enabled():
    app = create_app(
        Settings(
            auth_enabled=True,
            service_token="test-secret-token" + "x" * 32,
            classifier_provider="rule",
        )
    )
    client = TestClient(app)

    unauthorized = client.post("/v1/ticket-classifications", json=VALID_REQUEST)
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/v1/ticket-classifications",
        json=VALID_REQUEST,
        headers={"Authorization": "Bearer " + "test-secret-token" + "x" * 32},
    )
    assert authorized.status_code == 200


def test_noop_provider_returns_controlled_503():
    app = create_app(Settings(auth_enabled=False, classifier_provider="noop"))
    client = TestClient(app)

    response = client.post("/v1/ticket-classifications", json=VALID_REQUEST)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_unavailable"
