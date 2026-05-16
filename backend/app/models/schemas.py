from pydantic import BaseModel, ConfigDict, Field, field_validator


class OcrHealth(BaseModel):
    selected_engine: str
    available: bool
    active_engine: str | None = None
    fallback_engine: str | None = None
    error_message: str | None = None
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
    ocr_engine: str | None = None
    is_unclear: bool
    warnings: list[str] = []


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


class RetrievalQueryRequest(BaseModel):
    document_id: str
    query: str = Field(min_length=1)
    top_k: int = Field(default=6, ge=1, le=20)

    @field_validator("document_id", "query")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be empty.")
        return cleaned


class EvidenceSource(BaseModel):
    filename: str
    source_type: str
    ocr_confidence: float | None = None


class EvidenceChunk(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int
    text: str
    relevance_score: float
    source: EvidenceSource


class RetrievalQueryResponse(BaseModel):
    query: str
    document_id: str
    evidence: list[EvidenceChunk]
    message: str | None = None


class DraftGenerateRequest(BaseModel):
    document_id: str
    draft_type: str = Field(default="case_fact_summary")
    top_k: int = Field(default=8, ge=1, le=20)

    @field_validator("document_id", "draft_type")
    @classmethod
    def require_non_empty_draft_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be empty.")
        return cleaned


class LearnedRule(BaseModel):
    rule_id: str | None = None
    rule_type: str
    rule_text: str
    example_before: str | None = None
    example_after: str | None = None
    is_active: bool = True


class DraftGenerateResponse(BaseModel):
    draft_id: str
    document_id: str
    draft_type: str
    draft: str
    evidence: list[EvidenceChunk]
    model_used: str
    grounding_note: str
    applied_learning_rules: list[LearnedRule] = []
    learning_rules_warning: str | None = None


class DraftEditRequest(BaseModel):
    edited_draft: str = Field(min_length=1)

    @field_validator("edited_draft")
    @classmethod
    def require_non_empty_edit(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("edited_draft must not be empty.")
        return cleaned


class DraftEditResponse(BaseModel):
    edit_id: str
    draft_id: str
    learned_rules: list[LearnedRule]
    message: str
    warning: str | None = None


class LearningRuleResponse(BaseModel):
    rule_id: str
    rule_type: str
    rule_text: str
    example_before: str | None = None
    example_after: str | None = None
    is_active: bool
    source_edit_id: str | None = None


class LearningRuleUpdateRequest(BaseModel):
    is_active: bool


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
