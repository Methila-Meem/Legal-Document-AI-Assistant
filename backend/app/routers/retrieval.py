from fastapi import APIRouter, HTTPException, status

from app.models.schemas import RetrievalQueryRequest, RetrievalQueryResponse
from app.repositories.documents_repository import fetch_document
from app.services.retrieval_service import (
    EmbeddingModelUnavailableError,
    RetrievalService,
    VectorStoreError,
)


router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/query",
    response_model=RetrievalQueryResponse,
    status_code=status.HTTP_200_OK,
)
async def query_retrieval(request: RetrievalQueryRequest) -> RetrievalQueryResponse:
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
            detail="Document must be indexed before retrieval can be queried.",
        )

    service = RetrievalService()
    try:
        result = service.query(
            document_id=document.id,
            query=request.query,
            top_k=request.top_k,
        )
    except EmbeddingModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model could not be loaded or used.",
        ) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to search ChromaDB.",
        ) from exc

    return RetrievalQueryResponse(
        query=result.query,
        document_id=result.document_id,
        evidence=result.evidence,
        message=result.message,
    )
