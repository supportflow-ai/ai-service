from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from supportflow_ai.domain.errors import InvalidProviderOutputError, ProviderUnavailableError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Do not echo ticket content in logs or error bodies.
        logger.info("request_validation_failed", extra={"outcome": "invalid_request"})
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": {"code": "invalid_snapshot"}},
        )

    @app.exception_handler(ProviderUnavailableError)
    async def provider_unavailable(
        request: Request,
        exc: ProviderUnavailableError,
    ) -> JSONResponse:
        logger.warning("provider_unavailable", extra={"outcome": "unavailable"})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": {"code": "provider_unavailable"}},
        )

    @app.exception_handler(InvalidProviderOutputError)
    async def invalid_provider_output(
        request: Request,
        exc: InvalidProviderOutputError,
    ) -> JSONResponse:
        logger.warning("invalid_provider_output", extra={"outcome": "unavailable"})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": {"code": "invalid_provider_output"}},
        )
