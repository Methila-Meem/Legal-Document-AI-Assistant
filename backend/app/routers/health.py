from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse, OcrHealth, ServicesHealth
from app.services.ocr_service import OCRManager


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    ocr_health = OCRManager.health()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        services=ServicesHealth(
            database="ok",
            ocr=OcrHealth(
                selected_engine=str(ocr_health["selected_engine"]),
                available=bool(ocr_health["available"]),
                active_engine=(
                    str(ocr_health["active_engine"])
                    if ocr_health.get("active_engine") is not None
                    else None
                ),
                fallback_engine=(
                    str(ocr_health["fallback_engine"])
                    if ocr_health.get("fallback_engine") is not None
                    else None
                ),
                error_message=(
                    str(ocr_health["error_message"])
                    if ocr_health.get("error_message") is not None
                    else None
                ),
                message=str(ocr_health["message"]),
            ),
        ),
    )
