from __future__ import annotations

import math
import random


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


# Bản sao ma trận PriorityMatrix của Backend (docs/g1-doi-chieu-enum.md), CHỈ dùng để đánh giá
# ngoại tuyến (chỉ số "khớp Priority"). Dịch vụ không tính hay trả Priority; ranh giới này được
# kiểm thử canh: gói supportflow_ai không import evaluation.
PRIORITY_MATRIX: dict[tuple[str, str], str] = {
    ("High", "High"): "P1", ("High", "Medium"): "P2", ("High", "Low"): "P3",
    ("Medium", "High"): "P2", ("Medium", "Medium"): "P3", ("Medium", "Low"): "P4",
    ("Low", "High"): "P3", ("Low", "Medium"): "P4", ("Low", "Low"): "P4",
}
# Ngưỡng dải tin cậy của Backend (ConfidencePolicy): Low < 0,4 <= Medium < 0,75 <= High.
CONFIDENCE_LOW_THRESHOLD = 0.4
CONFIDENCE_HIGH_THRESHOLD = 0.75


def priority_of(impact: str, urgency: str) -> str:
    return PRIORITY_MATRIX[(impact, urgency)]


def priority_agreement(
    gold: list[tuple[str | None, str | None]],
    predicted: list[tuple[str | None, str | None]],
) -> dict:
    """So Priority tính từ gợi ý với Priority tính từ nhãn.

    Chỉ xét mẫu có đủ nhãn Impact và Urgency; mẫu mà mô hình thiếu một trong hai gợi ý thì không
    tính được Priority và chỉ làm giảm `coverage`.
    """
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    labeled = predicted_count = exact = within_one = 0
    for (gold_impact, gold_urgency), (pred_impact, pred_urgency) in zip(
        gold, predicted, strict=True
    ):
        if gold_impact is None or gold_urgency is None:
            continue
        labeled += 1
        if pred_impact is None or pred_urgency is None:
            continue
        predicted_count += 1
        distance = abs(
            int(priority_of(gold_impact, gold_urgency)[1])
            - int(priority_of(pred_impact, pred_urgency)[1])
        )
        exact += distance == 0
        within_one += distance <= 1
    return {
        "labeled": labeled,
        "predicted": predicted_count,
        "coverage": predicted_count / labeled if labeled else None,
        "exactMatch": exact / predicted_count if predicted_count else None,
        "withinOneLevel": within_one / predicted_count if predicted_count else None,
    }


def routing_error_rate(
    y_true: list[str], y_pred: list[str | None], team_of: dict[str, str],
) -> dict:
    """Tỷ lệ gợi ý Category đưa phiếu sang nhóm xử lý khác nhóm của nhãn đúng.

    Abstain không phải lỗi định tuyến (phiếu ở lại hàng đợi phân loại thủ công).
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred lengths differ")
    observed = set(y_true) | {p for p in y_pred if p is not None}
    if not observed <= set(team_of):
        raise ValueError("routing map does not cover every observed category")
    answered = [(a, p) for a, p in zip(y_true, y_pred, strict=True) if p is not None]
    errors = sum(team_of[a] != team_of[p] for a, p in answered)
    return {
        "answered": len(answered),
        "routingErrors": errors,
        "routingErrorRate": errors / len(answered) if answered else None,
    }


def calibration_report(scores: list[float], correct: list[bool], *, bins: int = 10) -> dict:
    """ECE với các bin đều trên [0, 1] và tỷ lệ gợi ý rơi vào từng dải tin cậy của Backend."""
    if len(scores) != len(correct):
        raise ValueError("scores and correct lengths differ")
    if bins < 1:
        raise ValueError("bins must be positive")
    if not scores:
        return {"scored": 0, "ece": None, "bands": None}
    totals = [0] * bins
    confidence_sums = [0.0] * bins
    correct_sums = [0] * bins
    for score, hit in zip(scores, correct, strict=True):
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be in [0, 1]")
        index = min(int(score * bins), bins - 1)
        totals[index] += 1
        confidence_sums[index] += score
        correct_sums[index] += hit
    ece = sum(
        abs(confidence_sums[i] / totals[i] - correct_sums[i] / totals[i]) * totals[i]
        for i in range(bins)
        if totals[i]
    ) / len(scores)
    bands = {"Low": 0, "Medium": 0, "High": 0}
    for score in scores:
        if score < CONFIDENCE_LOW_THRESHOLD:
            bands["Low"] += 1
        elif score < CONFIDENCE_HIGH_THRESHOLD:
            bands["Medium"] += 1
        else:
            bands["High"] += 1
    return {
        "scored": len(scores),
        "ece": ece,
        "bands": {band: count / len(scores) for band, count in bands.items()},
    }


def bootstrap_macro_f1_interval(
    y_true: list[str],
    y_pred: list[str | None],
    *,
    labels: list[str],
    neutral_abstain_labels: frozenset[str] = frozenset(),
    resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    """Khoảng tin cậy bootstrap (percentile) cho Macro-F1; cố định seed để báo cáo tái lập được."""
    if resamples < 1 or not 0.0 < confidence < 1.0:
        raise ValueError("invalid bootstrap parameters")
    rng = random.Random(seed)
    size = len(y_true)
    values: list[float] = []
    for _ in range(resamples):
        picks = [rng.randrange(size) for _ in range(size)]
        try:
            report = classification_report(
                [y_true[i] for i in picks],
                [y_pred[i] for i in picks],
                labels=labels,
                neutral_abstain_labels=neutral_abstain_labels,
            )
        except ValueError:
            continue  # mẫu lặp toàn abstain trung tính: không tính được
        values.append(report["macroF1"])
    if not values:
        return {"resamples": 0, "low": None, "high": None}
    values.sort()
    tail = (1.0 - confidence) / 2
    return {
        "resamples": len(values),
        "confidence": confidence,
        "low": values[int(tail * (len(values) - 1))],
        "high": values[int(round((1.0 - tail) * (len(values) - 1)))],
    }


def percentile(values: list[float], q: float) -> float:
    """Percentile theo nearest-rank (không nội suy), q trong (0, 100]."""
    if not values or not 0.0 < q <= 100.0:
        raise ValueError("values must be non-empty and q in (0, 100]")
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(ordered)))
    return ordered[rank - 1]
