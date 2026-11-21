import hashlib
import json

import pytest

from supportflow_ai.adapters.classifiers.ml.artifact import (
    MANIFEST_NAME,
    ArtifactError,
    load_manifest,
)
from supportflow_ai.adapters.classifiers.ml.text import PREPROCESSING_VERSION

MODEL_BYTES = b"synthetic-weights"


def _write(tmp_path, **overrides):
    (tmp_path / "model.bin").write_bytes(MODEL_BYTES)
    manifest = {
        "schemaVersion": 1,
        "name": "tfidf-lr",
        "version": "2026.12.1",
        "preprocessingVersion": PREPROCESSING_VERSION,
        "files": {"model.bin": hashlib.sha256(MODEL_BYTES).hexdigest()},
        "thresholds": {"category": 0.6, "impact": 0.5},
        "datasetVersion": "v1",
        "trainingCodeSha": "abc123",
    }
    manifest.update(overrides)
    (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def _code(tmp_path) -> str:
    with pytest.raises(ArtifactError) as raised:
        load_manifest(tmp_path)
    return raised.value.code


def test_valid_manifest_loads_with_verified_files_and_traceable_version(tmp_path):
    manifest = load_manifest(_write(tmp_path))
    assert manifest.model_version == "tfidf-lr@2026.12.1"
    assert manifest.thresholds == {"category": 0.6, "impact": 0.5}
    assert manifest.path("model.bin").read_bytes() == MODEL_BYTES
    assert manifest.dataset_version == "v1"


def test_missing_manifest(tmp_path):
    assert _code(tmp_path) == "artifact_manifest_missing"


def test_sha_mismatch_is_refused(tmp_path):
    _write(tmp_path)
    (tmp_path / "model.bin").write_bytes(b"tampered")
    assert _code(tmp_path) == "artifact_sha_mismatch"


def test_missing_file_is_refused(tmp_path):
    _write(tmp_path)
    (tmp_path / "model.bin").unlink()
    assert _code(tmp_path) == "artifact_file_missing"


@pytest.mark.parametrize(
    "relative", ["../outside.bin", "/etc/passwd", "sub\\model.bin", "", MANIFEST_NAME],
)
def test_paths_outside_model_dir_are_refused(tmp_path, relative):
    _write(tmp_path, files={relative: "0" * 64})
    assert _code(tmp_path) == "artifact_path_invalid"


def test_preprocessing_version_mismatch_is_refused(tmp_path):
    _write(tmp_path, preprocessingVersion="0")
    assert _code(tmp_path) == "artifact_preprocessing_mismatch"


@pytest.mark.parametrize(
    "thresholds",
    [{}, {"priority": 0.5}, {"category": 1.5}, {"category": True}, {"category": "0.5"}],
)
def test_invalid_thresholds_are_refused(tmp_path, thresholds):
    _write(tmp_path, thresholds=thresholds)
    assert _code(tmp_path) == "artifact_thresholds_invalid"


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"schemaVersion": 2}, "artifact_schema_unsupported"),
        ({"name": "Bad Name"}, "artifact_identity_invalid"),
        ({"files": {}}, "artifact_files_invalid"),
        ({"files": {"model.bin": "NOT-HEX"}}, "artifact_sha_invalid"),
        ({"trainingCodeSha": ""}, "artifact_metadata_invalid"),
    ],
)
def test_malformed_manifest_fields(tmp_path, override, code):
    _write(tmp_path, **override)
    assert _code(tmp_path) == code


def test_unlisted_file_cannot_be_opened_through_manifest(tmp_path):
    manifest = load_manifest(_write(tmp_path))
    with pytest.raises(ArtifactError):
        manifest.path("other.bin")
