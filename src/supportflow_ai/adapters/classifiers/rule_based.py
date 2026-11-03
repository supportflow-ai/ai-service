from __future__ import annotations

import re
import unicodedata

from supportflow_ai.domain.classification import (
    Category,
    ClassificationPrediction,
    Suggestion,
    SuggestionField,
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


class RuleBasedClassifier:
    """Deterministic keyword baseline.

    This adapter exists to satisfy the project's baseline-comparison requirement.
    It is NOT presented as the final ML model and therefore returns score=None.
    It only suggests category; impact/urgency remain for a later validated model.
    """

    _KEYWORDS: tuple[tuple[Category, tuple[str, ...]], ...] = (
        (
            Category.SEC,
            (
                "phishing",
                "malware",
                "ransomware",
                "virus",
                "mã độc",
                "ma doc",
                "bị hack",
                "bi hack",
                "security incident",
                "an ninh",
                "lộ dữ liệu",
                "lo du lieu",
            ),
        ),
        (
            Category.VPN,
            (
                "vpn",
                "anyconnect",
                "remote access",
                "mạng riêng ảo",
                "mang rieng ao",
            ),
        ),
        (
            Category.PRINT,
            (
                "printer",
                "scanner",
                "máy in",
                "may in",
                "máy quét",
                "may quet",
            ),
        ),
        (
            Category.MAIL,
            (
                "outlook",
                "email",
                "e-mail",
                "mailbox",
                "thư điện tử",
                "thu dien tu",
            ),
        ),
        (
            Category.ACCESS,
            (
                "access denied",
                "permission",
                "phân quyền",
                "phan quyen",
                "quyền truy cập",
                "quyen truy cap",
                "shared folder",
                "sharepoint access",
            ),
        ),
        (
            Category.ACC,
            (
                "password",
                "mật khẩu",
                "mat khau",
                "login",
                "đăng nhập",
                "dang nhap",
                "account locked",
                "tài khoản bị khóa",
                "tai khoan bi khoa",
            ),
        ),
        (
            Category.NET,
            (
                "wifi",
                "wi-fi",
                "internet",
                "network",
                "dns",
                "lan",
                "mất mạng",
                "mat mang",
                "kết nối mạng",
                "ket noi mang",
            ),
        ),
        (
            Category.SW,
            (
                "software",
                "application",
                "install",
                "license",
                "phần mềm",
                "phan mem",
                "cài đặt",
                "cai dat",
            ),
        ),
        (
            Category.HW,
            (
                "hardware",
                "ram",
                "ssd",
                "hard drive",
                "ổ cứng",
                "o cung",
                "bàn phím hỏng",
                "ban phim hong",
                "màn hình hỏng",
                "man hinh hong",
            ),
        ),
        (
            Category.EQUIP,
            (
                "cấp laptop",
                "cap laptop",
                "cấp thiết bị",
                "cap thiet bi",
                "new laptop",
                "new monitor",
                "request equipment",
                "thiết bị mới",
                "thiet bi moi",
            ),
        ),
    )

    @staticmethod
    def _matches(text: str, keyword: str) -> bool:
        term = _normalize(keyword)
        if term in {"lan", "ram", "ssd", "dns", "vpn"}:
            return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None
        return term in text

    @property
    def name(self) -> str:
        return "rule"

    async def classify(self, *, title: str, description: str) -> ClassificationPrediction:
        text = _normalize(f"{title}\n{description}")

        best_category = Category.OTHER
        best_hits = 0

        for category, keywords in self._KEYWORDS:
            hits = sum(1 for keyword in keywords if self._matches(text, keyword))
            # Baseline takes a conservative path for security-indicator tickets.
            # The backend still enforces mandatory manual triage for SEC.
            if category == Category.SEC and hits:
                return ClassificationPrediction(
                    suggestions=(Suggestion(SuggestionField.CATEGORY, Category.SEC),)
                )
            if hits > best_hits:
                best_category = category
                best_hits = hits

        return ClassificationPrediction(
            suggestions=(
                Suggestion(
                    field=SuggestionField.CATEGORY,
                    value=best_category,
                    score=None,
                ),
            )
        )
