from fastapi import APIRouter, HTTPException, status

from app.models.schemas import DraftGenerateRequest, DraftGenerateResponse
from app.repositories.documents_repository import (
    fetch_active_learning_rules,
    fetch_document,
    insert_draft,
)
from app.services.draft_generation_service import (
    DraftGenerationService,
    LlmResponseError,
    LlmTimeoutError,
    LlmUnavailableError,
    NoEvidenceFoundError,
    UnsupportedDraftTypeError,
)
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

    learning_rules = await fetch_active_learning_rules()
    service = DraftGenerationService()
    try:
        result = await service.generate_case_fact_summary(
            document_id=document.id,
            draft_type=request.draft_type,
            top_k=request.top_k,
            learning_rules=learning_rules,
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
    )
