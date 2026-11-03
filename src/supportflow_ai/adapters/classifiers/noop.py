from supportflow_ai.domain.errors import ProviderUnavailableError


class NoOpClassifier:
    @property
    def name(self) -> str:
        return "noop"

    async def classify(self, *, title: str, description: str):
        raise ProviderUnavailableError("classification_provider_not_configured")
