# Project State

## Current Phase

Phase 7 completed: the system can generate a grounded first-pass case fact summary from retrieved ChromaDB evidence using `gpt-4o-mini` via GitHub Models, save the draft, and display it in an editable frontend text area.

## Folder Structure

```text
legal-doc-assistant/
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- core/
|   |   |-- db/
|   |   |-- models/
|   |   |-- repositories/
|   |   |-- routers/
|   |   |   |-- documents.py
|   |   |   |-- drafts.py
|   |   |   |-- health.py
|   |   |   `-- retrieval.py
|   |   |-- services/
|   |   |   |-- chunking_service.py
|   |   |   |-- document_processing_service.py
|   |   |   |-- draft_generation_service.py
|   |   |   |-- embedding_service.py
|   |   |   |-- indexing_service.py
|   |   |   |-- llm_service.py
|   |   |   |-- ocr_service.py
|   |   |   |-- retrieval_service.py
|   |   |   |-- storage_service.py
|   |   |   |-- structured_extraction_service.py
|   |   |   `-- vector_store_service.py
|   |   `-- utils/
|   |-- storage/
|   |   |-- uploads/
|   |   |-- processed/
|   |   |-- outputs/
|   |   `-- chroma/
|   |-- tests/
|   |-- requirements.txt
|   |-- .env.example
|   `-- README.md
|-- frontend/
|   |-- app/
|   |-- components/
|   |-- lib/
|   |-- types/
|   |-- package.json
|   `-- README.md
|-- sample_data/
|-- sample_outputs/
|-- PROJECT_STATE.md
|-- .gitignore
`-- README.md
```

## Architecture

The backend is a FastAPI service with modular configuration, errors, database initialization, repositories, routers, services, and utilities. Upload handling validates files, stores UUID-named source files under `backend/storage/uploads/`, and persists metadata in SQLite.

`DocumentProcessingService` extracts text. TXT files are read directly. PDFs use PyMuPDF direct text first, then PaddleOCR when page text is too short. Image uploads and scanned PDF pages are preprocessed and OCRed. Page-level results are saved into `document_pages`, and full processed JSON is written to `backend/storage/processed/{document_id}.json`.

`StructuredExtractionService` reads processed page text, applies rule-based extraction, optionally calls `GitHubModelsService` with `gpt-4o-mini`, validates returned JSON with Pydantic, merges valid LLM output with rule output, and stores results in `document_structured_fields`.

`IndexingService` reads processed pages, uses `ChunkingService` to split text, uses `EmbeddingService` to lazy-load `sentence-transformers/all-MiniLM-L6-v2`, stores chunk rows in SQLite, and writes vectors through `VectorStoreService` into ChromaDB.

`RetrievalService` embeds an operator query with the same embedding model, searches ChromaDB with a required `document_id` filter, converts Chroma distances into bounded relevance scores, and returns inspectable evidence chunks with source metadata.

`DraftGenerationService` retrieves evidence for `case_fact_summary`, loads active learning rules, builds a grounded prompt, calls GitHub Models through `GitHubModelsService`, and returns a draft plus the exact evidence used. The drafts router saves generated content and evidence JSON in the `drafts` table.

The frontend is a Next.js TypeScript dashboard with Tailwind UI for backend health, upload, processing, structured fields, retrieval indexing, retrieval testing, evidence inspection, and editable grounded drafts.

## Backend Endpoints

- `GET /` - root service message
- `GET /api/health` - health check with database and PaddleOCR status
- `GET /api/documents` - placeholder route for future document list workflows
- `POST /api/documents/upload` - multipart document upload using form field `file`
- `POST /api/documents/{document_id}/process` - extract and persist document text
- `POST /api/documents/{document_id}/extract-fields` - extract structured fields from processed text
- `POST /api/documents/{document_id}/index` - chunk processed text, generate embeddings, and index vectors
- `POST /api/retrieval/query` - retrieve relevant evidence chunks from one indexed document
- `POST /api/drafts/generate` - generate and save a grounded case fact summary

## Draft Generation

Request body:

```json
{
  "document_id": "1",
  "draft_type": "case_fact_summary",
  "top_k": 8
}
```

Response:

```json
{
  "draft_id": "1",
  "document_id": "1",
  "draft_type": "case_fact_summary",
  "draft": "# Case Fact Summary\n\n...",
  "evidence": [],
  "model_used": "gpt-4o-mini",
  "grounding_note": "Draft generated only from retrieved evidence."
}
```

Prompt strategy:

- The backend retrieves top evidence from ChromaDB before generation.
- Evidence is labeled as `[E1 p.2]`, `[E2 p.3]`, etc.
- The prompt requires every factual claim to include a source reference.
- The model must write `Not found in the provided documents.` for missing information.
- The prompt forbids invented facts and legal advice.
- The prompt requires cautious legal-style wording.
- OCR confidence below `OCR_CONFIDENCE_THRESHOLD` is called out as an unclear OCR warning.
- Active rows from `learning_rules` are included unless they conflict with grounding.

Required draft structure:

```text
# Case Fact Summary

