import asyncio

from app.routers.health import health_check


def test_health_check_returns_ok() -> None:
    payload = asyncio.run(health_check()).model_dump()

    assert payload["status"] == "ok"
    assert payload["service"] == "Legal Document AI Assistant"
    assert payload["services"]["database"] == "ok"
    assert payload["services"]["ocr"]["engine"] == "PaddleOCR"
    assert "available" in payload["services"]["ocr"]
