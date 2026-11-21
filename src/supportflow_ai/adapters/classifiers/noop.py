from supportflow_ai.domain.errors import ProviderUnavailableError


class NoOpClassifier:
    @property
    def name(self) -> str:
        return "noop"

    @property
    def ready(self) -> bool:
        return False

    @property
    def model_version(self) -> str | None:
        return None

    async def classify(self, *, title: str, description: str):
        raise ProviderUnavailableError("classification_provider_not_configured")
