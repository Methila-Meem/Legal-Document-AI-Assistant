from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse, OcrHealth, ServicesHealth
from app.services.ocr_service import PaddleOCRService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    ocr_health = PaddleOCRService.health()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        services=ServicesHealth(
            database="ok",
            ocr=OcrHealth(
                engine=str(ocr_health["engine"]),
                available=bool(ocr_health["available"]),
                message=str(ocr_health["message"]),
            ),
        ),
    )
