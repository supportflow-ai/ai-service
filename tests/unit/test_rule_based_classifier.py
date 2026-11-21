import pytest

from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier
from supportflow_ai.domain.classification import Category, SuggestionField


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("VPN lỗi", "Cisco AnyConnect cannot connect", Category.VPN),
        ("Mất mạng", "Không truy cập được internet và wifi", Category.NET),
        ("Outlook lỗi", "Không gửi được email", Category.MAIL),
        ("Máy in", "Printer không in được", Category.PRINT),
        ("Nghi phishing", "Người dùng vừa bấm link phishing", Category.SEC),
        ("Server sập", "Máy chủ nội bộ không truy cập được", Category.OTHER),
    ],
)
@pytest.mark.asyncio
async def test_rule_classifier_returns_expected_category(title, description, expected):
    classifier = RuleBasedClassifier()

    result = await classifier.classify(title=title, description=description)

    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.field == SuggestionField.CATEGORY
    assert suggestion.value == expected
    assert suggestion.score is None


@pytest.mark.asyncio
async def test_security_indicator_takes_precedence_over_other_baseline_keywords():
    prediction = await RuleBasedClassifier().classify(
        title="VPN AnyConnect", description="Phishing suspected: wifi internet VPN AnyConnect",
    )
    assert prediction.suggestions[0].value == Category.SEC


@pytest.mark.parametrize(
    ("title", "description"),
    [
        ("Plan review", "Please review the planned update"),
        ("Không rõ", "Yêu cầu chưa có từ khóa phân loại"),
        ("Máy chuyển tiếp", "Dữ liệu được máy chuyển tiếp sang bộ phận khác"),
    ],
)
@pytest.mark.asyncio
async def test_no_keyword_match_abstains_instead_of_guessing_other(title, description):
    prediction = await RuleBasedClassifier().classify(title=title, description=description)

    assert prediction.suggestions == ()
