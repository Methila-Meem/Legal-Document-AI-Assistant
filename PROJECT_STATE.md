# Project State

## Current Phase

Phase 4 completed: structured field extraction from processed legal-style documents using hybrid rules plus optional GitHub Models LLM extraction.

## Folder Structure

```text
legal-doc-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── routers/
│   │   ├── services/
│   │   │   ├── document_processing_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── ocr_service.py
│   │   │   ├── storage_service.py
│   │   │   └── structured_extraction_service.py
│   │   └── utils/
│   ├── storage/
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── types/
│   ├── package.json
│   └── README.md
├── sample_data/
├── sample_outputs/
├── PROJECT_STATE.md
├── .gitignore
└── README.md
```

## Architecture

The backend is a FastAPI service with modular folders for configuration, errors, database initialization, repositories, routers, services, and utilities. Upload handling validates files, stores UUID-named source files under `backend/storage/uploads/`, and persists document metadata.

`DocumentProcessingService` handles text extraction. TXT files are read directly. PDFs are opened with PyMuPDF; each page uses direct PDF text when enough text is available and falls back to PaddleOCR when text is too short. Image uploads and scanned PDF pages are preprocessed and OCRed. Page-level results are saved into `document_pages`, and full downstream-ready JSON is written to `backend/storage/processed/{document_id}.json`.

`StructuredExtractionService` reads processed page text from `document_pages`, applies rule-based extraction, optionally calls `GitHubModelsService` for `gpt-4o-mini` extraction, validates returned JSON with Pydantic, merges valid LLM output with rule output, and stores the result in `document_structured_fields`.

The frontend is a Next.js TypeScript app with a Tailwind dashboard that checks backend health, uploads documents, triggers processing, and displays structured fields.

## Backend Endpoints

- `GET /` - root service message
- `GET /api/health` - health check with database and PaddleOCR status
- `GET /api/documents` - placeholder route for future document workflows
- `POST /api/documents/upload` - multipart document upload using form field `file`
- `POST /api/documents/{document_id}/process` - extract and persist document text
- `POST /api/documents/{document_id}/extract-fields` - extract structured fields from processed text

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

Rule-based extraction always runs for obvious fields:

- Dates: ISO, slash dates, and common month-name dates
- Money: `$2,500`, `USD $2,500`, and simple `2500 dollars` forms
- Case numbers: visible `case`, `docket`, `matter`, or `file` number patterns
- Addresses: simple street-style address patterns
- Document type: keyword classification such as Notice, Agreement, Lease, Complaint, Invoice, or Court Order
- Unclear items: generated from processed pages marked unclear

LLM extraction:

- Uses `gpt-4o-mini` through GitHub Models when `GITHUB_MODELS_API_KEY` is configured.
- Runs only from the backend. The key is never exposed to frontend code.
- Uses timeout and retry handling.
- Validates returned JSON against the `StructuredFields` Pydantic schema before saving.
- Merges valid LLM output with rule output and returns method `hybrid`.

Fallback behavior:

- Missing API key returns method `rules` with a warning.
- LLM request failure returns method `rules` with a warning.
- Invalid LLM JSON returns method `rules` with a warning.
- Document not found returns `404`.
- Document not processed returns `409`.

## Structured Extraction Response

```json
{
  "document_id": "1",
  "structured_fields": {
    "document_type": "Notice",
    "parties": ["John Smith", "ABC Holdings LLC"],
    "dates": ["2026-03-05"],
    "addresses": ["123 Main Street"],
    "monetary_amounts": ["$2,500"],
    "case_numbers": ["CIV-2026-7788"],
    "key_events": [
      {
        "event": "Date referenced",
        "date": "2026-03-05",
        "source_page": 1
      }
    ],
    "unclear_items": []
  },
  "method": "rules",
  "warnings": ["GitHub Models API key is not configured; used rule-based extraction only."]
}
```

## Database Tables

SQLite is initialized from `backend/app/db/schema.sql`.

- `documents` - one row per upload, status updated to `processed`
- `document_pages` - one row per extracted page, including `extracted_text`, `source_type`, `ocr_confidence`, and `is_unclear`
- `document_structured_fields` - one row per document storing fields JSON, extraction method, and warnings JSON
- `chunks`
- `drafts`
- `operator_edits`
- `learning_rules`

Repository functions:

- `insert_document(...)`
- `fetch_document(document_id)`
- `update_document_status(document_id, status)`
- `replace_document_pages(document_id, pages)`
- `fetch_processed_pages(document_id)`
- `save_structured_fields(...)`

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
- `FRONTEND_URL`
- `ALLOWED_ORIGINS`

Future GitHub Models API keys must stay backend-only.

## Run Commands

Backend:

```powershell
cd backend
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

## Completed Work

- Added `document_structured_fields` table.
- Added `POST /api/documents/{document_id}/extract-fields`.
- Added `StructuredExtractionService`.
- Added `GitHubModelsService` in `services/llm_service.py`.
- Added rule extraction for dates, money, case numbers, addresses, document type, key events, and unclear items.
- Added optional GitHub Models extraction with validated JSON.
- Added fallback behavior when the LLM key is missing, the request fails, or JSON is invalid.
- Added structured field persistence.
- Added frontend `Extract Fields` button and structured fields panel.
- Added backend tests for rules fallback and conflict on unprocessed documents.
- Preserved upload, processing, `document_pages`, processed JSON output, and frontend process button.
- Updated root, backend, frontend, and project-state documentation.

## Pending Work

- Add chunking for retrieved evidence.
- Add embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
- Add ChromaDB retrieval.
- Add grounded draft generation using `gpt-4o-mini` via GitHub Models.
- Add operator draft editing.
- Learn reusable improvement rules from edits.
- Apply learned rules to future drafts.
- Optional Docker support.

## Important Decisions

- Structured extraction is stored separately in `document_structured_fields` instead of adding a large JSON column to `documents`.
- Rules always run, even when LLM extraction is available.
- LLM output is only used after Pydantic validation.
- Method is `rules` when no LLM is used and `hybrid` when valid LLM output is merged with rules.
- Embeddings and ChromaDB were not implemented in Phase 4.
- The GitHub Models API key must never be exposed to frontend code.
- Future changes should update both `PROJECT_STATE.md` and root `README.md` after each phase.

## Known Issues

- Rule extraction is intentionally conservative and may miss complex party/address formats.
- LLM extraction depends on a backend-only GitHub Models API key and network availability.
- `GET /api/documents` remains a placeholder.
- First PaddleOCR use may download model weights and take longer than later OCR calls.
- Upload validation is extension-based only.
- Local ignored runtime storage and `app.db` may contain manual smoke-test uploads.
- `npm audit --omit=dev` reports a moderate advisory in Next.js bundled PostCSS dependency. npm does not currently offer a clean non-breaking stable fix from the installed Next.js line.

## Verification

- Backend tests passed with `9 passed`.
- Frontend production build completed successfully with `npm run build`.
- Rules-only structured extraction fallback is covered by tests.
- Document-not-processed conflict behavior is covered by tests.
- Live TXT upload, processing, and structured extraction smoke test succeeded with rules fallback.

## Next Recommended Phase

Phase 5 should implement chunking and retrieval preparation: split processed page text into reusable chunks, persist chunk records, generate embeddings with `sentence-transformers/all-MiniLM-L6-v2`, and store vectors in ChromaDB. Do not implement drafting until retrieval evidence is available.
