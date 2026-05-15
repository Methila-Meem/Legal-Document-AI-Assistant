import pytest

from app.services.ocr_service import PaddleOCRService


def test_paddleocr_health_reports_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PaddleOCRService, "_ocr_instance", None)
    monkeypatch.setattr(PaddleOCRService, "_init_error", None)

    health = PaddleOCRService.health()

    assert health["engine"] == "PaddleOCR"
    assert "available" in health
    assert "message" in health


def test_paddleocr_health_reports_cached_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PaddleOCRService, "_ocr_instance", None)
    monkeypatch.setattr(PaddleOCRService, "_init_error", "PaddleOCR failed to initialize.")

    health = PaddleOCRService.health()

    assert health["engine"] == "PaddleOCR"
    assert health["available"] is False
    assert health["message"] == "PaddleOCR failed to initialize."
