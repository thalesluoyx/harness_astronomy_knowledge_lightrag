import pytest
from pathlib import Path
from unittest.mock import MagicMock
from lightrag.lightrag import DocStatus
from astronomy_lightrag.ingestor import (
    discover_files,
    load_state,
    save_state,
    get_file_hash,
    run_ingestion_pipeline
)

def test_discover_files_scoped_and_recursive(mock_bilingual_dir):
    """Verifies that only target books are scanned and nested auto/*.md files are found."""
    target_books = ["book_Hidden Treasures (2007)", "book_Southern Gems (2013)"]
    files = discover_files(mock_bilingual_dir, target_books)

    assert len(files) == 2
    filenames = [f.name for f in files]
    assert "book_Hidden Treasures (2007)_bilingual.md" in filenames
    assert "book_Southern Gems (2013)_bilingual.md" in filenames
    assert not any("Unrelated" in str(f) for f in files)

def test_state_persistence_crud(mock_state_file):
    """Verifies state loading and atomic saving."""
    assert load_state(mock_state_file) == set()

    save_state("book1.md", "hash_abc", mock_state_file)
    assert load_state(mock_state_file) == {"book1.md"}

    save_state("book2.md", "hash_def", mock_state_file)
    assert load_state(mock_state_file) == {"book1.md", "book2.md"}

def test_file_hash_computation(tmp_path):
    f = tmp_path / "sample.md"
    f.write_text("Astronomical Data", encoding="utf-8")
    h1 = get_file_hash(f)
    assert len(h1) == 32

    f.write_text("Changed Data", encoding="utf-8")
    h2 = get_file_hash(f)
    assert h1 != h2

@pytest.mark.asyncio
async def test_run_ingestion_pipeline_skips_processed(mock_bilingual_dir, mock_state_file, mock_rag):
    """Verifies pipeline processes new files and skips previously processed ones."""
    target_books = ["book_Hidden Treasures (2007)", "book_Southern Gems (2013)"]

    # Run 1: Should ingest both files
    await run_ingestion_pipeline(
        rag_instance=mock_rag,
        base_dir=mock_bilingual_dir,
        state_file=mock_state_file,
        target_books=target_books
    )
    assert mock_rag.ainsert.call_count == 2
    state = load_state(mock_state_file)
    assert len(state) == 2

    # Run 2: Re-run should skip all already processed files
    mock_rag.ainsert.reset_mock()
    await run_ingestion_pipeline(
        rag_instance=mock_rag,
        base_dir=mock_bilingual_dir,
        state_file=mock_state_file,
        target_books=target_books
    )
    assert mock_rag.ainsert.call_count == 0

@pytest.mark.asyncio
async def test_run_ingestion_pipeline_does_not_save_failed_docs(mock_bilingual_dir, mock_state_file, mock_rag):
    """Verifies that if a document has FAILED status, it is NOT marked in state."""
    target_books = ["book_Hidden Treasures (2007)"]

    # Mock failed status
    failed_doc = MagicMock()
    failed_doc.status = DocStatus.FAILED
    failed_doc.chunks_count = 5
    mock_rag.aget_docs_by_track_id.return_value = {"doc-fail-id": failed_doc}

    await run_ingestion_pipeline(
        rag_instance=mock_rag,
        base_dir=mock_bilingual_dir,
        state_file=mock_state_file,
        target_books=target_books
    )

    state = load_state(mock_state_file)
    # Must NOT be marked in state
    assert len(state) == 0
