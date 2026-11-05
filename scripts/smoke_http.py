"""Kiểm tra hợp đồng qua HTTP loopback bên trong container đã khởi động."""

import json
import os
from http.client import HTTPConnection
from time import sleep
from uuid import uuid4

CLASSIFICATION_PATH = "/v1/ticket-classifications"


def request_json(
    path: str, payload: dict[str, object] | None = None, token: str | None = None
) -> tuple[int, dict[str, object]]:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    method = "GET" if payload is None else "POST"
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    connection = HTTPConnection("127.0.0.1", 8000, timeout=2)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def check_response(
    name: str, actual: tuple[int, dict[str, object]], status: int, body: dict[str, object]
) -> None:
    actual_status, actual_body = actual
    if actual_status != status:
        raise SystemExit(f"{name}: nhận HTTP {actual_status}, mong đợi {status}.")
    if actual_body != body:
        raise SystemExit(f"{name}: nội dung phản hồi không khớp hợp đồng.")
    print(f"Đạt | {name} | HTTP {status}")


def wait_for_live(provider: str) -> None:
    for _ in range(30):
        try:
            response = request_json("/health/live")
        except OSError:
            sleep(1)
        else:
            check_response(f"{provider} liveness", response, 200, {"status": "ok"})
            return
    raise SystemExit(f"{provider}: hết thời gian chờ HTTP liveness.")


def check_rule(token: str, max_request_bytes: int) -> None:
    check_response(
        "rule readiness",
        request_json("/health/ready"),
        200,
        {"status": "ready", "classifier": "rule"},
    )
    correlation = {
        "requestId": str(uuid4()),
        "ticketId": str(uuid4()),
        "ticketRevision": 7,
        "inputHash": "a" * 64,
    }
    vpn = {**correlation, "title": "Lỗi VPN", "description": "Cisco AnyConnect không kết nối"}
    sec = {
        **vpn,
        "requestId": str(uuid4()),
        "ticketId": str(uuid4()),
        "inputHash": "b" * 64,
        "title": "Email đáng ngờ",
        "description": "Nghi phishing",
    }
    for category, payload in (("VPN", vpn), ("SEC", sec)):
        check_response(
            f"Phân loại {category} và đối chiếu metadata",
            request_json(CLASSIFICATION_PATH, payload, token),
            200,
            {
                **{key: payload[key] for key in correlation},
                "suggestions": [{"field": "category", "value": category, "score": None}],
            },
        )

    for name, payload, bearer, status, error in (
        ("Bearer sai", vpn, "token-khong-hop-le", 401, "invalid_service_credential"),
        ("Revision boolean", {**vpn, "ticketRevision": True}, token, 400, "invalid_snapshot"),
        (
            "Payload quá giới hạn",
            {**vpn, "description": "x" * (max_request_bytes + 1)},
            token,
            413,
            "payload_too_large",
        ),
    ):
        check_response(
            name, request_json(CLASSIFICATION_PATH, payload, bearer), status,
            {"detail": {"code": error}},
        )


def main() -> None:
    provider = os.environ["SUPPORTFLOW_AI_CLASSIFIER_PROVIDER"]
    wait_for_live(provider)
    if provider == "rule":
        check_rule(
            os.environ["SUPPORTFLOW_AI_SERVICE_TOKEN"],
            int(os.environ["SUPPORTFLOW_AI_MAX_REQUEST_BYTES"]),
        )
    elif provider == "noop":
        check_response(
            "noop readiness",
            request_json("/health/ready"),
            503,
            {"status": "degraded", "classifier": "noop"},
        )
    else:
        raise SystemExit("Smoke test chỉ hỗ trợ hai cấu hình rule và noop.")


if __name__ == "__main__":
    main()
