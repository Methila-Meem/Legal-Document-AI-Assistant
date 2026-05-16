from fastapi import APIRouter, HTTPException, status

from app.models.schemas import LearningRuleResponse, LearningRuleUpdateRequest
from app.repositories.documents_repository import (
    fetch_learning_rules,
    update_learning_rule_active,
)


router = APIRouter(prefix="/learning-rules", tags=["learning-rules"])


def _to_response(rule: dict[str, object]) -> LearningRuleResponse:
    return LearningRuleResponse(
        rule_id=str(rule["id"]),
        rule_type=str(rule["rule_type"]),
        rule_text=str(rule["rule_description"]),
        example_before=rule.get("example_before"),
        example_after=rule.get("example_after"),
        is_active=bool(rule["is_active"]),
        source_edit_id=(
            str(rule["source_edit_id"]) if rule.get("source_edit_id") is not None else None
        ),
    )


@router.get("", response_model=list[LearningRuleResponse])
async def list_learning_rules() -> list[LearningRuleResponse]:
    try:
        rules = await fetch_learning_rules()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load learned rules.",
        ) from exc
    return [_to_response(rule) for rule in rules]


@router.patch("/{rule_id}", response_model=LearningRuleResponse)
async def update_learning_rule(
    rule_id: str,
    request: LearningRuleUpdateRequest,
) -> LearningRuleResponse:
    try:
        parsed_rule_id = int(rule_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="rule_id must be a valid integer string.",
        ) from exc

    try:
        rule = await update_learning_rule_active(parsed_rule_id, request.is_active)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update learned rule.",
        ) from exc

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning rule not found.",
        )
    return _to_response(rule)
