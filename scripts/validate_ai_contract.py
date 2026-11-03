from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/ai/v1/openapi.yaml"


def main() -> None:
    spec = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validate_spec(spec)

    fixtures = json.loads((CONTRACT.parent / "fixtures.json").read_text(encoding="utf-8"))
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

    lock = json.loads((ROOT / "contract.lock.json").read_text(encoding="utf-8"))
    assert lock["version"] == spec["info"]["version"]
    assert lock["sha256"] == hashlib.sha256(CONTRACT.read_bytes()).hexdigest()

    print("OpenAPI 3.1, fixtures and pinned checksum validated.")


if __name__ == "__main__":
    main()
