import json

import httpx
import pytest
from fastapi.testclient import TestClient

from supportflow_ai.application.classification.service import ClassifyTicket
from supportflow_ai.config import Settings
from supportflow_ai.main import create_app

TOKEN = "secure-integration-test-service-token-very-long"
PAYLOAD = {
    "requestId": "00000000-0000-0000-0000-000000000001",
    "ticketId": "00000000-0000-0000-0000-000000000002",
    "ticketRevision": 1,
    "inputHash": "a" * 64,
    "title": "VPN issue",
    "description": "Cisco AnyConnect cannot connect",
}


def _client():
    return TestClient(
        create_app(
            Settings(
                environment="test",
                auth_enabled=True,
                service_token=TOKEN,
                classifier_provider="rule",
                max_request_bytes=1024,
            )
        )
    )


def test_rejects_wrong_service_bearer():
    with _client() as client:
        response = client.post(
            "/v1/ticket-classifications",
            json=PAYLOAD,
            headers={"Authorization": "Bearer wrong"},
        )
    assert response.status_code == 401


def test_rejects_large_content_length_413():
    with _client() as client:
        response = client.post(
            "/v1/ticket-classifications",
            json={**PAYLOAD, "description": "x" * 2000},
            headers={"Authorization": "Bearer " + TOKEN},
        )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "payload_too_large"


@pytest.mark.asyncio
async def test_rejects_chunked_payload_without_content_length():
    async def stream():
        yield json.dumps({**PAYLOAD, "description": "x" * 2000}).encode("utf-8")

    app = create_app(
        Settings(
            environment="test",
            auth_enabled=True,
            service_token=TOKEN,
            classifier_provider="rule",
            max_request_bytes=1024,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/v1/ticket-classifications",
            content=stream(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN},
        )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "payload_too_large"


def test_rejects_invalid_uuid_hash_and_unknown_fields():
    with _client() as client:
        for changed in (
            {"ticketId": "abc"},
            {"inputHash": "NOT_HASH"},
            {"actions": ["resolve"]},
            {"ticketRevision": -1},
            {"ticketRevision": True},
            {"ticketRevision": "1"},
        ):
            response = client.post(
                "/v1/ticket-classifications",
                json={**PAYLOAD, **changed},
                headers={"Authorization": "Bearer " + TOKEN},
            )
            assert response.status_code == 400
            assert response.json()["detail"] == {"code": "invalid_snapshot"}


def test_production_has_no_openapi_endpoint():
    app = create_app(
        Settings(environment="production", classifier_provider="rule", service_token=TOKEN)
    )
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_noop_readiness_reports_degraded():
    app = create_app(Settings(environment="test", auth_enabled=False, classifier_provider="noop"))
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


def test_snake_case_aliases_not_accepted_by_versioned_contract():
    body = PAYLOAD.copy()
    body["request_id"] = body.pop("requestId")
    with _client() as client:
        response = client.post(
            "/v1/ticket-classifications",
            json=body,
            headers={"Authorization": "Bearer " + TOKEN},
        )
    assert response.status_code == 400



def test_invalid_provider_output_has_controlled_response():
    from supportflow_ai.domain.errors import InvalidProviderOutputError

    class BadClassifier:
        async def classify(self, *, title: str, description: str):
            raise InvalidProviderOutputError("do not expose raw provider details")

    app = create_app(Settings(environment="test", auth_enabled=False, classifier_provider="rule"))
    app.state.classify_ticket = ClassifyTicket(BadClassifier())
    with TestClient(app) as client:
        response = client.post("/v1/ticket-classifications", json=PAYLOAD)
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "invalid_provider_output"}}
    assert "do not expose" not in response.text
