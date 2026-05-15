# Legal Document AI Assistant

Full-stack legal-style document understanding and grounded drafting system for the AI Engineer assessment.

## Overview

The project supports safe legal-style document upload, text extraction from TXT/PDF/images, structured field extraction, and retrieval-ready indexing with chunks, embeddings, and ChromaDB. Grounded drafting, operator edits, and learned rules are intentionally deferred to later phases.

## Architecture

- `backend/` - FastAPI API, SQLite schema, startup initialization, upload validation, document processing, structured extraction, chunking, embeddings, ChromaDB indexing, and storage directories
- `frontend/` - Next.js dashboard with backend health check, drag-and-drop upload, processing controls, structured field display, and retrieval indexing controls
- `sample_data/` - future sample input files
- `sample_outputs/` - future generated examples
- `PROJECT_STATE.md` - continuity notes for future development sessions

## Tech Stack

- Backend: Python, FastAPI, Pydantic, SQLite, aiosqlite
- OCR/PDF: PaddleOCR, PaddlePaddle, PyMuPDF, OpenCV headless, Pillow, numpy
- Retrieval: sentence-transformers/all-MiniLM-L6-v2, ChromaDB
- Frontend: Next.js, TypeScript, Tailwind CSS, react-dropzone
- Testing: pytest, httpx
- LLM extraction: optional `gpt-4o-mini` via GitHub Models
- Later phases: grounded drafting, operator edits, learned rules

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

Open `http://localhost:3000`. The dashboard checks backend health, uploads documents, triggers processing, extracts structured fields, and indexes processed text for retrieval.

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
- Next.js dashboard upload and processing UI
- Frontend structured fields panel
- Frontend retrieval indexing panel
- Root, backend, and frontend documentation

Verification completed:

- Backend tests passed with `11 passed`
- Frontend production build completed successfully
- Health payload reports PaddleOCR dependency availability
- Live TXT upload and processing smoke test succeeded after the OCR swap
- Live TXT upload, processing, and structured extraction smoke test succeeded with rules fallback
- ChromaDB add/delete smoke test succeeded with fake embeddings

Pending:

- Grounded drafting with GitHub Models
- Operator edit workflow
- Learned rule generation and reuse

Known issues:

- First PaddleOCR use may download model weights and take longer.
- OCR quality depends on source scan quality and PaddleOCR model behavior.
- First indexing use may download embedding model weights and take longer.
- Upload validation is extension-based only.
- `npm audit --omit=dev` currently reports a moderate advisory in Next.js bundled PostCSS dependency; npm does not provide a clean non-breaking stable fix from the current dependency line.

## Previous / Alternative OCR

Earlier versions used Tesseract via `pytesseract`, which required a separate system install. The active OCR path now uses PaddleOCR.
