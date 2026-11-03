from __future__ import annotations

import logging
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends

from supportflow_ai.api.dependencies import authorize_service, get_classify_ticket
from supportflow_ai.api.schemas.classification import (
    ClassificationRequest,
    ClassificationResponse,
    ClassificationSuggestion,
)
from supportflow_ai.application.classification.models import ClassificationCommand
from supportflow_ai.application.classification.service import ClassifyTicket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["classification"])


@router.post(
    "/ticket-classifications",
    response_model=ClassificationResponse,
    response_model_by_alias=True,
    dependencies=[Depends(authorize_service)],
)
async def classify_ticket(
    request: ClassificationRequest,
    use_case: Annotated[ClassifyTicket, Depends(get_classify_ticket)],
) -> ClassificationResponse:
    started = perf_counter()

    result = await use_case.execute(
        ClassificationCommand(
            request_id=request.request_id,
            ticket_id=request.ticket_id,
            ticket_revision=request.ticket_revision,
            input_hash=request.input_hash,
            title=request.title,
            description=request.description,
        )
    )

    response = ClassificationResponse(
        requestId=result.request_id,
        ticketId=result.ticket_id,
        ticketRevision=result.ticket_revision,
        inputHash=result.input_hash,
        suggestions=[
            ClassificationSuggestion(
                field=item.field.value,
                value=item.value.value,
                score=item.score,
            )
            for item in result.prediction.suggestions
        ],
    )

    logger.info(
        "classification_completed",
        extra={
            "request_id": str(result.request_id),
            "ticket_id": str(result.ticket_id),
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "outcome": "success",
        },
    )
    return response
