import pytest

from supportflow_ai.domain.classification import (
    Category,
    ClassificationPrediction,
    Impact,
    Suggestion,
    SuggestionField,
)


def test_rejects_duplicate_fields():
    with pytest.raises(ValueError):
        ClassificationPrediction(
            suggestions=(
                Suggestion(SuggestionField.CATEGORY, Category.VPN),
                Suggestion(SuggestionField.CATEGORY, Category.NET),
            )
        )


def test_rejects_score_outside_contract_range():
    with pytest.raises(ValueError):
        Suggestion(SuggestionField.CATEGORY, Category.VPN, score=1.1)


def test_rejects_value_type_for_wrong_field():
    with pytest.raises(ValueError):
        Suggestion(SuggestionField.CATEGORY, Impact.HIGH)


def test_api_schema_does_not_coerce_invalid_json_score_types():
    from pydantic import ValidationError

    from supportflow_ai.api.schemas.classification import ClassificationSuggestion

    for invalid_score in (True, False, "0.5"):
        with pytest.raises(ValidationError):
            ClassificationSuggestion.model_validate(
                {"field": "category", "value": "VPN", "score": invalid_score}
            )
    assert ClassificationSuggestion.model_validate(
        {"field": "category", "value": "VPN", "score": 1}
    ).score == 1.0


@pytest.mark.parametrize("revision", [True, False, "1", 1.0, -1])
def test_request_revision_does_not_coerce_invalid_types(revision):
    from pydantic import ValidationError

    from supportflow_ai.api.schemas.classification import ClassificationRequest

    with pytest.raises(ValidationError):
        ClassificationRequest.model_validate({
            "requestId": "00000000-0000-0000-0000-000000000001",
            "ticketId": "00000000-0000-0000-0000-000000000002",
            "ticketRevision": revision,
            "inputHash": "a" * 64,
            "title": "VPN issue",
            "description": "Cannot connect",
        })


@pytest.mark.parametrize("revision", [True, False, "1", 1.0, -1])
def test_response_revision_does_not_coerce_invalid_types(revision):
    from pydantic import ValidationError

    from supportflow_ai.api.schemas.classification import ClassificationResponse

    with pytest.raises(ValidationError):
        ClassificationResponse.model_validate({
            "requestId": "00000000-0000-0000-0000-000000000001",
            "ticketId": "00000000-0000-0000-0000-000000000002",
            "ticketRevision": revision,
            "inputHash": "a" * 64,
            "suggestions": [],
        })
