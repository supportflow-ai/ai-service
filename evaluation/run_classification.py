from __future__ import annotations

import asyncio
import json
from pathlib import Path

from evaluation.metrics import classification_report
from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier
from supportflow_ai.domain.classification import Category, SuggestionField

ROOT = Path(__file__).resolve().parent


async def main() -> None:
    classifier = RuleBasedClassifier()
    rows = [
        json.loads(line)
        for line in (ROOT / "sample-classification.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    y_true: list[str] = []
    y_pred: list[str] = []

    for row in rows:
        prediction = await classifier.classify(
            title=row["title"],
            description=row["description"],
        )
        category = next(
            item.value.value
            for item in prediction.suggestions
            if item.field == SuggestionField.CATEGORY
        )
        y_true.append(row["goldCategory"])
        y_pred.append(category)

    report = classification_report(y_true, y_pred, labels=[category.value for category in Category])
    report["provider"] = classifier.name
    report["dataset"] = "sample-classification.jsonl"
    report["evidenceStatus"] = "smoke-only-not-gold"

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    output = reports / "classification-baseline.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Saved: {output}")


if __name__ == "__main__":
    asyncio.run(main())
