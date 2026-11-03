import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from astronomy_lightrag.harness.orchestrator import FullScaleOrchestrator

@pytest.fixture
def mock_orchestrator(tmp_path):
    workspace = tmp_path / "lightrag_workspace"
    workspace.mkdir()
    
    # Initialize mock orchestrator
    with patch("astronomy_lightrag.harness.orchestrator.get_book_registry", return_value={}), \
         patch("astronomy_lightrag.harness.orchestrator.get_checkpoint_manager"), \
         patch("astronomy_lightrag.harness.orchestrator.get_token_tracker"), \
         patch("astronomy_lightrag.harness.orchestrator.LightRAG"):
        orch = FullScaleOrchestrator(workspace_dir=workspace)
        orch.rag = MagicMock()
        orch.rag.doc_status_storage = MagicMock()
        orch.rag.doc_status_storage.delete = MagicMock()
        orch.rag.doc_status_storage.initialize = MagicMock()
        orch.rag.full_docs = MagicMock()
        orch.rag.full_docs.delete = MagicMock()
        orch.rag.full_docs.initialize = MagicMock()
        return orch

def test_clean_failed_doc_status_cleans_disk_and_memory(mock_orchestrator):
    """Verifies that _clean_failed_doc_status purges both disk JSON and memory storage."""
    ws = mock_orchestrator.workspace_dir
    ds_file = ws / "kv_store_doc_status.json"
    fd_file = ws / "kv_store_full_docs.json"

    # Seed disk data with a failed status and a processing status
    ds_file.write_text(json.dumps({
        "doc-1": {"file_path": "《Classic Telescopes》", "status": "failed"},
        "doc-2": {"file_path": "Classic Telescopes", "status": "processing"},
        "doc-other": {"file_path": "《Other Book》", "status": "completed"}
    }), encoding="utf-8")

    fd_file.write_text(json.dumps({
        "doc-1": {"content": "..."}
    }), encoding="utf-8")

    # Run clean
    mock_orchestrator._clean_failed_doc_status("《Classic Telescopes》", "book_057")

    # 1. Verify disk clean
    updated_ds = json.loads(ds_file.read_text(encoding="utf-8"))
    assert "doc-1" not in updated_ds, "Failed entry should be deleted from disk"
    assert "doc-2" not in updated_ds, "Processing entry should be deleted from disk"
    assert "doc-other" in updated_ds, "Unrelated completed entry must remain untouched"

    # 2. Verify in-memory storage sync calls
    mock_orchestrator.rag.doc_status_storage.delete.assert_called_once()
    deleted_keys = mock_orchestrator.rag.doc_status_storage.delete.call_args[0][0]
    assert "doc-1" in deleted_keys and "doc-2" in deleted_keys
    mock_orchestrator.rag.doc_status_storage.initialize.assert_called_once()
    mock_orchestrator.rag.full_docs.delete.assert_called_once()
    mock_orchestrator.rag.full_docs.initialize.assert_called_once()

def test_quarantine_queue_recording_and_skipping(mock_orchestrator, tmp_path, monkeypatch):
    """Verifies that quarantined books are tracked and skipped in future runs."""
    q_file = tmp_path / "data" / "quarantine_books.json"
    monkeypatch.setattr("astronomy_lightrag.harness.orchestrator.DATA_DIR", tmp_path / "data")

    assert not mock_orchestrator.is_book_quarantined("book_056")

    # Quarantine book_056
    mock_orchestrator._quarantine_book("book_056", "Twenty-Five Observations", "API Error")

    assert mock_orchestrator.is_book_quarantined("book_056")
    assert q_file.exists()
    q_data = json.loads(q_file.read_text(encoding="utf-8"))
    assert "book_056" in q_data
    assert q_data["book_056"]["attempts"] == 3
