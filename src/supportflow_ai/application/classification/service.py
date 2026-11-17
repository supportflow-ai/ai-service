from __future__ import annotations

from supportflow_ai.application.classification.models import (
    ClassificationCommand,
    ClassificationResult,
)
from supportflow_ai.domain.classification import ClassificationPrediction
from supportflow_ai.domain.errors import InvalidProviderOutputError
from supportflow_ai.ports.classifier import TicketClassifier


class ClassifyTicket:
    """Application use case.

    It intentionally does not know anything about authentication, HTTP, PostgreSQL,
    ticket priority, confidence bands, assignment or workflow transitions.
    """

    def __init__(self, classifier: TicketClassifier) -> None:
        self._classifier = classifier

    async def execute(self, command: ClassificationCommand) -> ClassificationResult:
        try:
            prediction = await self._classifier.classify(
                title=command.title,
                description=command.description,
            )
        except ValueError as exc:
            # Bất biến domain (Suggestion, ClassificationPrediction) bị vi phạm trong provider:
            # trả 503 có kiểm soát thay vì 500, không lộ chi tiết.
            raise InvalidProviderOutputError("prediction_invariant_violated") from exc
        if not isinstance(prediction, ClassificationPrediction):
            raise InvalidProviderOutputError("prediction_type_invalid")
        return ClassificationResult(
            request_id=command.request_id,
            ticket_id=command.ticket_id,
            ticket_revision=command.ticket_revision,
            input_hash=command.input_hash,
            prediction=prediction,
            provider=self._classifier.name,
            model_version=self._classifier.model_version,
        )
