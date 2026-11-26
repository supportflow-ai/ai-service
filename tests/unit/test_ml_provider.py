import io
import pickle
import sys
import types

import joblib
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from supportflow_ai.adapters.classifiers.ml.provider import MODEL_FILE, MlClassifier
from supportflow_ai.adapters.classifiers.ml.text import model_input
from supportflow_ai.domain.classification import Impact, SuggestionField
from supportflow_ai.domain.errors import ProviderUnavailableError
from tests.unit.ml_artifact_helper import (
    TRAINING_PAIRS,
    build_model_bytes,
    capture_logs,
    manifest_for,
    write_artifact,
)

PROVIDER_LOGGER = "supportflow_ai.adapters.classifiers.ml.provider"
TITLE = "vpn không kết nối được"


@pytest.fixture
def make_provider():
    created: list[MlClassifier] = []

    def _make(model_dir, *, allow_dev_stub: bool = False) -> MlClassifier:
        provider = MlClassifier(
            model_dir=str(model_dir) if model_dir is not None else None,
            allow_dev_stub=allow_dev_stub,
            max_concurrency=1,
            max_queue=0,
            queue_timeout_s=2.0,
        )
        created.append(provider)
        return provider

    yield _make
    for provider in created:
        provider.close()


def _refused(tmp_path, make_provider, reason: str, **kwargs) -> None:
    with capture_logs(PROVIDER_LOGGER) as logs:
        provider = make_provider(tmp_path, **kwargs)
    assert not provider.ready
    assert f"ml_provider_not_ready reason={reason}" in logs.messages()


