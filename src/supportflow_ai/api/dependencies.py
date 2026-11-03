from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from supportflow_ai.api.auth import bearer_scheme, require_service_bearer
from supportflow_ai.application.classification.service import ClassifyTicket


async def authorize_service(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    await require_service_bearer(request, credentials)


def get_classify_ticket(request: Request) -> ClassifyTicket:
    return request.app.state.classify_ticket
