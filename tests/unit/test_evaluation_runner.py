import hashlib
import json

import pytest

from evaluation.metrics import (
    bootstrap_macro_f1_interval,
    calibration_report,
    percentile,
    priority_agreement,
    priority_of,
    routing_error_rate,
)
from evaluation.run_classification import (
    MANIFEST_NAME,
    load_routing_map,
    load_samples,
    main,
    verify_manifest,
)

CATEGORIES = ["ACC", "NET", "VPN", "MAIL", "SW", "HW", "PRINT", "ACCESS", "EQUIP", "SEC", "OTHER"]


def _jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                    encoding="utf-8")
    return path


ROWS = [
    {"id": "a", "title": "VPN không kết nối", "description": "AnyConnect lỗi",
     "category": "VPN", "impact": "High", "urgency": "High", "split": "gold"},
    {"id": "b", "title": "Nghi phishing", "description": "Đã bấm link lạ",
     "category": "SEC", "impact": None, "urgency": None, "split": "gold"},
    {"id": "c", "title": "Máy in kẹt giấy", "description": "Printer tầng 2",
     "category": "PRINT", "impact": "Low", "urgency": "Low", "split": "train"},
]


# --- metrics -------------------------------------------------------------------------------

def test_priority_matrix_mirrors_backend():
    assert priority_of("High", "High") == "P1"
    assert priority_of("Medium", "Low") == "P4"
    assert priority_of("Low", "High") == "P3"


def test_priority_agreement_counts_exact_and_one_level_off():
    result = priority_agreement(
        [("High", "High"), ("High", "High"), ("Low", "Low"), (None, "High")],
        [("High", "High"), ("High", "Medium"), (None, "Low"), ("High", "High")],
    )
    assert result == {
        "labeled": 3, "predicted": 2, "coverage": 2 / 3, "exactMatch": 0.5,
        "withinOneLevel": 1.0,
    }


def test_routing_error_ignores_abstentions_and_same_team_confusions():
    teams = {"VPN": "network", "NET": "network", "SEC": "security"}
    result = routing_error_rate(["VPN", "VPN", "SEC", "SEC"], ["NET", "SEC", None, "SEC"], teams)
    assert result == {"answered": 3, "routingErrors": 1, "routingErrorRate": 1 / 3}


def test_routing_map_must_cover_observed_categories():
    with pytest.raises(ValueError):
        routing_error_rate(["VPN"], ["MAIL"], {"VPN": "network"})


def test_calibration_report_ece_and_backend_bands():
    result = calibration_report([0.9, 0.9, 0.5, 0.2], [True, False, True, False])
    # bin 0.9: |0.9-0.5|*2; bin 0.5: |0.5-1|*1; bin 0.2: |0.2-0|*1  -> (0.8+0.5+0.2)/4
    assert result["ece"] == pytest.approx(0.375)
    assert result["bands"] == {"Low": 0.25, "Medium": 0.25, "High": 0.5}


def test_calibration_report_without_scores_reports_none():
    assert calibration_report([], []) == {"scored": 0, "ece": None, "bands": None}


def test_bootstrap_interval_is_deterministic_and_bounded():
    y_true = ["VPN", "SEC"] * 20
    y_pred = ["VPN", "SEC"] * 19 + ["SEC", "VPN"]
    first = bootstrap_macro_f1_interval(y_true, y_pred, labels=["VPN", "SEC"], resamples=200)
    second = bootstrap_macro_f1_interval(y_true, y_pred, labels=["VPN", "SEC"], resamples=200)
    assert first == second
    assert 0.0 <= first["low"] <= first["high"] <= 1.0


def test_percentile_nearest_rank():
    values = [float(v) for v in range(1, 101)]
    assert percentile(values, 50) == 50.0
    assert percentile(values, 95) == 95.0
    assert percentile([3.0], 95) == 3.0


# --- dataset loading -----------------------------------------------------------------------

def test_load_samples_reads_new_format_and_split_filter(tmp_path):
    samples = load_samples(_jsonl(tmp_path / "d.jsonl", ROWS), split="gold")
    assert [s.id for s in samples] == ["a", "b"]
    assert samples[0].gold == {"category": "VPN", "impact": "High", "urgency": "High"}


def test_load_samples_accepts_legacy_gold_category(tmp_path):
    rows = [{"id": "s1", "title": "VPN", "description": "x", "goldCategory": "VPN"}]
    samples = load_samples(_jsonl(tmp_path / "d.jsonl", rows))
    assert samples[0].gold == {"category": "VPN", "impact": None, "urgency": None}


@pytest.mark.parametrize(
    "row",
    [
        {"id": "x", "title": "t", "description": "d", "category": "PRIORITY"},
        {"id": "x", "title": "t", "description": "d", "category": "VPN", "impact": "Critical"},
        {"id": "x", "title": "t", "description": "d"},
        {"title": "t", "description": "d", "category": "VPN"},
    ],
)
def test_load_samples_rejects_bad_rows(tmp_path, row):
    with pytest.raises(ValueError):
        load_samples(_jsonl(tmp_path / "d.jsonl", [row]))


def test_load_samples_rejects_duplicate_ids(tmp_path):
    with pytest.raises(ValueError):
        load_samples(_jsonl(tmp_path / "d.jsonl", [ROWS[0], ROWS[0]]))


def test_manifest_sha_is_verified(tmp_path):
    dataset = _jsonl(tmp_path / "gold.jsonl", ROWS)
    assert verify_manifest(dataset) is None
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    (tmp_path / MANIFEST_NAME).write_text(
        json.dumps({"version": "v1", "files": {"gold.jsonl": {"sha256": digest}}}),
        encoding="utf-8",
    )
    assert verify_manifest(dataset) == {"version": "v1", "verified": True}
    dataset.write_text(dataset.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        verify_manifest(dataset)


def test_routing_map_must_name_every_category(tmp_path):
    path = tmp_path / "routing.json"
    path.write_text(json.dumps({"teams": {"VPN": "network"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_routing_map(path)


# --- end to end ----------------------------------------------------------------------------

def test_runner_reports_three_fields_routing_and_robustness(tmp_path):
    dataset = _jsonl(tmp_path / "gold.jsonl", ROWS)
    routing = tmp_path / "routing.json"
    routing.write_text(
        json.dumps({"source": "test", "version": "0", "teams": {c: c for c in CATEGORIES}}),
        encoding="utf-8",
    )
    output = tmp_path / "out" / "report.json"
    report = main([
        "--dataset", str(dataset), "--routing-map", str(routing), "--robustness",
        "--output", str(output),
    ])

    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["provider"] == "rule"
    assert report["evidenceStatus"] == "unverified-dataset"
    assert report["dataset"]["samples"] == 3
    assert set(report["fields"]) == {"category", "impact", "urgency"}
    assert report["fields"]["impact"]["labeled"] == 2
    # Rule trả score null nên không có số liệu hiệu chỉnh.
    assert report["fields"]["category"]["calibration"]["ece"] is None
    assert report["keyMetrics"]["secRecall"] == 1.0
    assert report["keyMetrics"]["routing"]["answered"] == 3
    assert set(report["robustness"]["stripDiacritics"]) == {"category", "impact", "urgency"}
    assert report["latencyMs"]["p95"] >= report["latencyMs"]["p50"] >= 0


def test_runner_without_routing_map_does_not_invent_one(tmp_path):
    dataset = _jsonl(tmp_path / "gold.jsonl", ROWS)
    report = main(["--dataset", str(dataset), "--output", str(tmp_path / "r.json")])
    assert report["keyMetrics"]["routing"] == {"status": "not-configured"}
    assert "robustness" not in report
