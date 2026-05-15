from dataclasses import dataclass
import json

import aiosqlite

from app.core.config import settings


@dataclass(frozen=True)
class DocumentRecord:
    id: int
    original_filename: str
    stored_filename: str
    content_type: str | None
    file_size_bytes: int
    status: str


async def insert_document(
    *,
    original_filename: str,
    stored_filename: str,
    content_type: str | None,
    file_size_bytes: int,
    status: str = "uploaded",
) -> DocumentRecord:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO documents (
                original_filename,
                stored_filename,
                content_type,
                file_size_bytes,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                original_filename,
                stored_filename,
                content_type,
                file_size_bytes,
                status,
            ),
        )
        await db.commit()
        document_id = cursor.lastrowid

    if document_id is None:
        raise RuntimeError("Document insert did not return an id.")

    return DocumentRecord(
        id=document_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=content_type,
        file_size_bytes=file_size_bytes,
        status=status,
    )


async def fetch_document(document_id: int) -> DocumentRecord | None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, original_filename, stored_filename, content_type,
                   file_size_bytes, status
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        return None

    return DocumentRecord(
        id=row["id"],
        original_filename=row["original_filename"],
        stored_filename=row["stored_filename"],
        content_type=row["content_type"],
        file_size_bytes=row["file_size_bytes"],
        status=row["status"],
    )


async def update_document_status(document_id: int, status: str) -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            UPDATE documents
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, document_id),
        )
        await db.commit()


async def replace_document_pages(
    document_id: int,
    pages: list[dict[str, object]],
) -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("DELETE FROM document_pages WHERE document_id = ?", (document_id,))
        for page in pages:
            await db.execute(
                """
                INSERT INTO document_pages (
                    document_id,
                    page_number,
                    extracted_text,
                    source_type,
                    ocr_confidence,
                    is_unclear,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    page["page_number"],
                    page["text"],
                    page["source_type"],
                    page["ocr_confidence"],
                    1 if page["is_unclear"] else 0,
                    "processed",
                ),
            )
        await db.commit()


async def fetch_processed_pages(document_id: int) -> list[dict[str, object]]:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT page_number, extracted_text, source_type, ocr_confidence, is_unclear
            FROM document_pages
            WHERE document_id = ?
            ORDER BY page_number ASC
            """,
            (document_id,),
        )
        rows = await cursor.fetchall()

    return [
        {
            "page_number": row["page_number"],
            "text": row["extracted_text"] or "",
            "source_type": row["source_type"],
            "ocr_confidence": row["ocr_confidence"],
            "is_unclear": bool(row["is_unclear"]),
        }
        for row in rows
    ]


async def save_structured_fields(
    *,
    document_id: int,
    structured_fields: dict[str, object],
    method: str,
    warnings: list[str],
) -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            INSERT INTO document_structured_fields (
                document_id,
                fields_json,
                method,
                warnings_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(document_id) DO UPDATE SET
                fields_json = excluded.fields_json,
                method = excluded.method,
                warnings_json = excluded.warnings_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                document_id,
                json.dumps(structured_fields),
                method,
                json.dumps(warnings),
            ),
        )
        await db.commit()


async def delete_document_chunks(document_id: int) -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        await db.commit()


async def insert_chunks(
    document_id: int,
    chunks: list[dict[str, object]],
) -> list[dict[str, object]]:
    inserted: list[dict[str, object]] = []
    async with aiosqlite.connect(settings.sqlite_path) as db:
        for chunk in chunks:
            cursor = await db.execute(
                """
                INSERT INTO chunks (
                    document_id,
                    page_id,
                    chunk_index,
                    content,
                    embedding_id,
                    metadata_json
                )
                VALUES (?, NULL, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    chunk["chunk_index"],
                    chunk["content"],
                    chunk["embedding_id"],
                    json.dumps(chunk["metadata"]),
                ),
            )
            chunk_id = cursor.lastrowid
            if chunk_id is None:
                raise RuntimeError("Chunk insert did not return an id.")
            stored = dict(chunk)
            stored["chunk_id"] = chunk_id
            inserted.append(stored)
        await db.commit()
    return inserted


async def fetch_active_learning_rules() -> list[dict[str, object]]:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, rule_name, rule_description, rule_type
            FROM learning_rules
            WHERE is_active = 1
            ORDER BY created_at ASC
            """
        )
        rows = await cursor.fetchall()

    return [
        {
            "id": row["id"],
            "rule_name": row["rule_name"],
            "rule_description": row["rule_description"],
            "rule_type": row["rule_type"],
        }
        for row in rows
    ]


async def insert_draft(
    *,
    document_id: int,
    draft_type: str,
    content: str,
    evidence: list[dict[str, object]],
    model_name: str,
) -> int:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO drafts (
                document_id,
                draft_type,
                content,
                evidence_json,
                model_name
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                draft_type,
                content,
                json.dumps(evidence),
                model_name,
            ),
        )
        await db.commit()
        draft_id = cursor.lastrowid

    if draft_id is None:
        raise RuntimeError("Draft insert did not return an id.")
    return draft_id
