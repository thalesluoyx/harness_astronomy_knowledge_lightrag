import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from lightrag.lightrag import DocStatus

@pytest.fixture
def mock_bilingual_dir(tmp_path):
    """Creates a mock bilingual_output directory mimicking real directory structures."""
    base_dir = tmp_path / "bilingual_output"
    base_dir.mkdir()

    # Books with nested auto/ directories (matching production structure)
    books = [
        "book_Hidden Treasures (2007)",
        "book_Southern Gems (2013)",
        "book_Unrelated Book (9999)"
    ]

    for book in books:
        book_dir = base_dir / book
        book_dir.mkdir()
        if "Unrelated" not in book:
            auto_dir = book_dir / book / "auto"
            auto_dir.mkdir(parents=True)
            md_file = auto_dir / f"{book}_bilingual.md"
            md_file.write_text("# Chapter 1\nStars and clusters.\n恒星与星团。", encoding="utf-8")

            # Non-target files
            (book_dir / "pipeline.log").write_text("dummy log", encoding="utf-8")

    return base_dir

@pytest.fixture
def mock_state_file(tmp_path):
    return tmp_path / "data" / "ingest_state.json"

@pytest.fixture
def mock_rag():
    """Mocks the LightRAG instance with async ainsert and aget_docs_by_track_id."""
    rag = AsyncMock()
    rag.ainsert = AsyncMock(return_value="track_mock_123")

    mock_doc = MagicMock()
    mock_doc.status = DocStatus.PROCESSED
    mock_doc.chunks_count = 10
    rag.aget_docs_by_track_id = AsyncMock(return_value={"doc-mock-id": mock_doc})

    # Mock doc_status storage
    mock_ds = MagicMock()
    mock_ds.get_docs_by_statuses = AsyncMock(return_value={})
    mock_ds.delete = AsyncMock()
    rag.doc_status = mock_ds

    return rag
