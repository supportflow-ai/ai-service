import hashlib
import json
from pathlib import Path

from supportflow_ai.adapters.classifiers.ml.contract_pin import CONTRACT_SHA256

ROOT = Path(__file__).resolve().parents[2]


def test_contract_pin_matches_lock_file_and_contract_bytes():
    lock = json.loads((ROOT / "contract.lock.json").read_text(encoding="utf-8"))
    assert lock["path"] == "contracts/ai/v1/openapi.yaml"
    assert lock["sha256"] == CONTRACT_SHA256
    contract_bytes = (ROOT / lock["path"]).read_bytes()
    assert hashlib.sha256(contract_bytes).hexdigest() == CONTRACT_SHA256
