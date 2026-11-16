import pytest

from evaluation.metrics import classification_report


def test_fixed_taxonomy_counts_missing_classes_in_macro_f1():
    result = classification_report(["VPN", "VPN"], ["VPN", "VPN"], labels=["VPN", "SEC"])
    assert result["accuracy"] == 1.0
    assert result["macroF1"] == 0.5
    assert result["perClass"]["SEC"]["support"] == 0


def test_abstention_is_wrong_for_accuracy_and_recall_but_not_a_false_positive():
    result = classification_report(
        ["VPN", "SEC", "VPN", "SEC"],
        ["VPN", None, None, "SEC"],
        labels=["VPN", "SEC"],
    )
    assert result["accuracy"] == 0.5
    assert result["coverage"] == 0.5
    assert result["selectiveAccuracy"] == 1.0
    assert result["perClass"]["VPN"]["recall"] == 0.5
    assert result["perClass"]["VPN"]["precision"] == 1.0
    assert result["perClass"]["VPN"]["support"] == 2


def test_neutral_abstention_lowers_coverage_but_not_accuracy():
    result = classification_report(
        ["OTHER", "VPN"],
        [None, "VPN"],
        labels=["OTHER", "VPN"],
        neutral_abstain_labels=frozenset({"OTHER"}),
    )
    assert result["accuracy"] == 1.0
    assert result["coverage"] == 0.5
    assert result["neutralAbstentions"] == 1
    assert result["perClass"]["VPN"]["support"] == 1


def test_all_abstentions_have_no_selective_accuracy():
    result = classification_report(["VPN"], [None], labels=["VPN"])
    assert result["coverage"] == 0.0
    assert result["selectiveAccuracy"] is None


def test_unknown_label_fails_fast():
    with pytest.raises(ValueError):
        classification_report(["INVALID"], ["VPN"], labels=["VPN", "SEC"])


def test_duplicate_taxonomy_labels_rejected():
    with pytest.raises(ValueError):
        classification_report(["VPN"], ["VPN"], labels=["VPN", "VPN"])
