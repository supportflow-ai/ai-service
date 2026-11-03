import pytest
from pydantic import ValidationError

from supportflow_ai.config import Settings


def test_auth_enabled_by_default_and_no_default_token():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_staging_cannot_disable_auth():
    with pytest.raises(ValidationError):
        Settings(environment="staging", auth_enabled=False)


def test_production_cannot_disable_auth():
    with pytest.raises(ValidationError):
        Settings(environment="production", auth_enabled=False)


def test_placeholder_token_rejected():
    with pytest.raises(ValidationError):
        Settings(service_token="replace-with-a-long-random-service-token")


def test_invalid_request_budget_rejected():
    with pytest.raises(ValidationError):
        Settings(auth_enabled=False, max_request_bytes=99)


def test_compose_prefixed_settings_enable_authenticated_rule_provider(monkeypatch):
    monkeypatch.setenv("SUPPORTFLOW_AI_ENVIRONMENT", "production")
    monkeypatch.setenv(
        "SUPPORTFLOW_AI_SERVICE_TOKEN", "synthetic-test-service-token-at-least-32-characters"
    )
    monkeypatch.setenv("SUPPORTFLOW_AI_CLASSIFIER_PROVIDER", "rule")
    monkeypatch.setenv("SUPPORTFLOW_AI_AUTH_ENABLED", "true")
    settings = Settings(_env_file=None)
    assert settings.environment == "production"
    assert settings.auth_enabled
    assert settings.classifier_provider == "rule"
    assert settings.service_token is not None
