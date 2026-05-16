# Project State

## Current Phase

The system now uses EasyOCR as the default OCR engine with optional Tesseract fallback. The reviewer workflow remains intact: upload, process, extract fields, index, retrieve evidence, generate grounded draft, edit draft, save operator edit, view learned rules, and generate an improved draft using active learned rules.

## Folder Structure

```text
legal-doc-assistant/
|-- backend/
|   |-- app/
|   |   |-- core/
|   |   |-- db/
|   |   |-- models/
|   |   |-- repositories/
|   |   |-- routers/
|   |   `-- services/
|   |-- scripts/
|   |   `-- check_ocr.py
|   |-- storage/
|   |-- tests/
|   |-- requirements.txt
|   |-- .env.example
|   `-- README.md
|-- frontend/
|-- sample_data/
|-- sample_outputs/
|-- PROJECT_STATE.md
`-- README.md
```

## Current OCR Architecture

Default OCR: EasyOCR.

Optional fallback OCR: Tesseract.

Reason for the change: the previous OCR stack caused Windows dependency conflicts and made reviewer setup less reliable. The active OCR path has been simplified to EasyOCR by default, with Tesseract available when the system OCR engine is installed separately.

`OCR_ENGINE` values:

- `easyocr` - use only EasyOCR.
- `tesseract` - use only Tesseract.
- `auto` - try EasyOCR first, then Tesseract.

Environment variables:

- `OCR_ENGINE=easyocr`
- `OCR_LANG=en`
- `OCR_CONFIDENCE_THRESHOLD=0.60`
- `TESSERACT_CMD=`

`backend/app/services/ocr_service.py` contains:

- `OCRManager`
- `EasyOCRService`
- `TesseractOCRService`
- normalized OCR result models with `text`, `confidence`, `lines`, and `engine_used`

OCR dependencies are imported lazily. Backend startup does not fail just because OCR dependencies are missing. TXT files and digital PDFs can still process without OCR. OCR is required only for images, scanned PDFs, or PDF pages with little/no extractable text.

## Processing Flow

`DocumentProcessingService` behavior:

- TXT files are read directly.
- Digital PDFs use PyMuPDF text extraction first.
- PDF pages with little/no extractable text are rendered and sent to `OCRManager`.
- PNG/JPG/JPEG files are preprocessed with OpenCV/Pillow and sent to `OCRManager`.
- Processed JSON is written to `backend/storage/processed/{document_id}.json`.
- Page text is persisted in `document_pages`.

Processed page output includes:

- `page_number`
- `source_type`
- `text`
- `text_preview`
- `ocr_confidence`
- `ocr_engine`
- `is_unclear`
- `warnings`

The `document_pages` table now includes an `ocr_engine` column, with a migration helper for existing local databases.

## Health and Diagnostics

`GET /api/health` returns OCR status without failing the health endpoint when OCR is unavailable:

```json
{
  "status": "ok",
  "service": "Legal Document AI Assistant",
  "version": "0.1.0",
  "services": {
    "database": "ok",
    "ocr": {
      "selected_engine": "easyocr",
      "available": true,
      "active_engine": "easyocr",
      "fallback_engine": "tesseract",
      "error_message": null,
      "message": "EasyOCR is ready."
    }
  }
}
```

Diagnostic script:

```powershell
cd backend
venv\Scripts\activate
python scripts/check_ocr.py
```

The script prints the Python executable, selected OCR engine, EasyOCR status, Tesseract status, initialization result, and recommended setup fixes.

## Backend Endpoints

- `GET /` - root service message
- `GET /api/health` - database and OCR status
- `GET /api/documents` - placeholder route
- `POST /api/documents/upload` - upload a supported document
- `POST /api/documents/{document_id}/process` - extract and persist document text
- `POST /api/documents/{document_id}/extract-fields` - extract structured fields
- `POST /api/documents/{document_id}/index` - chunk text, generate embeddings, and index vectors
- `POST /api/retrieval/query` - retrieve relevant evidence chunks
- `POST /api/drafts/generate` - generate and save a grounded case fact summary
- `POST /api/drafts/{draft_id}/edits` - save an operator edit and extract reusable learned rules
- `GET /api/learning-rules` - list learned rules
- `PATCH /api/learning-rules/{rule_id}` - enable or disable a learned rule

Error behavior:

- OCR unavailable when OCR is required returns HTTP 503 with `message`, `selected_engine`, `active_engine`, `fallback_engine`, `error`, and `hint`.
- Health returns HTTP 200 when the API and database are running, even if OCR is unavailable.
- Central error responses use `{ "error": { "code", "message", "details" } }`.

## Draft Improvement Loop

`DraftGenerationService` retrieves evidence, loads the latest 10 active learned rules, injects concise operator-learned preferences into the prompt, and returns `applied_learning_rules`. If rules fail to load, draft generation continues and returns `learning_rules_warning`.

`EditLearningService` saves operator edits, computes a diff, asks `gpt-4o-mini` through GitHub Models to extract reusable rules, and stores active rules in `learning_rules`. If the LLM is unavailable, the edit is still saved and a warning is returned. If model JSON is invalid, the backend attempts a simple heuristic rule.

`applied_learning_rules` proves rules were included in the generation request. It does not guarantee changed output if the model decides the preference is already satisfied or unsupported by retrieved evidence.

## Sample Data and Outputs

Sample input files:

- `sample_data/sample_notice.txt` - synthetic notice of alleged unpaid rent and missing reports.
- `sample_data/sample_case_note.txt` - synthetic internal case note.
- `sample_data/sample_notice.pdf` - generated PDF version of the synthetic notice.
- `sample_data/sample_notice_scanned.png` - scanned-style image for OCR testing.
- `sample_data/README.md` - sample input guidance.

Sample output files:

- `sample_outputs/extracted_text_example.json`
- `sample_outputs/structured_fields_example.json`
- `sample_outputs/retrieval_evidence_example.json`
- `sample_outputs/generated_draft_example.md`
- `sample_outputs/operator_edit_example.json`
- `sample_outputs/learned_rules_example.json`
- `sample_outputs/improved_draft_example.md`
- `sample_outputs/README.md`

These files are synthetic demo aids only. Formal evaluation was intentionally not added because assessment reviewers will evaluate the system themselves.

## Verification Commands

Backend:

```powershell
cd backend
venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd frontend
npm run build
```

OCR:

```powershell
cd backend
venv\Scripts\activate
python scripts/check_ocr.py
```

## Known Limitations

- EasyOCR uses PyTorch and may require the CPU PyTorch reinstall command on Windows.
- Tesseract requires a system-level installation if used.
- First EasyOCR or embedding-model use may download model weights.
- OCR quality depends on scan quality and source layout.
- Draft generation and rule extraction require `GITHUB_MODELS_API_KEY`.
- Retrieval quality depends on chunking and embedding similarity; there is no reranking yet.
- The system does not yet validate every generated claim against citations after generation.
- Repeated operator edits may create duplicate or overlapping learned rules.

## Next Recommended Phase

Add reviewer convenience and quality checks: one-click demo reset, citation validation, learned-rule deduplication, and post-generation checks that flag unsupported claims before final review.
