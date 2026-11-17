"""Tiền xử lý văn bản dùng chung cho huấn luyện và suy luận (ml-classifier-plan.md mục 4.2, K6).

Huấn luyện và suy luận phải gọi cùng các hàm này để tránh lệch tiền xử lý. Mọi thay đổi hành vi
phải tăng `PREPROCESSING_VERSION`; manifest của artifact ghi phiên bản này và `artifact.py` từ chối
nạp artifact được huấn luyện với phiên bản khác.
"""

from __future__ import annotations

import re
import unicodedata

PREPROCESSING_VERSION = "1"

_WHITESPACE = re.compile(r"\s+")
# NFD không tách "đ" thành "d" + dấu, nên phải ánh xạ riêng.
_D_STROKE = str.maketrans({"đ": "d", "Đ": "D"})


def normalize(text: str) -> str:
    """NFKC, casefold, gộp mọi khoảng trắng thành một dấu cách.

    Dùng NFKC (không phải NFC) để gộp cả ký tự tương thích như chữ full-width; với tiếng Việt,
    NFKC cũng hợp nhất dạng tổ hợp (NFD) và dựng sẵn. Cùng cách chuẩn hóa với rule baseline.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", folded).strip()


def strip_diacritics(text: str) -> str:
    """Bỏ dấu tiếng Việt ("Không kết nối được" -> "Khong ket noi duoc").

    Chỉ dùng để thêm đặc trưng (n-gram ký tự) và kiểm thử độ bền. Không dùng cho từ khóa của rule:
    bỏ dấu làm trùng nghĩa ("gặp" thành "gap", "mạng" thành "mang").
    """
    decomposed = unicodedata.normalize("NFD", text.translate(_D_STROKE))
    kept = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return unicodedata.normalize("NFC", kept)


def compose_input(title: str, description: str, *, max_chars: int) -> str:
    """Ghép tiêu đề và mô tả đã chuẩn hóa, cắt xác định theo số ký tự.

    Giữ đủ tiêu đề và phần đầu mô tả; chỉ cắt tiêu đề khi riêng nó đã vượt `max_chars`.
    Giới hạn token của PhoBERT do tokenizer của adapter xử lý thêm; hàm này là chặn trên chung.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    head = normalize(title)
    body = normalize(description)
    if len(head) >= max_chars:
        return head[:max_chars]
    text = f"{head}\n{body}" if body else head
    return text[:max_chars]
