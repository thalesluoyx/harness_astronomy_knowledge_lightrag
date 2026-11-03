"""
test_storage_parity.py
Parity and functionality tests for LanceDB vector storage and SQLite graph/KV backends.
"""
import pytest
import sqlite3
import lancedb
from pathlib import Path

from astronomy_lightrag.config import LIGHTRAG_WORKSPACE_LANCEDB, EMBEDDING_ENGINE
from astronomy_lightrag.storage.lancedb_vector import LanceDBVectorStorage
from astronomy_lightrag.storage.sqlite_graph import SQLiteGraphStorage
from astronomy_lightrag.storage.sqlite_kv import SQLiteKVStorage
from astronomy_lightrag.llm import get_astronomy_embedding_func


@pytest.fixture(scope="module")
def ws_dir():
    assert LIGHTRAG_WORKSPACE_LANCEDB.exists(), "LanceDB workspace directory does not exist"
    return LIGHTRAG_WORKSPACE_LANCEDB


def test_lancedb_tables_exist_and_counts(ws_dir):
    db = lancedb.connect(str(ws_dir / "lancedb_store"))
    tables = db.table_names() if hasattr(db, "table_names") else db.list_tables()
    assert "chunks" in tables
    assert "entities" in tables
    assert "relationships" in tables

    assert db.open_table("chunks").count_rows() == 39692
    assert db.open_table("entities").count_rows() == 313608
    assert db.open_table("relationships").count_rows() == 703323


def test_sqlite_graph_counts(ws_dir):
    conn = sqlite3.connect(str(ws_dir / "astronomy_graph.db"))
    cur = conn.cursor()
    n_nodes = cur.execute("SELECT count(*) FROM nodes").fetchone()[0]
    n_edges = cur.execute("SELECT count(*) FROM edges").fetchone()[0]
    conn.close()

    assert n_nodes == 313608
    assert n_edges == 703323


def test_sqlite_kv_counts(ws_dir):
    conn = sqlite3.connect(str(ws_dir / "astronomy_kv.db"))
    cur = conn.cursor()
    n_cache = cur.execute("SELECT count(*) FROM kv_store WHERE namespace='llm_response_cache'").fetchone()[0]
    conn.close()

    assert n_cache >= 133976


@pytest.mark.asyncio
async def test_sqlite_graph_operations(ws_dir):
    graph = SQLiteGraphStorage(
        namespace="astronomy_graph",
        workspace="",
        global_config={"working_dir": str(ws_dir)},
        embedding_func=None
    )

    has_m42 = await graph.has_node("M42")
    assert has_m42 is True

    deg = await graph.node_degree("M42")
    assert deg > 100

    node_data = await graph.get_node("M42")
    assert node_data is not None
    assert "description" in node_data
    assert len(node_data["description"]) > 10


@pytest.mark.asyncio
async def test_lancedb_vector_query(ws_dir):
    vdb = LanceDBVectorStorage(
        namespace="entities",
        workspace="",
        global_config={
            "working_dir": str(ws_dir),
            "vector_db_storage_cls_kwargs": {"cosine_better_than_threshold": 0.2}
        },
        embedding_func=get_astronomy_embedding_func(engine_type=EMBEDDING_ENGINE)
    )

    res = await vdb.query("M42 猎户座大星云", top_k=3)
    assert len(res) > 0
    assert any("M42" in r.get("entity_name", "") or "猎户" in r.get("entity_name", "") for r in res)


@pytest.mark.asyncio
async def test_sqlite_kv_operations(ws_dir):
    kv = SQLiteKVStorage(
        namespace="text_chunks",
        workspace="",
        global_config={"working_dir": str(ws_dir)},
        embedding_func=None
    )

    is_empty = await kv.is_empty()
    assert is_empty is False

    chunk = await kv.get_by_id("doc-1b0ce47e5c2117b34f98510c0f67d5d9-chunk-000")
    assert chunk is not None
    assert "content" in chunk