async def test_candidate_artifact_is_ready_and_suggests_category(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate", thresholds={"category": 0.0})
    provider = make_provider(tmp_path)
    assert provider.ready
    assert provider.model_version == "tfidf-lr@2026.12.1"
    prediction = await provider.classify(title=TITLE, description="")
    (suggestion,) = prediction.suggestions
    assert suggestion.field is SuggestionField.CATEGORY
    assert suggestion.value.value in {"VPN", "PRINT", "ACC"}
    assert suggestion.score is None  # candidate không có calibration: không phát điểm


async def test_dev_stub_is_refused_without_flag(tmp_path, make_provider):
    write_artifact(tmp_path)
    _refused(tmp_path, make_provider, "dev_stub_not_allowed", allow_dev_stub=False)


async def test_dev_stub_with_flag_is_ready_and_never_returns_score(tmp_path, make_provider):
    write_artifact(
        tmp_path,
        model_bytes=build_model_bytes(calibrated=True),
        calibrated=True,
        thresholds={"category": 0.0},
    )
    provider = make_provider(tmp_path, allow_dev_stub=True)
    assert provider.ready
    prediction = await provider.classify(title=TITLE, description="")
    assert prediction.suggestions[0].score is None


async def test_calibrated_candidate_returns_probability_as_score(tmp_path, make_provider):
    data = build_model_bytes(calibrated=True)
    write_artifact(
        tmp_path, model_bytes=data, status="candidate", calibrated=True,
        thresholds={"category": 0.0},
    )
    provider = make_provider(tmp_path)
    prediction = await provider.classify(title=TITLE, description="")
    expected = joblib.load(io.BytesIO(data)).predict_proba([model_input(TITLE, "")])[0].max()
    assert prediction.suggestions[0].score == pytest.approx(float(expected))


async def test_score_below_threshold_abstains_with_empty_suggestions(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate", thresholds={"category": 0.999})
    provider = make_provider(tmp_path)
    assert provider.ready
    prediction = await provider.classify(title=TITLE, description="")
    assert prediction.suggestions == ()


SEVERE_TITLE = "cả phòng không truy cập được hệ thống"


async def test_high_impact_is_added_next_to_category_with_null_score(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate", thresholds={"category": 0.0})
    provider = make_provider(tmp_path)
    prediction = await provider.classify(title=SEVERE_TITLE, description="")
    by_field = {s.field: s for s in prediction.suggestions}
    assert by_field[SuggestionField.CATEGORY].score is None
    assert by_field[SuggestionField.IMPACT].value == Impact.HIGH
    assert by_field[SuggestionField.IMPACT].score is None
    assert SuggestionField.URGENCY not in by_field  # không có tín hiệu thời hạn


async def test_high_impact_survives_category_abstention(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate", thresholds={"category": 0.999})
    provider = make_provider(tmp_path)
    prediction = await provider.classify(title=SEVERE_TITLE, description="")
    assert [(s.field, s.value) for s in prediction.suggestions] == [
        (SuggestionField.IMPACT, Impact.HIGH),
    ]


def test_tampered_model_is_refused_by_hash_check(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate")
    (tmp_path / MODEL_FILE).write_bytes(b"tampered-model-bytes")
    _refused(tmp_path, make_provider, "artifact_sha_mismatch")


def test_contract_hash_mismatch_is_refused(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate", classificationContractSha256="0" * 64)
    _refused(tmp_path, make_provider, "contract_sha_mismatch")


@pytest.mark.parametrize("package", ["sklearn", "numpy", "joblib"])
def test_package_version_mismatch_is_refused(tmp_path, make_provider, package):
    environment = dict(manifest_for(b"")["environment"])
    environment[package] = "0.0.0"
    write_artifact(tmp_path, status="candidate", environment=environment)
    _refused(tmp_path, make_provider, "environment_mismatch")


@pytest.mark.parametrize("python", ["3.11.9", "3.13.0"])
def test_python_major_minor_mismatch_is_refused(tmp_path, make_provider, python):
    environment = dict(manifest_for(b"")["environment"])
    environment["python"] = python
    write_artifact(tmp_path, status="candidate", environment=environment)
    _refused(tmp_path, make_provider, "environment_mismatch")


def test_python_patch_difference_is_accepted(tmp_path, make_provider):
    environment = dict(manifest_for(b"")["environment"])
    environment["python"] = f"{sys.version_info[0]}.{sys.version_info[1]}.99"
    write_artifact(tmp_path, status="candidate", environment=environment)
    assert make_provider(tmp_path).ready


def test_label_outside_taxonomy_is_refused(tmp_path, make_provider):
    pairs = (*TRAINING_PAIRS, ("hóa đơn lạ", "FOO"))
    write_artifact(tmp_path, model_bytes=build_model_bytes(pairs), status="candidate")
    _refused(tmp_path, make_provider, "model_label_invalid")


def test_model_without_predict_proba_is_refused(tmp_path, make_provider):
    write_artifact(
        tmp_path, model_bytes=build_model_bytes(estimator="hinge"), status="candidate",
    )
    _refused(tmp_path, make_provider, "model_interface_invalid")


def test_pickled_class_from_module_absent_at_runtime_is_not_loaded(tmp_path, make_provider):
    # Mô phỏng lớp tự viết của bước huấn luyện: module không có trong môi trường chạy.
    module = types.ModuleType("ml_training_only_module")
    sys.modules[module.__name__] = module
    try:
        custom = type("CustomTransformer", (), {"__module__": module.__name__})
        module.CustomTransformer = custom
        buffer = io.BytesIO()
        joblib.dump(Pipeline([("custom", custom())]), buffer)
    finally:
        del sys.modules[module.__name__]
    write_artifact(tmp_path, model_bytes=buffer.getvalue(), status="candidate")
    _refused(tmp_path, make_provider, "model_load_failed")


def test_lambda_pipeline_cannot_be_serialized(tmp_path):
    # Phía sản xuất: pickle lambda không được tạo ra, nên artifact không thể chứa lambda.
    pipeline = Pipeline([("fn", FunctionTransformer(lambda x: x))])
    with pytest.raises(pickle.PicklingError, match="<lambda>"):
        joblib.dump(pipeline, io.BytesIO())


async def test_classify_when_not_ready_raises_controlled_unavailable(tmp_path, make_provider):
    provider = make_provider(tmp_path / "missing")
    assert not provider.ready
    with pytest.raises(ProviderUnavailableError, match="classification_provider_not_ready"):
        await provider.classify(title=TITLE, description="")


async def test_classify_after_close_is_refused(tmp_path, make_provider):
    write_artifact(tmp_path, status="candidate")
    provider = make_provider(tmp_path)
    provider.close()
    with pytest.raises(ProviderUnavailableError, match="classification_provider_not_ready"):
        await provider.classify(title=TITLE, description="")
