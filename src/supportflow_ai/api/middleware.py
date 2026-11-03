from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse


class LimitRequestBodyMiddleware:
    """Bound the classification request body before FastAPI parses JSON.

    Buffers at most max_bytes and also handles chunked bodies that omit Content-Length.
    A full request snapshot is needed for classification, so streaming downstream is not required.
    """

    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http" or scope.get("path") != "/v1/ticket-classifications":
            await self.app(scope, receive, send)
            return

        async def reject() -> None:
            response = JSONResponse(
                status_code=413, content={"detail": {"code": "payload_too_large"}}
            )
            await response(scope, receive, send)

        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await reject()
                        return
                except ValueError:
                    pass  # The ASGI server handles malformed HTTP framing.

        content = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            part = event.get("body", b"")
            if len(content) + len(part) > self.max_bytes:
                await reject()
                return
            content.extend(part)
            if not event.get("more_body", False):
                break

        was_replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal was_replayed
            if not was_replayed:
                was_replayed = True
                return {"type": "http.request", "body": bytes(content), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)
