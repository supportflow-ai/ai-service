from __future__ import annotations

from supportflow_ai.application.classification.models import (
    ClassificationCommand,
    ClassificationResult,
)
from supportflow_ai.ports.classifier import TicketClassifier


class ClassifyTicket:
    """Application use case.

    It intentionally does not know anything about authentication, HTTP, PostgreSQL,
    ticket priority, confidence bands, assignment or workflow transitions.
    """

    def __init__(self, classifier: TicketClassifier) -> None:
        self._classifier = classifier

    async def execute(self, command: ClassificationCommand) -> ClassificationResult:
        prediction = await self._classifier.classify(
            title=command.title,
            description=command.description,
        )
        return ClassificationResult(
            request_id=command.request_id,
            ticket_id=command.ticket_id,
            ticket_revision=command.ticket_revision,
            input_hash=command.input_hash,
            prediction=prediction,
        )
