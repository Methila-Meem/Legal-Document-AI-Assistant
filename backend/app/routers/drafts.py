from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    DraftEditRequest,
    DraftEditResponse,
    DraftGenerateRequest,
    DraftGenerateResponse,
    LearnedRule,
)
from app.repositories.documents_repository import (
    fetch_document,
    fetch_draft,
    insert_draft,
    insert_learning_rules,
    insert_operator_edit,
)
from app.services.draft_generation_service import (
    DraftGenerationService,
    LlmResponseError,
    LlmTimeoutError,
    LlmUnavailableError,
    NoEvidenceFoundError,
    UnsupportedDraftTypeError,
)
from app.services.edit_learning_service import EditLearningService
from app.services.embedding_service import EmbeddingModelUnavailableError
from app.services.vector_store_service import VectorStoreError


router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post(
    "/generate",
    response_model=DraftGenerateResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_draft(request: DraftGenerateRequest) -> DraftGenerateResponse:
    try:
        document_id = int(request.document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="document_id must be a valid integer string.",
        ) from exc

    document = await fetch_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    if document.status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document must be indexed before a draft can be generated.",
        )

    service = DraftGenerationService()
    try:
        result = await service.generate_case_fact_summary(
            document_id=document.id,
            draft_type=request.draft_type,
            top_k=request.top_k,
        )
    except UnsupportedDraftTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except NoEvidenceFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No retrieved evidence is available for draft generation.",
        ) from exc
    except LlmUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub Models API key is not configured. Set GITHUB_MODELS_API_KEY in backend/.env.",
        ) from exc
    except LlmTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="GitHub Models request timed out. Try again or increase LLM_TIMEOUT_SECONDS.",
        ) from exc
    except EmbeddingModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model could not be loaded or used.",
        ) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve evidence from ChromaDB.",
        ) from exc
    except LlmResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Draft generation returned an invalid response.",
        ) from exc

    try:
        draft_id = await insert_draft(
            document_id=document.id,
            draft_type=request.draft_type,
            content=result.draft,
            evidence=[item.model_dump() for item in result.evidence],
            model_name=result.model_used,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save generated draft.",
        ) from exc

    return DraftGenerateResponse(
        draft_id=str(draft_id),
        document_id=str(document.id),
        draft_type=request.draft_type,
        draft=result.draft,
        evidence=result.evidence,
        model_used=result.model_used,
        grounding_note=result.grounding_note,
        applied_learning_rules=result.applied_learning_rules,
        learning_rules_warning=result.learning_rules_warning,
    )


@router.post(
    "/{draft_id}/edits",
    response_model=DraftEditResponse,
    status_code=status.HTTP_200_OK,
)
async def save_operator_edit(
    draft_id: str,
    request: DraftEditRequest,
) -> DraftEditResponse:
    try:
        parsed_draft_id = int(draft_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="draft_id must be a valid integer string.",
        ) from exc

    try:
        draft = await fetch_draft(parsed_draft_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load original draft.",
        ) from exc

    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found.",
        )

    learning_service = EditLearningService()
    extraction_result = await learning_service.extract_rules(
        original_draft=draft.content,
        edited_draft=request.edited_draft,
    )

    try:
        edit_id = await insert_operator_edit(
            draft_id=draft.id,
            original_content=draft.content,
            edited_content=request.edited_draft,
            edit_notes=extraction_result.diff_text,
        )
        inserted_rules = await insert_learning_rules(
            source_edit_id=edit_id,
            rules=extraction_result.rules,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save operator edit or learned rules.",
        ) from exc

    learned_rules = [
        LearnedRule(
            rule_id=str(rule["id"]),
            rule_type=str(rule["rule_type"]),
            rule_text=str(rule["rule_text"]),
            example_before=rule.get("example_before"),
            example_after=rule.get("example_after"),
            is_active=True,
        )
        for rule in inserted_rules
    ]

    return DraftEditResponse(
        edit_id=str(edit_id),
        draft_id=str(draft.id),
        learned_rules=learned_rules,
        message="Operator edit saved and reusable rules extracted.",
        warning=extraction_result.warning,
    )
