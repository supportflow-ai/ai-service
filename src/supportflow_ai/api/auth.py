from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


async def require_service_bearer(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> None:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return

    if credentials is None:
        # FastAPI does not inject security dependencies into plain functions automatically;
        # the route dependency wrapper in dependencies.py supplies this value.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_service_credential"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = settings.service_token.get_secret_value()
    if credentials.scheme.casefold() != "bearer" or not secrets.compare_digest(
        credentials.credentials,
        token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_service_credential"},
            headers={"WWW-Authenticate": "Bearer"},
        )
