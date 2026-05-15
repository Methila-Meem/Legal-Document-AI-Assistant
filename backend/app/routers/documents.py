from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.schemas import (
    DocumentPlaceholderResponse,
    DocumentProcessResponse,
    DocumentUploadResponse,
    DocumentIndexResponse,
    ProcessedPageResponse,
    StructuredExtractionResponse,
)
from app.repositories.documents_repository import (
    fetch_document,
    fetch_processed_pages,
    insert_document,
    replace_document_pages,
    save_structured_fields,
    update_document_status,
)
from app.services.document_processing_service import (
    DocumentProcessingError,
    DocumentProcessingService,
    OcrEngineMissingError,
    OcrProcessingError,
    UnsupportedDocumentTypeError,
)
from app.services.storage_service import save_upload_file
from app.services.structured_extraction_service import StructuredExtractionService
from app.services.indexing_service import (
    EmbeddingModelUnavailableError,
    EmptyExtractedTextError,
    IndexingService,
    VectorStoreError,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "",
    response_model=DocumentPlaceholderResponse,
    status_code=status.HTTP_200_OK,
)
async def documents_placeholder() -> DocumentPlaceholderResponse:
    return DocumentPlaceholderResponse(
        message="Document listing will be implemented in a later phase."
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    try:
        stored_upload = await save_upload_file(file)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store uploaded file.",
        ) from exc

    try:
        document = await insert_document(
            original_filename=stored_upload.original_filename,
            stored_filename=stored_upload.stored_filename,
            content_type=stored_upload.content_type,
            file_size_bytes=stored_upload.size_bytes,
        )
    except Exception as exc:
        stored_upload.path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save document metadata.",
        ) from exc

    return DocumentUploadResponse(
        document_id=str(document.id),
        original_filename=document.original_filename,
        stored_filename=document.stored_filename,
        file_type=stored_upload.file_type,
        size_bytes=document.file_size_bytes,
        status=document.status,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    status_code=status.HTTP_200_OK,
)
async def process_document(document_id: int) -> DocumentProcessResponse:
    document = await fetch_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    service = DocumentProcessingService()
    try:
        result = service.process(document)
        await replace_document_pages(
            document.id,
            [
                {
                    "page_number": page.page_number,
                    "text": page.text,
                    "source_type": page.source_type,
                    "ocr_confidence": page.ocr_confidence,
                    "is_unclear": page.is_unclear,
                }
                for page in result.pages
            ],
        )
        await update_document_status(document.id, "processed")
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except OcrEngineMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "PaddleOCR is unavailable. Install paddleocr and paddlepaddle; "
                "the first OCR request may download model weights."
            ),
        ) from exc
    except OcrProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR failed while processing the document.",
        ) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save document processing results.",
        ) from exc

    return DocumentProcessResponse(
        document_id=result.document_id,
        status=result.status,
        page_count=result.page_count,
        pages=[
            ProcessedPageResponse(
                page_number=page.page_number,
                source_type=page.source_type,
                text_preview=page.text_preview,
                ocr_confidence=page.ocr_confidence,
                is_unclear=page.is_unclear,
            )
            for page in result.pages
        ],
        warnings=result.warnings,
    )


@router.post(
    "/{document_id}/extract-fields",
    response_model=StructuredExtractionResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_document_fields(document_id: int) -> StructuredExtractionResponse:
    document = await fetch_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.status not in {"processed", "indexed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document must be processed before structured fields can be extracted.",
        )

    pages = await fetch_processed_pages(document.id)
    if not pages:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No processed page text is available for this document.",
        )

    extraction_service = StructuredExtractionService()
    result = await extraction_service.extract(pages)
    await save_structured_fields(
        document_id=document.id,
        structured_fields=result.fields.model_dump(),
        method=result.method,
        warnings=result.warnings,
    )

    return StructuredExtractionResponse(
        document_id=str(document.id),
        structured_fields=result.fields,
        method=result.method,
        warnings=result.warnings,
    )


@router.post(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    status_code=status.HTTP_200_OK,
)
async def index_document(document_id: int) -> DocumentIndexResponse:
    document = await fetch_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.status not in {"processed", "indexed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document must be processed before it can be indexed.",
        )

    indexing_service = IndexingService()
    try:
        result = await indexing_service.index_document(document)
    except EmptyExtractedTextError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No extracted text is available for indexing.",
        ) from exc
    except EmbeddingModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model could not be loaded or used.",
        ) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to write document chunks to ChromaDB.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document indexing failed.",
        ) from exc

    return DocumentIndexResponse(
        document_id=result.document_id,
        status=result.status,
        chunk_count=result.chunk_count,
        embedding_model=result.embedding_model,
        vector_db=result.vector_db,
    )
