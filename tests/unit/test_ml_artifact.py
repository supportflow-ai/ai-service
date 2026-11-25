import hashlib
import io
import os

import joblib
import pytest

from supportflow_ai.adapters.classifiers.ml.artifact import (
    ENVIRONMENT_KEYS,
    MANIFEST_NAME,
    ArtifactError,
    load_manifest,
    load_verified_bytes,
)
from tests.unit.ml_artifact_helper import (
    MODEL_FILE,
    manifest_for,
    save_manifest,
    tiny_model_bytes,
    write_artifact,
)


def _code(tmp_path) -> str:
    with pytest.raises(ArtifactError) as raised:
        load_manifest(tmp_path)
    return raised.value.code


@pytest.mark.parametrize("status", ["dev-stub", "candidate"])
def test_valid_manifest_loads_with_traceable_version(tmp_path, status):
    write_artifact(tmp_path, status=status)
    manifest = load_manifest(tmp_path)
    assert manifest.model_version == "tfidf-lr@2026.12.1"
    assert manifest.status == status
    assert manifest.thresholds == {"category": 0.6}
    assert set(manifest.environment) == ENVIRONMENT_KEYS
    assert not manifest.calibrated


def test_calibration_block_marks_manifest_as_calibrated(tmp_path):
    write_artifact(
        tmp_path,
        status="candidate",
        calibration={"method": "sigmoid", "splitOrFolds": "groupkfold-5"},
    )
    assert load_manifest(tmp_path).calibrated


def test_missing_manifest(tmp_path):
    assert _code(tmp_path) == "artifact_manifest_missing"


def test_sha_mismatch_is_refused(tmp_path):
    write_artifact(tmp_path)
    (tmp_path / MODEL_FILE).write_bytes(b"tampered")
    assert _code(tmp_path) == "artifact_sha_mismatch"


def test_missing_file_is_refused(tmp_path):
    write_artifact(tmp_path)
    (tmp_path / MODEL_FILE).unlink()
    assert _code(tmp_path) == "artifact_file_missing"


@pytest.mark.parametrize(
    "relative", ["../outside.joblib", "/etc/passwd", "sub\\model.joblib", "", MANIFEST_NAME],
)
def test_paths_outside_model_dir_are_refused(tmp_path, relative):
    write_artifact(tmp_path, files={relative: "0" * 64})
    assert _code(tmp_path) == "artifact_path_invalid"


def test_preprocessing_version_mismatch_is_refused(tmp_path):
    write_artifact(tmp_path, preprocessingVersion="0")
    assert _code(tmp_path) == "artifact_preprocessing_mismatch"


@pytest.mark.parametrize(
    "thresholds",
    [{}, {"priority": 0.5}, {"category": 1.5}, {"category": True}, {"category": "0.5"},
     {"impact": 0.5}],
)
def test_invalid_thresholds_are_refused(tmp_path, thresholds):
    write_artifact(tmp_path, thresholds=thresholds)
    assert _code(tmp_path) == "artifact_thresholds_invalid"


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"schemaVersion": 1}, "artifact_schema_unsupported"),
        ({"name": "Bad Name"}, "artifact_identity_invalid"),
        ({"status": "production"}, "artifact_status_invalid"),
        ({"files": {}}, "artifact_files_invalid"),
        ({"files": {MODEL_FILE: "NOT-HEX"}}, "artifact_sha_invalid"),
        ({"sourceSha": ""}, "artifact_source_sha_invalid"),
        ({"classificationContractSha256": "abc"}, "artifact_contract_sha_invalid"),
        ({"splitSha256": "x"}, "artifact_split_sha_invalid"),
        ({"guidelineVersion": ""}, "artifact_metadata_invalid"),
        ({"dataset": {"version": "v1", "sha256": "x"}}, "artifact_dataset_invalid"),
        ({"environment": {"python": "3.12"}}, "artifact_environment_invalid"),
        ({"model": {"family": "x", "revision": "n/a", "seed": True}}, "artifact_model_invalid"),
        ({"calibration": {"method": "sigmoid"}}, "artifact_calibration_invalid"),
        ({"calibration": {"method": "sigmoid", "splitOrFolds": ""}},
         "artifact_calibration_invalid"),
        ({"evaluation": {"development": "x"}}, "artifact_evaluation_invalid"),
        ({"unexpectedKey": 1}, "artifact_manifest_invalid"),
    ],
)
def test_malformed_manifest_fields(tmp_path, override, code):
    write_artifact(tmp_path, **override)
    assert _code(tmp_path) == code


@pytest.mark.parametrize("key", sorted(manifest_for(b"")))
def test_manifest_missing_a_required_field_is_refused(tmp_path, key):
    write_artifact(tmp_path)
    manifest = manifest_for(tmp_path.joinpath(MODEL_FILE).read_bytes())
    del manifest[key]
    save_manifest(tmp_path, manifest)
    unsupported = key == "schemaVersion"
    expected = "artifact_schema_unsupported" if unsupported else "artifact_manifest_invalid"
    assert _code(tmp_path) == expected


def test_file_outside_manifest_cannot_be_loaded(tmp_path):
    write_artifact(tmp_path)
    manifest = load_manifest(tmp_path)
    with pytest.raises(ArtifactError) as raised:
        load_verified_bytes(manifest, "other.bin")
    assert raised.value.code == "artifact_file_not_in_manifest"


def test_verified_bytes_are_the_hashed_bytes_and_load_as_model(tmp_path):
    write_artifact(tmp_path)
    manifest = load_manifest(tmp_path)
    data = load_verified_bytes(manifest, MODEL_FILE)
    assert hashlib.sha256(data).hexdigest() == manifest.files[MODEL_FILE]
    model = joblib.load(io.BytesIO(data))
    assert set(model.classes_) == {"VPN", "PRINT", "ACC"}


def test_model_replaced_after_manifest_check_is_not_loaded(tmp_path):
    # TOCTOU: load_manifest băm xong, file bị thay trước khi nạp. Phải bị từ chối.
    write_artifact(tmp_path)
    manifest = load_manifest(tmp_path)
    (tmp_path / MODEL_FILE).write_bytes(tiny_model_bytes() + b"-swapped")
    with pytest.raises(ArtifactError) as raised:
        load_verified_bytes(manifest, MODEL_FILE)
    assert raised.value.code == "artifact_sha_mismatch"


def test_model_deleted_after_manifest_check_is_refused(tmp_path):
    write_artifact(tmp_path)
    manifest = load_manifest(tmp_path)
    (tmp_path / MODEL_FILE).unlink()
    with pytest.raises(ArtifactError) as raised:
        load_verified_bytes(manifest, MODEL_FILE)
    assert raised.value.code == "artifact_file_missing"


@pytest.mark.skipif(
    not hasattr(os, "symlink") or os.name == "nt",
    reason="Windows cần quyền tạo symlink; máy phát triển này không có (WinError 1314). "
           "Test chạy trên CI Linux.",
)
def test_model_replaced_by_symlink_outside_root_is_refused(tmp_path):
    model_dir = tmp_path / "model"
    write_artifact(model_dir)
    outside = tmp_path / "outside.joblib"
    outside.write_bytes(tiny_model_bytes())
    manifest = load_manifest(model_dir)
    (model_dir / MODEL_FILE).unlink()
    os.symlink(outside, model_dir / MODEL_FILE)
    with pytest.raises(ArtifactError) as raised:
        load_verified_bytes(manifest, MODEL_FILE)
    assert raised.value.code == "artifact_path_invalid"
