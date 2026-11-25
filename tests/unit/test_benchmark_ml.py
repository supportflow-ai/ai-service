import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_ml.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("benchmark_ml", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_percentile_uses_nearest_rank():
    percentile = _load_script().percentile
    values = [float(v) for v in range(1, 21)]
    assert percentile(values, 50) == 10.0
    assert percentile(values, 95) == 19.0
    assert percentile([7.0], 95) == 7.0


def test_percentile_rejects_empty_input():
    with pytest.raises(ValueError):
        _load_script().percentile([], 50)
