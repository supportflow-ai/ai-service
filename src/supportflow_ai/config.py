from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_UNSAFE_TOKENS = {
    'replace-with-a-long-random-service-token',
    'changeme',
    'your-token',
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPORTFLOW_AI_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    auth_enabled: bool = True
    service_token: SecretStr | None = None
    classifier_provider: Literal["noop", "rule"] = "noop"
    log_level: str = "INFO"
    max_request_bytes: int = 65_536

    @model_validator(mode="after")
    def validate_security(self) -> Settings:
        if self.environment not in {"development", "test"} and not self.auth_enabled:
            raise ValueError("Authentication may only be disabled in development or test.")
        if not 1024 <= self.max_request_bytes <= 1_048_576:
            raise ValueError("max_request_bytes must be in [1024, 1048576].")
        if self.auth_enabled:
            token = self.service_token.get_secret_value() if self.service_token else ""
            if len(token) < 32 or token.casefold().strip() in _UNSAFE_TOKENS:
                raise ValueError(
                    "Provide a non-placeholder service token at least 32 characters long."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
