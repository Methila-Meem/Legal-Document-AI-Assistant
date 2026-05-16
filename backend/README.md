# Backend

FastAPI backend for document upload, text extraction, structured extraction, retrieval indexing, grounded draft generation, operator edit capture, and learned drafting rules.

## Setup

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

## OCR Setup and Troubleshooting

Default OCR engine: EasyOCR.

Fallback/optional OCR engine: Tesseract.

Digital PDFs are extracted with PyMuPDF first and do not require OCR. OCR is used for images, scanned PDFs, and PDF pages with little/no extractable text. OCR runs locally, and the first EasyOCR run may download model weights.

Environment:

```text
OCR_ENGINE=easyocr
OCR_LANG=en
OCR_CONFIDENCE_THRESHOLD=0.60
TESSERACT_CMD=
```

Allowed `OCR_ENGINE` values:

- `easyocr` - use only EasyOCR.
- `tesseract` - use only Tesseract.
- `auto` - try EasyOCR first, then Tesseract.

Install packages inside `backend/venv`; do not install globally.

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

Run diagnostics:

```powershell
python scripts/check_ocr.py
```

## Processing

`POST /api/documents/{document_id}/process`:

- TXT files use direct text extraction.
- Digital PDFs use PyMuPDF text extraction first.
- Scanned PDF pages and images use the configured OCR manager.
- Processed page JSON includes `source_type`, `ocr_confidence`, `ocr_engine`, `is_unclear`, and page warnings.
- Full processed output is written to `backend/storage/processed/{document_id}.json`.
- Page text is persisted in `document_pages`.

If OCR is required but unavailable, the backend returns HTTP 503 with a diagnostic message and setup hint. TXT and digital PDF extraction can still work without OCR dependencies.

## Health

`GET /api/health` returns database and OCR status:

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

Health remains HTTP 200 while the API/database are running, even if OCR is unavailable.

## Tests

```powershell
cd backend
venv\Scripts\python.exe -m pytest
```
