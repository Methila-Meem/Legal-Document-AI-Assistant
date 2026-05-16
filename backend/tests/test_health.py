import asyncio

from app.routers.health import health_check


def test_health_check_returns_ok() -> None:
    payload = asyncio.run(health_check()).model_dump()

    assert payload["status"] == "ok"
    assert payload["service"] == "Legal Document AI Assistant"
    assert payload["services"]["database"] == "ok"
    assert payload["services"]["ocr"]["selected_engine"] in {"easyocr", "tesseract", "auto"}
    assert "available" in payload["services"]["ocr"]
    assert "active_engine" in payload["services"]["ocr"]
    assert payload["services"]["ocr"]["fallback_engine"] == "tesseract"
    assert "error_message" in payload["services"]["ocr"]
    assert "message" in payload["services"]["ocr"]
