import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "compare_backend_contract", ROOT / "scripts/compare_backend_contract.py"
)
compare_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(compare_module)

compare = compare_module.compare
diff_values = compare_module.diff_values
sha256 = compare_module.sha256


def _doc(categories: list[str]) -> bytes:
    return json.dumps({"info": {"version": "1.0.0"}, "enum": categories}, indent=2).encode("utf-8")


def _lock_for(data: bytes) -> dict:
    return {"version": "1.0.0", "sha256": sha256(data), "sourceRef": "abc"}


def test_identical_contracts_have_no_problems():
    data = _doc(["ACC", "NET"])
    assert compare(data, data, _lock_for(data)) == []


def test_changed_enum_value_is_reported_with_path():
    local = _doc(["ACC", "NET"])
    remote = _doc(["ACC", "VPN"])
    problems = compare(local, remote, _lock_for(local))
    assert any("$.enum[1]" in problem for problem in problems)
    assert any("Bản byte" in problem for problem in problems)


def test_field_only_on_one_side_is_reported():
    assert diff_values({"a": 1}, {"a": 1, "b": 2}) == ["$.b: chỉ có ở Backend"]
    assert diff_values({"a": 1, "b": 2}, {"a": 1}) == ["$.b: chỉ có ở AI Service"]


def test_type_change_is_reported():
    assert diff_values({"score": 1}, {"score": 1.0}) == ["$.score: kiểu int khác float"]


def test_lock_mismatch_is_reported_even_when_bytes_match():
    data = _doc(["ACC"])
    lock = {"version": "1.0.0", "sha256": "0" * 64, "sourceRef": "abc"}
    problems = compare(data, data, lock)
    assert problems == ["contract.lock.json không khớp file hợp đồng cục bộ"]


def test_unparseable_backend_contract_is_reported():
    data = _doc(["ACC"])
    problems = compare(data, b"not json", _lock_for(data))
    assert any("không đọc được JSON" in problem for problem in problems)


def test_missing_backend_repository_returns_error_code(tmp_path):
    assert compare_module.main(["--backend", str(tmp_path / "missing")]) == 2
