import pytest

from supportflow_ai.adapters.classifiers.rule_based import RuleBasedClassifier, _normalize
from supportflow_ai.adapters.classifiers.severity_rules import infer_severity
from supportflow_ai.domain.classification import Category, Impact, SuggestionField, Urgency


def _severity(text: str) -> set:
    return {(s.field, s.value) for s in infer_severity(_normalize(text))}


def _fields(text: str) -> set:
    return {field for field, _ in _severity(text)}


@pytest.mark.parametrize(
    "text",
    [
        "Cả phòng kế toán không làm việc được từ 8 giờ",
        "Toàn công ty không truy cập được hệ thống",
        "Toan cong ty khong vao duoc mail",
    ],
)
def test_department_or_organization_scope_gives_impact_high(text):
    assert (SuggestionField.IMPACT, Impact.HIGH) in _severity(text)


@pytest.mark.parametrize(
    "text",
    [
        "Máy của em bị lỗi",
        "Một nhóm nhỏ chậm một chút",
        "Chào anh chị, máy bị lỗi rồi",
    ],
)
def test_missing_scope_signal_gives_no_impact(text):
    assert SuggestionField.IMPACT not in _fields(text)


def test_blocked_with_today_deadline_gives_urgency_high():
    assert (SuggestionField.URGENCY, Urgency.HIGH) in _severity(
        "Máy tính k mở đc, sáng nay có họp gấp"
    )


def test_blocked_with_sensitive_security_gives_urgency_high():
    assert (SuggestionField.URGENCY, Urgency.HIGH) in _severity(
        "Không truy cập được, nghi máy bị mã độc"
    )


def test_blocked_without_deadline_or_sensitive_gives_no_urgency():
    assert SuggestionField.URGENCY not in _fields("Không truy cập được hệ thống từ hôm qua")


def test_sensitive_without_blocked_gives_no_urgency():
    assert SuggestionField.URGENCY not in _fields("Nghi lộ tài khoản qua email lạ")


@pytest.mark.asyncio
async def test_server_outage_ticket_is_other_without_impact_or_urgency():
    result = await RuleBasedClassifier().classify(
        title="Server ứng dụng bị sập",
        description="Nhiều người không truy cập",
    )
    values = {(s.field, s.value) for s in result.suggestions}
    assert values == {(SuggestionField.CATEGORY, Category.OTHER)}


@pytest.mark.asyncio
async def test_full_classifier_emits_category_and_severity_together():
    result = await RuleBasedClassifier().classify(
        title="Cả phòng kế toán không truy cập được VPN",
        description="Cisco AnyConnect báo lỗi, sáng nay phải nộp báo cáo",
    )
    values = {(s.field, s.value) for s in result.suggestions}
    assert (SuggestionField.CATEGORY, Category.VPN) in values
    assert (SuggestionField.IMPACT, Impact.HIGH) in values
    assert (SuggestionField.URGENCY, Urgency.HIGH) in values
    assert len(result.suggestions) <= 3
    assert all(s.score is None for s in result.suggestions)


@pytest.mark.asyncio
async def test_vague_ticket_yields_no_suggestions_at_all():
    result = await RuleBasedClassifier().classify(
        title="Chào anh chị",
        description="Máy bị lỗi rồi",
    )
    assert result.suggestions == ()
