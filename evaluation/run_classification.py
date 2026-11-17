"""Đánh giá provider phân loại trên một bộ dữ liệu JSONL (ml-classifier-plan.md mục 7, PR D4).

Chạy không tham số (CI, `make baseline`): provider `rule` trên dữ liệu smoke, ghi
`evaluation/reports/classification-baseline.json`.

    python -m evaluation.run_classification \
        --provider rule --dataset evaluation/data/v1/gold.jsonl --split gold \
        --routing-map evaluation/data/routing-map.json --robustness \
        --output evaluation/reports/rule-gold-v1.json

Định dạng dữ liệu và MANIFEST.json: xem evaluation/DATASET.md.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from evaluation.metrics import (
    bootstrap_macro_f1_interval,
    calibration_report,
    classification_report,
    percentile,
    priority_agreement,
    routing_error_rate,
)
from supportflow_ai.adapters.classifiers.ml.text import strip_diacritics
from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier
from supportflow_ai.domain.classification import Category, Impact, SuggestionField, Urgency
from supportflow_ai.ports.classifier import TicketClassifier

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "sample-classification.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "classification-baseline.json"
MANIFEST_NAME = "MANIFEST.json"
BOOTSTRAP_MIN_SAMPLES = 300

# Provider ML được thêm vào đây cùng adapter của nó (mốc M3).
PROVIDERS: dict[str, Callable[[], TicketClassifier]] = {"rule": RuleBasedClassifier}

FIELD_LABELS: dict[str, list[str]] = {
    "category": [item.value for item in Category],
    "impact": [item.value for item in Impact],
    "urgency": [item.value for item in Urgency],
}
# OTHER nghĩa là "không đủ thông tin" trong taxonomy: abstain trên nó không tính là sai.
NEUTRAL_ABSTAIN = {"category": frozenset({Category.OTHER.value})}
FIELDS = tuple(FIELD_LABELS)


@dataclass(frozen=True, slots=True)
class Sample:
    id: str
    title: str
    description: str
    gold: dict[str, str | None]


@dataclass(frozen=True, slots=True)
class Prediction:
    values: dict[str, str | None]
    scores: dict[str, float | None]
    latency_ms: float


def load_samples(path: Path, *, split: str | None = None) -> list[Sample]:
    samples: list[Sample] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if split is not None and row.get("split") != split:
            continue
        sample_id = row.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError(f"line {number}: missing or duplicate id")
        seen.add(sample_id)
        # `goldCategory` là tên trường của dữ liệu smoke cũ.
        gold = {
            "category": row.get("category", row.get("goldCategory")),
            "impact": row.get("impact"),
            "urgency": row.get("urgency"),
        }
        if gold["category"] is None:
            raise ValueError(f"line {number}: category is required")
        for field, value in gold.items():
            if value is not None and value not in FIELD_LABELS[field]:
                raise ValueError(f"line {number}: unknown {field} label")
        title, description = row.get("title"), row.get("description")
        if not isinstance(title, str) or not isinstance(description, str) or not title.strip():
            raise ValueError(f"line {number}: title and description must be text")
        samples.append(Sample(sample_id, title, description, gold))
    if not samples:
        raise ValueError("dataset is empty after filtering")
    return samples


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(dataset: Path) -> dict | None:
    """Kiểm SHA của file dữ liệu theo MANIFEST.json cùng thư mục (nếu có)."""
    manifest_path = dataset.parent / MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest.get("files", {}).get(dataset.name)
    if not isinstance(entry, dict) or "sha256" not in entry:
        raise ValueError(f"{MANIFEST_NAME} does not list {dataset.name}")
    if entry["sha256"] != sha256_file(dataset):
        raise ValueError(f"{dataset.name} does not match the sha256 in {MANIFEST_NAME}")
    return {"version": manifest.get("version"), "verified": True}


def load_routing_map(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    teams = data.get("teams")
    if not isinstance(teams, dict) or set(teams) != set(FIELD_LABELS["category"]):
        raise ValueError("routing map must assign a team to every category")
    return {"source": data.get("source"), "version": data.get("version"), "teams": teams}


def code_revision() -> dict | None:
    repo = ROOT.parent
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return {"commit": commit, "dirty": bool(dirty)}


async def predict(
    classifier: TicketClassifier,
    samples: list[Sample],
    transform: Callable[[str], str] = lambda text: text,
) -> list[Prediction]:
    predictions: list[Prediction] = []
    for sample in samples:
        started = perf_counter()
        prediction = await classifier.classify(
            title=transform(sample.title), description=transform(sample.description),
        )
        latency_ms = (perf_counter() - started) * 1000
        values: dict[str, str | None] = dict.fromkeys(FIELDS)
        scores: dict[str, float | None] = dict.fromkeys(FIELDS)
        for item in prediction.suggestions:
            field = SuggestionField(item.field).value
            values[field] = item.value.value
            scores[field] = item.score
        predictions.append(Prediction(values, scores, latency_ms))
    return predictions


def evaluate_field(field: str, samples: list[Sample], predictions: list[Prediction]) -> dict:
    pairs = [
        (sample.gold[field], prediction)
        for sample, prediction in zip(samples, predictions, strict=True)
        if sample.gold[field] is not None
    ]
    if not pairs:
        return {"labeled": 0}
    y_true = [gold for gold, _ in pairs]
    y_pred = [prediction.values[field] for _, prediction in pairs]
    neutral = NEUTRAL_ABSTAIN.get(field, frozenset())
    report = classification_report(
        y_true, y_pred, labels=FIELD_LABELS[field], neutral_abstain_labels=neutral,
    )
    report["labeled"] = len(pairs)
    scored = [
        (prediction.scores[field], gold == prediction.values[field])
        for gold, prediction in pairs
        if prediction.values[field] is not None and prediction.scores[field] is not None
    ]
    report["calibration"] = calibration_report(
        [score for score, _ in scored], [hit for _, hit in scored],
    )
    if len(pairs) >= BOOTSTRAP_MIN_SAMPLES:
        report["macroF1Interval"] = bootstrap_macro_f1_interval(
            y_true, y_pred, labels=FIELD_LABELS[field], neutral_abstain_labels=neutral,
        )
    return report


def evaluate(
    samples: list[Sample], predictions: list[Prediction], routing: dict | None,
) -> dict:
    fields = {field: evaluate_field(field, samples, predictions) for field in FIELDS}
    key = {
        "categoryMacroF1": fields["category"]["macroF1"],
        "secRecall": fields["category"]["perClass"]["SEC"]["recall"],
        "impactHighRecall": _high_recall(fields["impact"]),
        "urgencyHighRecall": _high_recall(fields["urgency"]),
        "priority": priority_agreement(
            [(s.gold["impact"], s.gold["urgency"]) for s in samples],
            [(p.values["impact"], p.values["urgency"]) for p in predictions],
        ),
    }
    if routing is None:
        # Backend chưa có RoutingRule (ADR-016, B2): không tự đặt bảng định tuyến.
        key["routing"] = {"status": "not-configured"}
    else:
        key["routing"] = {
            "source": routing["source"],
            "version": routing["version"],
            **routing_error_rate(
                [s.gold["category"] for s in samples],
                [p.values["category"] for p in predictions],
                routing["teams"],
            ),
        }
    return {"fields": fields, "keyMetrics": key}


def _high_recall(report: dict) -> float | None:
    if not report.get("labeled") or not report["perClass"]["High"]["support"]:
        return None
    return report["perClass"]["High"]["recall"]


def _evidence_status(dataset: Path, manifest: dict | None) -> str:
    if dataset.resolve() == DEFAULT_DATASET.resolve():
        return "smoke-only-not-gold"
    return "manifest-verified" if manifest else "unverified-dataset"


async def run(args: argparse.Namespace) -> dict:
    dataset = Path(args.dataset)
    manifest = verify_manifest(dataset)
    samples = load_samples(dataset, split=args.split)
    routing = load_routing_map(Path(args.routing_map)) if args.routing_map else None
    classifier = PROVIDERS[args.provider]()

    predictions = await predict(classifier, samples)
    report: dict = {
        "provider": classifier.name,
        "modelVersion": classifier.model_version,
        "dataset": {
            "path": dataset.name,
            "sha256": sha256_file(dataset),
            "manifest": manifest,
            "split": args.split,
            "samples": len(samples),
        },
        "evidenceStatus": _evidence_status(dataset, manifest),
        "code": code_revision(),
        **evaluate(samples, predictions, routing),
    }
    latencies = [prediction.latency_ms for prediction in predictions]
    report["latencyMs"] = {
        "scope": "in-process classify() call, excludes HTTP; measure in the container for SLOs",
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "max": max(latencies),
    }
    if args.robustness:
        stripped = evaluate(samples, await predict(classifier, samples, strip_diacritics), None)
        report["robustness"] = {
            "stripDiacritics": {
                field: _robustness_delta(report["fields"][field], stripped["fields"][field])
                for field in FIELDS
            }
        }
    return report


def _robustness_delta(original: dict, variant: dict) -> dict | None:
    if not original.get("labeled"):
        return None
    return {
        "macroF1": variant["macroF1"],
        "macroF1Delta": variant["macroF1"] - original["macroF1"],
        "coverage": variant["coverage"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="rule")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--split", help="chỉ đánh giá các dòng có trường split bằng giá trị này")
    parser.add_argument("--routing-map", help="JSON ánh xạ Category -> SupportTeam")
    parser.add_argument(
        "--robustness", action="store_true", help="chạy lại trên bản bỏ dấu, báo mức giảm",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    report = asyncio.run(run(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Console Windows (cp1252) không mã hóa được tiếng Việt, kể cả trong đường dẫn: thay ký tự
    # thay vì dừng tiến trình. File báo cáo vẫn ghi UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Saved: {output}")
    return report


if __name__ == "__main__":
    main()
