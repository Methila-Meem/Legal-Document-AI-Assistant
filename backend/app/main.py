from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.db.database import initialize_database
from app.routers import documents, health
from app.services.storage_service import ensure_storage_directories


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_storage_directories()
    await initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Legal-style document understanding and grounded drafting API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.app_name, "status": "running"}
