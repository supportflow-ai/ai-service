from __future__ import annotations

from supportflow_ai.adapters.classifiers.noop import NoOpClassifier
from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier
from supportflow_ai.application.classification.service import ClassifyTicket
from supportflow_ai.config import Settings
from supportflow_ai.ports.classifier import TicketClassifier


def build_classifier(settings: Settings) -> TicketClassifier:
    if settings.classifier_provider == "rule":
        return RuleBasedClassifier()
    return NoOpClassifier()


def build_classification_use_case(settings: Settings) -> ClassifyTicket:
    return ClassifyTicket(build_classifier(settings))
