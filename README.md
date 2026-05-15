# Legal Document AI Assistant

Full-stack legal-style document understanding and grounded drafting system for the AI Engineer assessment.

## Overview

The project supports safe legal-style document upload, text extraction from TXT/PDF/images, structured field extraction, retrieval-ready indexing, grounded evidence retrieval from ChromaDB, and grounded first-pass draft generation. Operator edits and learned rules are intentionally deferred to later phases.

## Architecture

- `backend/` - FastAPI API, SQLite schema, startup initialization, upload validation, document processing, structured extraction, chunking, embeddings, ChromaDB indexing, retrieval queries, draft generation, and storage directories
- `frontend/` - Next.js dashboard with backend health check, drag-and-drop upload, processing controls, structured field display, retrieval indexing controls, evidence results, and editable draft output
- `sample_data/` - future sample input files
- `sample_outputs/` - future generated examples
- `PROJECT_STATE.md` - continuity notes for future development sessions

## Tech Stack

- Backend: Python, FastAPI, Pydantic, SQLite, aiosqlite
- OCR/PDF: PaddleOCR, PaddlePaddle, PyMuPDF, OpenCV headless, Pillow, numpy
- Retrieval: sentence-transformers/all-MiniLM-L6-v2, ChromaDB
- Frontend: Next.js, TypeScript, Tailwind CSS, react-dropzone
- Testing: pytest, httpx
- LLM extraction/drafting: `gpt-4o-mini` via GitHub Models
- Later phases: operator edits, learned rules

## Backend Setup

Windows:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the backend at `http://localhost:8000`, not `http://0.0.0.0:8000`.

## OCR Setup

PaddleOCR is the default OCR engine. It runs locally through Python dependencies, so no external OCR API or separate system OCR executable is required.

Environment options in `backend/.env`:

```text
OCR_ENGINE=paddleocr
OCR_LANG=en
OCR_CONFIDENCE_THRESHOLD=0.60
```

The first OCR request may download PaddleOCR model weights. The backend sets Paddle/PaddleOCR cache folders under `backend/storage/processed/ocr_cache/`.

PyMuPDF is still used first for digital PDF text. PaddleOCR is used only for scanned PDFs, image files, or PDF pages with little/no extractable text.

## Upload API

`POST /api/documents/upload`

Uploads one document using multipart form field `file`.

Supported extensions:

- `pdf`
- `png`
- `jpg`
- `jpeg`
- `txt`

## Processing API

`POST /api/documents/{document_id}/process`

Response shape:

```json
{
  "document_id": "1",
  "status": "processed",
  "page_count": 1,
  "pages": [
    {
      "page_number": 1,
      "source_type": "pdf_text",
      "text_preview": "Extracted text preview...",
      "ocr_confidence": null,
      "is_unclear": false
    }
  ],
  "warnings": []
}
```

Processed output is also saved to:

```text
backend/storage/processed/{document_id}.json
```

## Structured Extraction API

`POST /api/documents/{document_id}/extract-fields`

The document must already be processed. The endpoint runs rule-based extraction and, when `GITHUB_MODELS_API_KEY` is available, merges validated `gpt-4o-mini` output from GitHub Models.

Backend-only environment variables:

