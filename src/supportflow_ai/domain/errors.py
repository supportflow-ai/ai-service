class AIServiceError(Exception):
    """Base exception for controlled AI service failures."""


class ProviderUnavailableError(AIServiceError):
    """Raised when the selected inference provider is unavailable."""


class InvalidProviderOutputError(AIServiceError):
    """Raised when a provider violates internal prediction invariants."""
