from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from supportflow_ai.adapters.classifiers.ml.inference import (
    MAX_CONCURRENCY_LIMIT,
    MAX_QUEUE_LIMIT,
    MAX_QUEUE_TIMEOUT_S,
)

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
    classifier_provider: Literal["noop", "rule", "ml"] = "noop"
    # Giá trị mặc định của các trường ml dưới đây là giả định kỹ thuật, chưa có trong tài liệu.
    classifier_model_dir: str | None = None
    classifier_max_concurrency: int = 2
    classifier_max_queue: int = 8
    classifier_queue_timeout_s: float = 3.0
    allow_dev_stub: bool = False
    embedding_provider: Literal["noop", "local-e5"] = "noop"
    embedding_cache_dir: str | None = None
    log_level: str = "INFO"
    max_request_bytes: int = 65_536

    @model_validator(mode="after")
    def validate_security(self) -> Settings:
        if self.environment not in {"development", "test"} and not self.auth_enabled:
            raise ValueError("Authentication may only be disabled in development or test.")
        if not 1024 <= self.max_request_bytes <= 1_048_576:
            raise ValueError("max_request_bytes must be in [1024, 1048576].")
        self._validate_classifier()
        if self.auth_enabled:
            token = self.service_token.get_secret_value() if self.service_token else ""
            if len(token) < 32 or token.casefold().strip() in _UNSAFE_TOKENS:
                raise ValueError(
                    "Provide a non-placeholder service token at least 32 characters long."
                )
        return self

    def _validate_classifier(self) -> None:
        if self.classifier_provider == "ml" and not self.classifier_model_dir:
            raise ValueError("classifier_model_dir is required when classifier_provider is ml.")
        if not 1 <= self.classifier_max_concurrency <= MAX_CONCURRENCY_LIMIT:
            raise ValueError(f"classifier_max_concurrency must be in [1, {MAX_CONCURRENCY_LIMIT}].")
        if not 0 <= self.classifier_max_queue <= MAX_QUEUE_LIMIT:
            raise ValueError(f"classifier_max_queue must be in [0, {MAX_QUEUE_LIMIT}].")
        if not 0.0 < self.classifier_queue_timeout_s <= MAX_QUEUE_TIMEOUT_S:
            raise ValueError(f"classifier_queue_timeout_s must be in (0, {MAX_QUEUE_TIMEOUT_S}].")
        if self.allow_dev_stub and self.environment not in {"development", "test"}:
            raise ValueError("allow_dev_stub may only be enabled in development or test.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
