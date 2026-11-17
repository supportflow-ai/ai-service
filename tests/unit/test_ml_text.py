import unicodedata

import pytest

from supportflow_ai.adapters.classifiers.ml.text import (
    compose_input,
    normalize,
    strip_diacritics,
)


def test_normalize_folds_case_width_and_whitespace():
    assert normalize("  VPN\tKHÔNG   vào\nđược  ") == "vpn không vào được"
    assert normalize("ＶＰＮ") == "vpn"


def test_normalize_unifies_composed_and_decomposed_vietnamese():
    composed = "Không kết nối được mạng"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert normalize(composed) == normalize(decomposed)


def test_strip_diacritics_handles_d_stroke_and_all_tones():
    assert strip_diacritics("đăng nhập Đà Nẵng") == "dang nhap Da Nang"
    assert strip_diacritics("không kết nối được") == "khong ket noi duoc"
    assert strip_diacritics("ữ ỹ ặ ợ") == "u y a o"


def test_compose_input_keeps_title_and_cuts_description_first():
    text = compose_input("VPN lỗi", "mô tả " * 100, max_chars=30)
    assert text.startswith("vpn lỗi\n")
    assert len(text) == 30


def test_compose_input_cuts_title_only_when_title_alone_is_too_long():
    assert compose_input("a" * 50, "mô tả", max_chars=10) == "a" * 10


def test_compose_input_without_description_and_is_deterministic():
    assert compose_input("Máy in", "   ", max_chars=100) == "máy in"
    assert compose_input("X", "y", max_chars=100) == compose_input("X", "y", max_chars=100)


def test_compose_input_rejects_non_positive_limit():
    with pytest.raises(ValueError):
        compose_input("a", "b", max_chars=0)
