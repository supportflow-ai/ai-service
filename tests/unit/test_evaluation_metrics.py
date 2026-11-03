import pytest

from evaluation.metrics import classification_report


def test_fixed_taxonomy_counts_missing_classes_in_macro_f1():
    result = classification_report(["VPN", "VPN"], ["VPN", "VPN"], labels=["VPN", "SEC"])
    assert result["accuracy"] == 1.0
    assert result["macroF1"] == 0.5
    assert result["perClass"]["SEC"]["support"] == 0


def test_unknown_label_fails_fast():
    with pytest.raises(ValueError):
        classification_report(["INVALID"], ["VPN"], labels=["VPN", "SEC"])


def test_duplicate_taxonomy_labels_rejected():
    with pytest.raises(ValueError):
        classification_report(["VPN"], ["VPN"], labels=["VPN", "VPN"])
