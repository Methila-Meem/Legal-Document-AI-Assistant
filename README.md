# Legal Document AI Assistant

Full-stack legal-style document understanding and grounded drafting system for the AI Engineer assessment.

## Overview

The project supports document upload, TXT/PDF/image text extraction, structured field extraction, retrieval-ready indexing, grounded evidence retrieval, grounded draft generation, and an operator improvement loop that learns reusable drafting rules from saved edits and applies active rules to future drafts.

## Architecture

- `backend/` - FastAPI API, SQLite schema, upload validation, document processing, structured extraction, embeddings, ChromaDB indexing, retrieval, draft generation, operator edits, learned rules, and local storage.
- `frontend/` - Next.js reviewer dashboard with a 10-step workflow, gated actions, status messages, evidence display, editable drafts, learned rules, and improved-draft comparison.
- `sample_data/` - synthetic sample input files for reviewer demos.
- `sample_outputs/` - synthetic example outputs that illustrate expected behavior.
- `PROJECT_STATE.md` - continuity notes for future development.

## Tech Stack

- Backend: Python, FastAPI, Pydantic, SQLite, aiosqlite
- OCR/PDF: EasyOCR, optional Tesseract fallback, PyMuPDF, OpenCV headless, Pillow, numpy
- Retrieval: sentence-transformers/all-MiniLM-L6-v2, ChromaDB
- Frontend: Next.js, TypeScript, Tailwind CSS, react-dropzone
- Testing: pytest, httpx
- LLM extraction/drafting: `gpt-4o-mini` via GitHub Models

## Backend Setup

Windows:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python scripts/check_ocr.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

macOS/Linux:

```bash
cd backend
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python scripts/check_ocr.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the backend at `http://localhost:8000`.

## OCR Setup and Troubleshooting

Default OCR engine: EasyOCR.

Fallback/optional OCR engine: Tesseract.

OCR runs locally. Digital PDFs are handled by PyMuPDF first and do not require OCR. OCR is only required for scanned PDFs, image files, or PDF pages with little/no extractable text. The first EasyOCR run may download model weights.

Environment options in `backend/.env`:

```text
OCR_ENGINE=easyocr
OCR_LANG=en
OCR_CONFIDENCE_THRESHOLD=0.60
TESSERACT_CMD=
```

Allowed `OCR_ENGINE` values are `easyocr`, `tesseract`, and `auto`. In `auto` mode the backend tries EasyOCR first, then Tesseract.

Install dependencies inside `backend/venv`; do not install them globally and then run the backend from a different Python environment.

If EasyOCR/PyTorch has issues on Windows:

```powershell
pip uninstall torch torchvision easyocr -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install easyocr
```

Optional Tesseract install on Windows:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

Then set:

```text
OCR_ENGINE=auto
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Optional Tesseract install on Linux/macOS:

```bash
sudo apt-get install tesseract-ocr
brew install tesseract
```

If OCR is unavailable, check `GET /api/health` and run:

```powershell
python scripts/check_ocr.py
```

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Full Reviewer Workflow

1. Upload Document
2. Process Document
3. Extract Structured Fields
4. Index for Retrieval
5. Retrieve Evidence
6. Generate Grounded Draft
7. Edit Draft
8. Save Operator Edit
9. View Learned Rules
10. Generate Improved Draft

The frontend disables actions until prerequisites are complete and shows success, warning, and error messages for each async operation.

## Demo Workflow

1. Start the backend and frontend.
2. Upload `sample_data/sample_notice.txt`, `sample_data/sample_notice.pdf`, or `sample_data/sample_notice_scanned.png`.
3. Click `Process Document`.
4. Click `Extract Fields`.
5. Click `Index for Retrieval`.
6. Run retrieval with a query such as `unpaid rent cure deadline`.
7. Click `Generate Grounded Draft`.
8. Edit the draft with a cautious wording preference.
9. Click `Save Operator Edit`.
10. Review the Learned Rules panel.
11. Click `Generate Improved Draft` and compare the previous and improved draft panels.

## Key APIs

- `GET /api/health` - health check with database and OCR status.
- `POST /api/documents/upload` - multipart upload using form field `file`.
- `POST /api/documents/{document_id}/process` - extract and persist page text.
- `POST /api/documents/{document_id}/extract-fields` - extract structured legal-style fields.
- `POST /api/documents/{document_id}/index` - chunk text, embed, and index vectors.
- `POST /api/retrieval/query` - retrieve relevant evidence chunks.
- `POST /api/drafts/generate` - generate a grounded case fact summary and return `applied_learning_rules`.
- `POST /api/drafts/{draft_id}/edits` - save an operator edit and learn reusable rules.
- `GET /api/learning-rules` - list learned rules.
- `PATCH /api/learning-rules/{rule_id}` - enable or disable a learned rule.

Processed output is saved to:

```text
backend/storage/processed/{document_id}.json
```

## Health API

Example OCR health payload:

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

The health endpoint still returns HTTP 200 when the API and database are running, even if OCR dependencies are unavailable.

## Sample Inputs and Outputs

All files in `sample_data/` and `sample_outputs/` are fully synthetic. They use fake names, fake addresses, fake case numbers, fake dates, and fake amounts. They are provided only to help reviewers quickly understand system behavior.

Sample inputs:

- `sample_data/sample_notice.txt`
- `sample_data/sample_case_note.txt`
- `sample_data/sample_notice.pdf`
- `sample_data/sample_notice_scanned.png`
- `sample_data/README.md`

Sample outputs:

- `sample_outputs/extracted_text_example.json`
- `sample_outputs/structured_fields_example.json`
- `sample_outputs/retrieval_evidence_example.json`
- `sample_outputs/generated_draft_example.md`
- `sample_outputs/operator_edit_example.json`
- `sample_outputs/learned_rules_example.json`
- `sample_outputs/improved_draft_example.md`
- `sample_outputs/README.md`

## Draft Improvement Loop

Generated drafts are editable. When an operator saves an edit, the backend stores the edited draft, compares it with the original, extracts reusable improvement rules, stores those rules as active by default, and injects the latest active rules into future draft-generation prompts. The response includes `applied_learning_rules` so reviewers can confirm which preferences were sent to the model.

`applied_learning_rules` means the rules were included in the prompt; it does not guarantee changed output if the model decides the rule is already satisfied or unsupported by retrieved evidence.