```text
GITHUB_MODELS_API_KEY=
GITHUB_MODELS_ENDPOINT=https://models.github.ai/inference/chat/completions
GITHUB_MODELS_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

If the key is missing or the LLM response fails validation, the system falls back to rules and returns a warning.

Response shape:

```json
{
  "document_id": "1",
  "structured_fields": {
    "document_type": "Notice",
    "parties": ["John Smith"],
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
  "warnings": []
}
```

## Retrieval Index API

`POST /api/documents/{document_id}/index`

The document must already be processed. The endpoint splits page text into overlapping chunks, stores chunk records in SQLite, generates embeddings with `sentence-transformers/all-MiniLM-L6-v2`, writes vectors to ChromaDB, and updates the document status to `indexed`.

Environment options in `backend/.env`:

```text
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
CHROMA_COLLECTION_NAME=legal_document_chunks
CHUNK_TARGET_CHARS=900
CHUNK_OVERLAP_CHARS=150
```

ChromaDB data is stored locally under `backend/storage/chroma/`. The first indexing request may download the embedding model weights.

Response shape:

```json
{
  "document_id": "1",
  "status": "indexed",
  "chunk_count": 12,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "vector_db": "ChromaDB"
}
```

Re-indexing deletes existing SQLite chunks and Chroma vectors for that document before recreating them.

## Retrieval Query API

`POST /api/retrieval/query`

Searches the ChromaDB collection for relevant chunks from one indexed document. The backend embeds the query with `sentence-transformers/all-MiniLM-L6-v2` and applies a Chroma `document_id` filter so results do not mix evidence from unrelated documents.

Request:

```json
{
  "document_id": "1",
  "query": "Generate a case fact summary from this document.",
  "top_k": 6
}
```

Response:

```json
{
  "query": "Generate a case fact summary from this document.",
  "document_id": "1",
  "evidence": [
    {
      "chunk_id": "12",
      "document_id": "1",
      "page_number": 1,
      "text": "Relevant extracted text...",
      "relevance_score": 0.87,
      "source": {
        "filename": "sample_notice.pdf",
        "source_type": "ocr",
        "ocr_confidence": 0.81
      }
    }
  ],
  "message": null
}
```

If no matching chunks are found, the endpoint returns an empty `evidence` list with a clear `message`.

## Draft Generation API

`POST /api/drafts/generate`

Generates a grounded first-pass case fact summary from retrieved evidence. The backend retrieves evidence from ChromaDB, loads active `learning_rules`, builds a grounding prompt, calls `gpt-4o-mini` through GitHub Models, saves the draft and evidence JSON into SQLite, and returns the draft.

Request:

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

Prompt safeguards:

- Use only retrieved evidence.
- Every factual claim must include a source reference like `[E1 p.2]`.
- Missing information must be stated as `Not found in the provided documents.`
- Do not invent facts.
- Do not provide legal advice.
- Use cautious legal-style wording.
- Include unclear OCR warnings where relevant.

GitHub Models setup in `backend/.env`:

```text
GITHUB_MODELS_API_KEY=your_backend_only_key
GITHUB_MODELS_ENDPOINT=https://models.github.ai/inference/chat/completions
GITHUB_MODELS_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

Never expose `GITHUB_MODELS_API_KEY` to frontend code.

## Health API

`GET /api/health` now includes service status:

```json
{
  "status": "ok",
  "service": "Legal Document AI Assistant",
  "version": "0.1.0",
  "services": {
    "database": "ok",
    "ocr": {
      "engine": "PaddleOCR",
      "available": true,
      "message": "PaddleOCR dependencies are installed. Model loads on first OCR request."
    }
  }
}
```

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The dashboard checks backend health, uploads documents, triggers processing, extracts structured fields, indexes processed text, retrieves inspectable evidence chunks, and generates editable grounded drafts.

## Current Status

Completed:

- FastAPI app shell with CORS
- `GET /api/health` with database and PaddleOCR status
- Centralized error response format
- SQLite schema and startup initialization
- Safe `POST /api/documents/upload`
- UUID-based upload storage
- Document metadata persistence in SQLite
- `POST /api/documents/{document_id}/process`
- `POST /api/documents/{document_id}/extract-fields`
- `POST /api/documents/{document_id}/index`
- `POST /api/retrieval/query`
- `POST /api/drafts/generate`
- TXT direct extraction
- Digital PDF extraction with PyMuPDF
- PaddleOCR fallback for scanned/low-text PDF pages
- Image OCR with preprocessing
- Page text persistence in `document_pages`
- Processed JSON output for downstream retrieval
- Rule-based structured field extraction
- Optional GitHub Models extraction with rule fallback
- Structured fields persistence in SQLite
- Chunking service for processed page text
- Embedding service using `sentence-transformers/all-MiniLM-L6-v2`
- ChromaDB vector indexing under `backend/storage/chroma/`
- SQLite chunk persistence and document status update to `indexed`
- Document-filtered ChromaDB retrieval over indexed chunks
- Grounded case fact summary generation with GitHub Models
- Draft and evidence JSON persistence in SQLite
- Next.js dashboard upload and processing UI
- Frontend structured fields panel
- Frontend retrieval indexing panel
- Frontend retrieval test panel and evidence display
- Frontend Generate Draft button and editable draft textarea
- Root, backend, and frontend documentation

Verification completed:

- Backend tests passed with `13 passed`
- Frontend production build completed successfully
- Health payload reports PaddleOCR dependency availability
- Live TXT upload and processing smoke test succeeded after the OCR swap
- Live TXT upload, processing, and structured extraction smoke test succeeded with rules fallback
- ChromaDB add/delete smoke test succeeded with fake embeddings
- Retrieval request validation test passed
- Draft prompt-builder test passed

Pending:

- Operator edit workflow
- Learned rule generation and reuse

Known issues:

- First PaddleOCR use may download model weights and take longer.
- OCR quality depends on source scan quality and PaddleOCR model behavior.
- First indexing use may download embedding model weights and take longer.
- Retrieval quality depends on chunk quality and embedding similarity; there is no reranking yet.
- Draft quality depends on retrieved evidence and GitHub Models availability.
- Upload validation is extension-based only.
- `npm audit --omit=dev` currently reports a moderate advisory in Next.js bundled PostCSS dependency; npm does not provide a clean non-breaking stable fix from the current dependency line.

## Previous / Alternative OCR

Earlier versions used Tesseract via `pytesseract`, which required a separate system install. The active OCR path now uses PaddleOCR.
