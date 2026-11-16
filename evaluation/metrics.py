from __future__ import annotations


def classification_report(
    y_true: list[str],
    y_pred: list[str | None],
    *,
    labels: list[str] | None = None,
    neutral_abstain_labels: frozenset[str] = frozenset(),
) -> dict:
    """A None prediction is an abstention: wrong, unless its gold label is neutral.

    Neutral abstentions leave accuracy and F1 unchanged but still lower coverage.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred lengths differ")
    if not y_true:
        raise ValueError("dataset is empty")

    if labels is not None and len(labels) != len(set(labels)):
        raise ValueError("labels must be unique")
    predicted = [p for p in y_pred if p is not None]
    classes = sorted(set(labels if labels is not None else y_true + predicted))
    if not set(y_true + predicted).issubset(classes):
        raise ValueError("an observed label is missing from the label set")

    confusion = {label: {pred: 0 for pred in classes} for label in classes}
    abstained = {label: 0 for label in classes}
    neutral_abstentions = 0
    for actual, prediction in zip(y_true, y_pred, strict=True):
        if prediction is not None:
            confusion[actual][prediction] += 1
        elif actual in neutral_abstain_labels:
            neutral_abstentions += 1
        else:
            abstained[actual] += 1

    scored = len(y_true) - neutral_abstentions
    if not scored:
        raise ValueError("no scored samples after neutral abstentions")

    per_class = {}
    f1_values = []
    for label in classes:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in classes if other != label)
        fn = sum(confusion[label][other] for other in classes if other != label) + abstained[label]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(confusion[label].values()) + abstained[label],
        }
        f1_values.append(f1)

    answered = [(a, p) for a, p in zip(y_true, y_pred, strict=True) if p is not None]
    answered_correct = sum(a == p for a, p in answered)
    accuracy = sum(a == p for a, p in zip(y_true, y_pred, strict=True)) / scored
    return {
        "samples": len(y_true),
        "accuracy": accuracy,
        "macroF1": sum(f1_values) / len(f1_values),
        "neutralAbstentions": neutral_abstentions,
        "coverage": len(answered) / len(y_true),
        "selectiveAccuracy": answered_correct / len(answered) if answered else None,
        "perClass": per_class,
        "confusionMatrix": confusion,
    }
