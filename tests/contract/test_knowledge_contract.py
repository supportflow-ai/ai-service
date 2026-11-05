import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec

from supportflow_ai.api.routes.knowledge import IndexRequest
from supportflow_ai.domain.knowledge import PROFILE

ROOT = Path(__file__).resolve().parents[2] / "contracts/ai/knowledge-index/v1"


def test_knowledge_contract_profile_and_cross_language_fixtures():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for name, checksum in manifest["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == checksum
    assert manifest["profileHash"] == PROFILE.fingerprint
    assert json.loads((ROOT / "profile.json").read_text(encoding="utf-8")) == asdict(PROFILE)
    spec = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    validate_spec(spec)
    fixtures = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    IndexRequest.model_validate(fixtures["request"])
    for kind in ("request", "response"):
        schema = {
            "$ref": "#/components/schemas/Index" + kind.title(),
            "components": spec["components"],
        }
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(fixtures[kind])