## 1. Parties Involved
## 2. Key Dates
## 3. Important Facts
## 4. Source Evidence
## 5. Missing or Unclear Information
## 6. Suggested Next Review Points
```

Error behavior:

- Document not found returns `404`.
- Document not indexed returns `409`.
- Unsupported draft type returns `422`.
- No retrieved evidence returns `422`.
- Missing `GITHUB_MODELS_API_KEY` returns `503`.
- LLM timeout returns `504`.
- Invalid/empty model response returns `500`.
- Draft save failure returns `500`.

## Retrieval Querying

Request body:

```json
{
  "document_id": "1",
  "query": "Generate a case fact summary from this document.",
  "top_k": 6
}
```

Evidence response contains `chunk_id`, `document_id`, `page_number`, `text`, `relevance_score`, and `source` metadata with filename, source type, and OCR confidence.

Grounding strategy:

- Retrieval only runs for documents with status `indexed`.
- Query embeddings use `sentence-transformers/all-MiniLM-L6-v2`.
- ChromaDB is queried with `where={"document_id": "<id>"}` to prevent evidence from unrelated documents.
- Returned evidence is shown to the operator and reused for draft generation.

## Retrieval Indexing

Chunking strategy:

- Uses processed page text from `document_pages`.
- Normalizes whitespace and skips empty pages.
- Targets `CHUNK_TARGET_CHARS=900`.
- Uses `CHUNK_OVERLAP_CHARS=150`.
- Prefers natural boundaries such as newlines, sentence endings, and spaces.
- Preserves page metadata on every chunk.

Embedding and vector storage:

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`.
- Embedding model is lazy-loaded and reused across requests.
- ChromaDB persistent directory: `backend/storage/chroma/`.
- ChromaDB collection name: `legal_document_chunks`.
- Chroma metadata includes `document_id`, `chunk_id`, `page_number`, `original_filename`, `source_type`, and `ocr_confidence` when available.

Re-indexing deletes existing SQLite chunks and Chroma vectors for the same document before recreating them.

## Structured Field Extraction Logic

Extracted fields:

- `document_type`
- `parties`
- `dates`
- `addresses`
- `monetary_amounts`
- `case_numbers`
- `key_events`
- `unclear_items`

Rules always run for obvious fields such as dates, money amounts, addresses, case numbers, simple document type classification, key events, and unclear OCR items.

LLM extraction uses `gpt-4o-mini` through GitHub Models when `GITHUB_MODELS_API_KEY` is configured. The key stays backend-only. LLM output is validated against Pydantic schemas before saving. Missing keys, request failures, and invalid JSON fall back to rules with warnings.

## Database Tables

SQLite is initialized from `backend/app/db/schema.sql`.

- `documents` - one row per upload; status progresses through `uploaded`, `processed`, and `indexed`
- `document_pages` - one row per extracted page with `extracted_text`, `source_type`, `ocr_confidence`, and `is_unclear`
- `document_structured_fields` - one row per document storing fields JSON, extraction method, and warnings JSON
- `chunks` - one row per retrieval chunk with content, embedding ID, and metadata JSON
- `drafts` - generated drafts with `document_id`, `draft_type`, `content`, `evidence_json`, and `model_name`
- `operator_edits` - placeholder for future edit tracking
- `learning_rules` - reusable drafting rules; active rules are loaded during draft generation

Repository functions include document insert/fetch/status updates, page replacement/fetch, structured field save, chunk deletion/insertion, active learning rule fetch, and draft insertion.

## Environment Variables

Defined in `backend/.env.example`:

