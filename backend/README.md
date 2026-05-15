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
- `POST /api/documents/{document_id}/index` - chunk processed text, generate embeddings, and store vectors in ChromaDB
- `POST /api/retrieval/query` - retrieve relevant evidence chunks from one indexed document
- `POST /api/drafts/generate` - generate a grounded case fact summary from retrieved evidence

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

## Retrieval Indexing

Index a processed document for retrieval:

```powershell
curl.exe -X POST http://localhost:8000/api/documents/1/index
```

The indexing endpoint:

- Requires the document to have status `processed` or `indexed`
- Reads page text from `document_pages`
- Splits text into roughly 700-1000 character chunks with 100-150 character overlap
- Preserves page number, source type, OCR confidence, original filename, and document ID metadata
- Generates embeddings with `sentence-transformers/all-MiniLM-L6-v2`
- Stores chunks in the SQLite `chunks` table
- Stores vectors in the ChromaDB collection `legal_document_chunks`
- Updates the document status to `indexed`

Environment options:

```text
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
CHROMA_COLLECTION_NAME=legal_document_chunks
CHUNK_TARGET_CHARS=900
CHUNK_OVERLAP_CHARS=150
```

ChromaDB persists runtime vector data under `backend/storage/chroma/`. The first indexing request may download embedding model weights into `backend/storage/processed/embedding_cache/`.

Re-indexing deletes old chunks and vectors for the same document, then recreates them.

## Retrieval Querying

Query an indexed document for evidence:

```powershell
curl.exe -X POST http://localhost:8000/api/retrieval/query `
  -H "Content-Type: application/json" `
  -d "{\"document_id\":\"1\",\"query\":\"Generate a case fact summary from this document.\",\"top_k\":6}"
```

The retrieval endpoint:

- Requires the document to have status `indexed`
- Rejects empty queries
- Embeds the query with `sentence-transformers/all-MiniLM-L6-v2`
- Searches ChromaDB collection `legal_document_chunks`
- Filters by `document_id` so evidence does not cross documents
- Returns chunk text, page number, relevance score, filename, source type, and OCR confidence

If no evidence is found, the endpoint returns an empty `evidence` list with a message instead of failing.

## Draft Generation

Generate a grounded first-pass case fact summary:

```powershell
curl.exe -X POST http://localhost:8000/api/drafts/generate `
  -H "Content-Type: application/json" `
  -d "{\"document_id\":\"1\",\"draft_type\":\"case_fact_summary\",\"top_k\":8}"
```

The draft generation endpoint:

- Requires the document to have status `indexed`
- Retrieves evidence from ChromaDB before generation
- Loads active rows from `learning_rules`
- Calls `gpt-4o-mini` through GitHub Models
- Enforces source references such as `[E1 p.2]`
- Requires missing information to be written as `Not found in the provided documents.`
- Saves the draft and exact evidence JSON in the `drafts` table
- Returns model name, grounding note, draft text, and evidence used

GitHub Models environment variables:

```text
GITHUB_MODELS_API_KEY=
GITHUB_MODELS_ENDPOINT=https://models.github.ai/inference/chat/completions
GITHUB_MODELS_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

The API key must remain backend-only.

## Notes

The app initializes SQLite and creates required storage folders at startup. Operator edits and learned rules are intentionally deferred to later phases.
