import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec

ROOT = Path(__file__).resolve().parents[2]


def test_pinned_contract_and_fixtures_are_valid():
    contract_path = ROOT / "contracts/ai/v1/openapi.yaml"
    spec = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_spec(spec)

    lock = json.loads((ROOT / "contract.lock.json").read_text(encoding="utf-8"))
    assert lock["version"] == spec["info"]["version"]
    assert lock["sha256"] == hashlib.sha256(contract_path.read_bytes()).hexdigest()

    fixtures = json.loads(
        (ROOT / "contracts/ai/v1/fixtures.json").read_text(encoding="utf-8")
    )
    for case in fixtures:
        schema = {
            "$ref": "#/components/schemas/Classification" + case["kind"].title(),
            "components": spec["components"],
        }
        errors = list(
            Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            ).iter_errors(case["payload"])
        )
        assert (not errors) == case["valid"], case.get("name", case["kind"])
