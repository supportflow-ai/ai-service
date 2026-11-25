import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from supportflow_ai.adapters.classifiers.ml.provider import MlClassifier
from supportflow_ai.adapters.classifiers.noop import NoOpClassifier
from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier
from supportflow_ai.bootstrap import build_classifier
from supportflow_ai.config import Settings
from supportflow_ai.main import create_app


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [("rule", RuleBasedClassifier), ("noop", NoOpClassifier), ("ml", MlClassifier)],
)
def test_each_configured_provider_is_built(tmp_path, provider, expected_type):
    settings = Settings(
        _env_file=None,
        auth_enabled=False,
        classifier_provider=provider,
        classifier_model_dir=str(tmp_path / "missing"),
    )
    assert isinstance(build_classifier(settings), expected_type)


def test_unknown_provider_name_is_refused_not_silently_noop():
    with pytest.raises(ValueError, match="Unknown classifier provider"):
        build_classifier(SimpleNamespace(classifier_provider="xyz"))


def test_app_starts_with_ml_and_missing_artifact_and_reports_503(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            auth_enabled=False,
            classifier_provider="ml",
            classifier_model_dir=str(tmp_path / "missing"),
        )
    )
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    # Lý do chỉ nằm trong log; body giữ nguyên dạng mà smoke_http.py so khớp.
    assert response.json() == {"status": "degraded", "classifier": "ml"}


def test_sklearn_and_joblib_are_not_imported_at_startup():
    code = (
        "import sys\n"
        "sys.modules['sklearn'] = None\n"
        "sys.modules['joblib'] = None\n"
        "from fastapi.testclient import TestClient\n"
        "from supportflow_ai.config import Settings\n"
        "from supportflow_ai.main import create_app\n"
        "settings = Settings(_env_file=None, auth_enabled=False, classifier_provider='rule')\n"
        "app = create_app(settings)\n"
        "print(TestClient(app).get('/health/live').status_code)\n"
    )
    # Đầu ra mã hóa UTF-8 để không phụ thuộc bảng mã mặc định của Windows (cp1252).
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "200"


def test_lifespan_closes_ml_provider_on_shutdown(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            auth_enabled=False,
            classifier_provider="ml",
            classifier_model_dir=str(tmp_path / "missing"),
        )
    )
    classifier = app.state.classifier
    with TestClient(app):
        assert not classifier._closed
    assert classifier._closed
