from supportflow_ai.domain.errors import ProviderUnavailableError


class NoOpEmbedder:
    @property
    def name(self) -> str:
        return "noop"

    async def embed(self, *, text: str):
        raise ProviderUnavailableError("embedding_provider_not_configured")
