from supportflow_ai.adapters.classifiers.ml.text import (
    MODEL_INPUT_MAX_CHARS,
    PREPROCESSING_VERSION,
    model_input,
)


def test_preprocessing_version_is_fixed_for_this_format():
    # Đổi định dạng model_input bắt buộc tăng phiên bản này; test này nhắc việc đó.
    assert PREPROCESSING_VERSION == "1"


def test_accented_title_is_kept_and_stripped_copy_appended():
    assert model_input("VPN không kết nối được", "") == (
        "vpn không kết nối được\nvpn khong ket noi duoc"
    )


def test_d_stroke_is_mapped_to_plain_d_in_stripped_copy():
    assert model_input("Đăng nhập lỗi", "") == "đăng nhập lỗi\ndang nhap loi"


def test_unaccented_text_is_duplicated_unchanged():
    assert model_input("may in khong in duoc", "") == "may in khong in duoc\nmay in khong in duoc"


def test_title_and_description_are_joined_before_stripping():
    assert model_input("VPN lỗi", "mô tả") == "vpn lỗi\nmô tả\nvpn loi\nmo ta"


def test_empty_input_gives_empty_string():
    assert model_input("   ", "   ") == ""


def test_long_input_is_cut_deterministically_before_stripping():
    text = model_input("a" * 3000, "b" * 3000)
    assert text == "a" * MODEL_INPUT_MAX_CHARS + "\n" + "a" * MODEL_INPUT_MAX_CHARS
