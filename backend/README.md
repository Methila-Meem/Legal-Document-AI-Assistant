# Backend

FastAPI backend for the Legal Document AI Assistant.

## Setup

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

Open the backend at `http://localhost:8000` or `http://127.0.0.1:8000`.

## Current Endpoints

- `GET /api/health` - service health check with database and OCR status
- `GET /api/documents` - placeholder route for later document list workflows
- `POST /api/documents/upload` - upload and safely store PDF, PNG, JPG, JPEG, or TXT documents
- `POST /api/documents/{document_id}/process` - extract text from uploaded TXT, PDF, and image documents
- `POST /api/documents/{document_id}/extract-fields` - extract structured legal fields from processed text

## Uploads

Uploaded files are validated by extension and size before metadata is stored in SQLite.

- Allowed extensions: `pdf`, `png`, `jpg`, `jpeg`, `txt`
- Default max size: `25 MB`
- Runtime file location: `backend/storage/uploads/`
- Stored filenames use UUIDs and preserve the original extension
- Original filenames are stored as metadata in the `documents` table

Example:

```powershell
curl.exe -X POST -F "file=@sample.txt" http://localhost:8000/api/documents/upload
```

## Processing

Process a previously uploaded document:

```powershell
curl.exe -X POST http://localhost:8000/api/documents/1/process
```

The processing endpoint:

- Reads TXT files directly
- Extracts digital PDF text with PyMuPDF
- Falls back to PaddleOCR for PDF pages with very short text
- Renders scanned PDF pages to images and runs PaddleOCR
- Preprocesses images with grayscale conversion, light denoising, resizing, and thresholding
- Stores page text in `document_pages`
- Writes full processed JSON to `backend/storage/processed/{document_id}.json`

## OCR

PaddleOCR is the default OCR engine and runs locally through Python dependencies. No external OCR API or separate system OCR install is required.

Environment options:

```text
OCR_ENGINE=paddleocr
OCR_LANG=en
OCR_CONFIDENCE_THRESHOLD=0.60
```

The first OCR request may download PaddleOCR model weights. The backend stores Paddle/PaddleOCR cache data under `backend/storage/processed/ocr_cache/` when it initializes OCR.

## Previous / Alternative OCR

Earlier versions used Tesseract through `pytesseract`, which required a separate system install. The active pipeline now uses PaddleOCR instead.

## Structured Field Extraction

Extract fields after processing:

```powershell
curl.exe -X POST http://localhost:8000/api/documents/1/extract-fields
```

The endpoint extracts:

- `document_type`
- `parties`
- `dates`
- `addresses`
- `monetary_amounts`
- `case_numbers`
- `key_events`
- `unclear_items`

Rules always run for obvious fields such as dates, money amounts, addresses, and case numbers. If `GITHUB_MODELS_API_KEY` is configured, the backend also calls `gpt-4o-mini` through GitHub Models and validates the returned JSON before saving. If the API key is missing, the LLM call fails, or JSON is invalid, the endpoint falls back to rules and returns a warning.

Backend-only environment variables:

```text
GITHUB_MODELS_API_KEY=
GITHUB_MODELS_ENDPOINT=https://models.github.ai/inference/chat/completions
GITHUB_MODELS_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

Never expose `GITHUB_MODELS_API_KEY` to frontend code.

## Notes

The app initializes SQLite and creates required storage folders at startup. Embeddings, ChromaDB, and draft generation are intentionally deferred to later phases.
