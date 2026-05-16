from pathlib import Path
import os
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.ocr_service import (  # noqa: E402
    EasyOCRService,
    OCRManager,
    OcrUnavailableError,
    TesseractOCRService,
)


def main() -> int:
    selected_engine = os.getenv("OCR_ENGINE", settings.ocr_engine).lower().strip()
    print(f"Python: {sys.executable}")
    print(f"OCR_ENGINE: {selected_engine}")

    easy_status = EasyOCRService.status()
    tesseract_status = TesseractOCRService.status()
    print_status("EasyOCR", easy_status)
    print_status("Tesseract", tesseract_status)

    if selected_engine == "easyocr":
        return check_easyocr()
    if selected_engine == "tesseract":
        return check_tesseract()
    if selected_engine == "auto":
        easy_result = check_easyocr(silent_failure=True)
        if easy_result == 0:
            return 0
        return check_tesseract()

    print("OCR initialization: FAILED")
    print("Unsupported OCR_ENGINE. Use easyocr, tesseract, or auto.")
    return 1


def check_easyocr(silent_failure: bool = False) -> int:
    try:
        EasyOCRService.initialize()
        print("EasyOCR initialization: OK")
        return 0
    except OcrUnavailableError as exc:
        if not silent_failure:
            print("EasyOCR initialization: FAILED")
            print(str(exc))
            print(
                "Recommended fix on Windows: pip uninstall torch torchvision easyocr -y; "
                "pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu; "
                "pip install easyocr"
            )
        return 1


def check_tesseract() -> int:
    try:
        TesseractOCRService.initialize()
        print("Tesseract initialization: OK")
        return 0
    except OcrUnavailableError as exc:
        print("Tesseract initialization: FAILED")
        print(str(exc))
        print(
            "Recommended fix: install the Tesseract OCR system package and set "
            "TESSERACT_CMD in backend/.env if it is not on PATH."
        )
        return 1


def print_status(label: str, status: dict[str, object]) -> None:
    available = "available" if status["available"] else "unavailable"
    print(f"{label}: {available}")
    if status.get("error_message"):
        print(f"{label} error: {status['error_message']}")


if __name__ == "__main__":
    sys.exit(main())
