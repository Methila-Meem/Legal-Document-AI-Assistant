from pydantic import BaseModel, ConfigDict


class OcrHealth(BaseModel):
    engine: str
    available: bool
    message: str


class ServicesHealth(BaseModel):
    database: str
    ocr: OcrHealth


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    services: ServicesHealth | None = None


class DocumentPlaceholderResponse(BaseModel):
    message: str
    implemented: bool = False


class DocumentUploadResponse(BaseModel):
    document_id: str
    original_filename: str
    stored_filename: str
    file_type: str
    size_bytes: int
    status: str


class ProcessedPageResponse(BaseModel):
    page_number: int
    source_type: str
    text_preview: str
    ocr_confidence: float | None = None
    is_unclear: bool


class DocumentProcessResponse(BaseModel):
    document_id: str
    status: str
    page_count: int
    pages: list[ProcessedPageResponse]
    warnings: list[str]


class KeyEvent(BaseModel):
    event: str
    date: str | None = None
    source_page: int | None = None


class StructuredFields(BaseModel):
    document_type: str | None = None
    parties: list[str] = []
    dates: list[str] = []
    addresses: list[str] = []
    monetary_amounts: list[str] = []
    case_numbers: list[str] = []
    key_events: list[KeyEvent] = []
    unclear_items: list[str] = []


class StructuredExtractionResponse(BaseModel):
    document_id: str
    structured_fields: StructuredFields
    method: str
    warnings: list[str] = []


class DocumentIndexResponse(BaseModel):
    document_id: str
    status: str
    chunk_count: int
    embedding_model: str
    vector_db: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": [],
            }
        }
    })
