from pathlib import Path

import aiosqlite

from app.core.config import settings


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def initialize_database() -> None:
    db_path = settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(schema)
        await _ensure_document_pages_columns(db)
        await _ensure_learning_rules_columns(db)
        await db.commit()


def get_database_path() -> Path:
    return settings.sqlite_path


async def _ensure_document_pages_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(document_pages)")
    rows = await cursor.fetchall()
    existing_columns = {row[1] for row in rows}

    migrations = {
        "source_type": "ALTER TABLE document_pages ADD COLUMN source_type TEXT",
        "ocr_confidence": "ALTER TABLE document_pages ADD COLUMN ocr_confidence REAL",
        "ocr_engine": "ALTER TABLE document_pages ADD COLUMN ocr_engine TEXT",
        "is_unclear": (
            "ALTER TABLE document_pages "
            "ADD COLUMN is_unclear INTEGER NOT NULL DEFAULT 0"
        ),
    }
    for column, statement in migrations.items():
        if column not in existing_columns:
            await db.execute(statement)


async def _ensure_learning_rules_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(learning_rules)")
    rows = await cursor.fetchall()
    existing_columns = {row[1] for row in rows}

    migrations = {
        "example_before": "ALTER TABLE learning_rules ADD COLUMN example_before TEXT",
        "example_after": "ALTER TABLE learning_rules ADD COLUMN example_after TEXT",
    }
    for column, statement in migrations.items():
        if column not in existing_columns:
            await db.execute(statement)
