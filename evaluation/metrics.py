from __future__ import annotations


def classification_report(
    y_true: list[str], y_pred: list[str], *, labels: list[str] | None = None
) -> dict:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred lengths differ")
    if not y_true:
        raise ValueError("dataset is empty")

    if labels is not None and len(labels) != len(set(labels)):
        raise ValueError("labels must be unique")
    classes = sorted(set(labels if labels is not None else y_true + y_pred))
    if not set(y_true + y_pred).issubset(classes):
        raise ValueError("an observed label is missing from the label set")

    confusion = {label: {pred: 0 for pred in classes} for label in classes}
    for actual, predicted in zip(y_true, y_pred, strict=True):
        confusion[actual][predicted] += 1

    per_class = {}
    f1_values = []
    for label in classes:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in classes if other != label)
        fn = sum(confusion[label][other] for other in classes if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(confusion[label].values()),
        }
        f1_values.append(f1)

    accuracy = sum(a == p for a, p in zip(y_true, y_pred, strict=True)) / len(y_true)
    return {
        "samples": len(y_true),
        "accuracy": accuracy,
        "macroF1": sum(f1_values) / len(f1_values),
        "perClass": per_class,
        "confusionMatrix": confusion,
    }
