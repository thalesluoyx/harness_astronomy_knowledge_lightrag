"""
Storage adapters and factory for LanceDB and SQLite.
"""
from .lancedb_vector import LanceDBVectorStorage
from .sqlite_graph import SQLiteGraphStorage
from .sqlite_kv import SQLiteKVStorage

__all__ = ["LanceDBVectorStorage", "SQLiteGraphStorage", "SQLiteKVStorage", "init_astronomy_storage_backends"]


def init_astronomy_storage_backends():
    """Registers LanceDB and SQLite storage implementations into LightRAG."""
    import lightrag.kg as kg
    import lightrag.kg.factory as factory

    if "SQLiteKVStorage" not in kg.STORAGE_IMPLEMENTATIONS["KV_STORAGE"]["implementations"]:
        kg.STORAGE_IMPLEMENTATIONS["KV_STORAGE"]["implementations"].append("SQLiteKVStorage")
    if "SQLiteGraphStorage" not in kg.STORAGE_IMPLEMENTATIONS["GRAPH_STORAGE"]["implementations"]:
        kg.STORAGE_IMPLEMENTATIONS["GRAPH_STORAGE"]["implementations"].append("SQLiteGraphStorage")
    if "LanceDBVectorStorage" not in kg.STORAGE_IMPLEMENTATIONS["VECTOR_STORAGE"]["implementations"]:
        kg.STORAGE_IMPLEMENTATIONS["VECTOR_STORAGE"]["implementations"].append("LanceDBVectorStorage")

    factory.STORAGES["SQLiteKVStorage"] = "astronomy_lightrag.storage.sqlite_kv.SQLiteKVStorage"
    factory.STORAGES["SQLiteGraphStorage"] = "astronomy_lightrag.storage.sqlite_graph.SQLiteGraphStorage"
    factory.STORAGES["LanceDBVectorStorage"] = "astronomy_lightrag.storage.lancedb_vector.LanceDBVectorStorage"

    orig_get_storage_class = factory.get_storage_class

    def custom_get_storage_class(storage_name: str):
        if storage_name == "LanceDBVectorStorage":
            return LanceDBVectorStorage
        if storage_name == "SQLiteGraphStorage":
            return SQLiteGraphStorage
        if storage_name == "SQLiteKVStorage":
            return SQLiteKVStorage
        return orig_get_storage_class(storage_name)

    factory.get_storage_class = custom_get_storage_class

    try:
        import lightrag.lightrag as lr
        lr.get_storage_class = custom_get_storage_class
    except Exception:
        pass
