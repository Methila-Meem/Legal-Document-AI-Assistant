from app.services.chunking_service import ChunkingService


def test_chunking_preserves_page_metadata(monkeypatch) -> None:
    service = ChunkingService()
    service.target_chars = 120
    service.overlap_chars = 25
    text = (
        "Section one contains important legal terms. "
        "Section two contains more details about notice and payment. "
        "Section three contains the final obligations and remedies."
    )

    chunks = service.create_chunks(
        [
            {
                "page_number": 2,
                "text": text,
                "source_type": "pdf_text",
                "ocr_confidence": None,
                "is_unclear": False,
            }
        ]
    )

    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 2
    assert chunks[0].source_type == "pdf_text"
    assert all(chunk.content for chunk in chunks)


def test_chunking_skips_empty_pages() -> None:
    chunks = ChunkingService().create_chunks(
        [
            {
                "page_number": 1,
                "text": "   ",
                "source_type": "ocr",
                "ocr_confidence": 0.2,
                "is_unclear": True,
            }
        ]
    )

    assert chunks == []
