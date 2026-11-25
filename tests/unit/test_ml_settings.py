import pytest
from pydantic import SecretStr, ValidationError

from supportflow_ai.config import Settings

TOKEN = SecretStr("synthetic-test-service-token-at-least-32-characters")


def test_ml_provider_requires_model_dir():
    with pytest.raises(ValidationError, match="classifier_model_dir is required"):
        Settings(_env_file=None, auth_enabled=False, classifier_provider="ml")


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_dev_stub_flag_is_refused_outside_development_and_test(environment):
    with pytest.raises(ValidationError, match="allow_dev_stub"):
        Settings(
            _env_file=None,
            environment=environment,
            service_token=TOKEN,
            allow_dev_stub=True,
        )


def test_dev_stub_flag_is_allowed_in_development():
    settings = Settings(_env_file=None, auth_enabled=False, allow_dev_stub=True)
    assert settings.allow_dev_stub


@pytest.mark.parametrize(
    "limits",
    [
        {"classifier_max_concurrency": 0},
        {"classifier_max_concurrency": 17},
        {"classifier_max_queue": 257},
        {"classifier_queue_timeout_s": 0},
        {"classifier_queue_timeout_s": 4.5},
    ],
)
def test_classifier_limits_are_checked_at_startup(limits):
    with pytest.raises(ValidationError, match="classifier_"):
        Settings(_env_file=None, auth_enabled=False, **limits)
