import pytest

from app.core.config import settings
from app.services.ocr_service import OCRManager, SUPPORTED_OCR_ENGINES


def test_ocr_engine_config_accepts_supported_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for engine in ("easyocr", "tesseract", "auto"):
        monkeypatch.setattr(settings, "ocr_engine", engine)
        status = OCRManager.health()

        assert status["selected_engine"] == engine
        assert "available" in status
        assert "active_engine" in status
        assert status["fallback_engine"] == "tesseract"


def test_ocr_engine_config_rejects_unsupported_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ocr_engine", "unsupported")

    status = OCRManager.health()

    assert status["available"] is False
    assert "Unsupported OCR_ENGINE value" in str(status["error_message"])


def test_no_removed_ocr_engine_in_supported_values() -> None:
    assert SUPPORTED_OCR_ENGINES == {"easyocr", "tesseract", "auto"}