- `APP_NAME`
- `APP_VERSION`
- `ENVIRONMENT`
- `API_PREFIX`
- `DATABASE_URL`
- `STORAGE_DIR`
- `MAX_UPLOAD_SIZE_MB`
- `ALLOWED_UPLOAD_EXTENSIONS`
- `OCR_ENGINE`
- `OCR_LANG`
- `OCR_CONFIDENCE_THRESHOLD`
- `GITHUB_MODELS_API_KEY`
- `GITHUB_MODELS_ENDPOINT`
- `GITHUB_MODELS_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`
- `EMBEDDING_MODEL_NAME`
- `CHROMA_COLLECTION_NAME`
- `CHUNK_TARGET_CHARS`
- `CHUNK_OVERLAP_CHARS`
- `FRONTEND_URL`
- `ALLOWED_ORIGINS`

`GITHUB_MODELS_API_KEY` must stay backend-only and must never be exposed to frontend code.

## Run Commands

Backend:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open local backend URLs using `http://localhost:8000` or `http://127.0.0.1:8000`.

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Tests:

```powershell
cd backend
venv\Scripts\python.exe -m pytest
```

## Manual Test Checklist

1. Configure `GITHUB_MODELS_API_KEY` in `backend/.env`.
2. Upload a TXT or PDF document from the frontend.
3. Click `Process Document`.
4. Optionally click `Extract Fields`.
5. Click `Index for Retrieval`.
6. Optionally run the retrieval test query.
7. Click `Generate Draft`.
8. Confirm the draft includes source references such as `[E1 p.1]`.
9. Confirm missing information is marked as `Not found in the provided documents.`
10. Confirm the evidence panel shows the evidence used for generation.

## Completed Work

- Added `POST /api/drafts/generate`.
- Added draft generation request/response schemas.
- Added `DraftGenerationService`.
- Added generic GitHub Models text generation with timeout handling.
- Added active learning rule loading from SQLite.
- Added draft insertion with evidence JSON.
- Added prompt-builder test for grounding requirements.
- Added frontend Generate Draft button.
- Added editable draft textarea, model display, and grounding warning.
- Evidence panel now shows evidence used for generated drafts.
- Preserved upload, processing, structured extraction, indexing, retrieval, Chroma persistence, and existing frontend controls.
- Updated root, backend, frontend, and project-state documentation.

## Pending Work

- Add operator draft saving/edit tracking.
- Add comparison between original generated draft and edited draft.
- Learn reusable improvement rules from edits.
- Apply learned rules to future drafts.
- Add citation validation or post-generation source-reference checks.
- Optional Docker support.

## Important Decisions

- Draft generation is limited to `case_fact_summary`.
- Draft generation always retrieves evidence first; it does not use full document text directly.
- Active learning rules are loaded now, but rule creation remains a future phase.
- Draft evidence is saved exactly as JSON in the `drafts` table.
- The frontend allows editing generated draft text locally, but does not persist operator edits yet.
- Future changes should update both `PROJECT_STATE.md` and root `README.md` after each phase.

## Known Issues

- First PaddleOCR use may download OCR model weights and take longer than later OCR calls.
- First indexing or retrieval use may download embedding model weights and take longer.
- Draft generation requires `GITHUB_MODELS_API_KEY` and network access to GitHub Models.
- Retrieval quality depends on chunk quality and embedding similarity; there is no reranking yet.
- The system does not yet validate that every generated factual claim has a citation.
- OCR quality depends on source scan quality and PaddleOCR model behavior.
- Upload validation is extension-based only.
- `GET /api/documents` remains a placeholder.
- Local ignored runtime storage and `app.db` may contain manual smoke-test data.
- `npm audit --omit=dev` previously reported a moderate advisory in Next.js bundled PostCSS dependency; npm did not provide a clean non-breaking stable fix from the installed Next.js line.

## Verification

- Backend tests passed with `13 passed`.
- Frontend production build completed successfully with `npm run build`.
- Draft prompt builder is covered by tests.
- Previous chunk creation, upload, processing, OCR service, health, retrieval, and structured extraction tests still pass.

## Next Recommended Phase

Phase 8 should implement operator edit persistence: save edited draft content, store original and edited versions in `operator_edits`, expose a save-edit endpoint, and prepare the data needed to learn reusable improvement rules later.
