from __future__ import annotations

import re

from supportflow_ai.domain.classification import Impact, Suggestion, SuggestionField, Urgency

# Rubric E0 theo tài liệu kiến trúc v3.0, mục 9.2 và 9.4. Chỉ có hai quy tắc High được quy định.
# Thiếu tín hiệu thì không gửi gợi ý cho trường đó (v3.0 mục 9.3: không tự gán High).
# Các mức Low và Medium chưa có quy tắc được duyệt nên không được phát ra.

_ORGANIZATION_SCOPE = (
    "toàn công ty",
    "toan cong ty",
    "cả công ty",
    "ca cong ty",
)
_DEPARTMENT_SCOPE = (
    "cả phòng",
    "ca phong",
    "toàn phòng",
    "toan phong",
)
_SERVICE_BLOCKED = (
    "ngừng làm việc",
    "ngung lam viec",
    "không làm việc được",
    "khong lam viec duoc",
    "không truy cập được",
    "khong truy cap duoc",
    "không vào được",
    "khong vao duoc",
    "không mở được",
    "khong mo duoc",
    "không mở đc",
    "khong mo dc",
    "k mở đc",
    "k mo dc",
    "k mở được",
    "k mo duoc",
)
_DEADLINE_TODAY = (
    "sáng nay",
    "sang nay",
    "chiều nay",
    "chieu nay",
    "trưa nay",
    "trua nay",
    "hôm nay",
    "hom nay",
)
_DEADLINE_SOON = ("gấp", "gap", "khẩn", "khan")
_SENSITIVE_SECURITY = (
    "mã độc",
    "ma doc",
    "ransomware",
    "phishing",
    "lộ tài khoản",
    "lo tai khoan",
    "bị hack",
    "bi hack",
    "lộ dữ liệu",
    "lo du lieu",
)


def _mentions(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) for term in terms)


def infer_severity(normalized_text: str) -> tuple[Suggestion, ...]:
    suggestions: list[Suggestion] = []

    affected_wide = _mentions(normalized_text, _ORGANIZATION_SCOPE + _DEPARTMENT_SCOPE)
    if affected_wide:
        suggestions.append(Suggestion(SuggestionField.IMPACT, Impact.HIGH))

    blocked = _mentions(normalized_text, _SERVICE_BLOCKED)
    deadline_near = _mentions(normalized_text, _DEADLINE_TODAY + _DEADLINE_SOON)
    sensitive = _mentions(normalized_text, _SENSITIVE_SECURITY)
    if blocked and (deadline_near or sensitive):
        suggestions.append(Suggestion(SuggestionField.URGENCY, Urgency.HIGH))

    return tuple(suggestions)
