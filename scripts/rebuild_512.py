import asyncio
import os
import shutil
import sys
sys.path.insert(0, "src")
from astronomy_lightrag.local_embedding import get_local_embedding_func
from astronomy_lightrag.llm import get_minimax_llm_func
from lightrag import LightRAG
from lightrag.tools.rebuild_vdb import rebuild_entities_vdb, rebuild_relationships_vdb, rebuild_chunks_vdb
from lightrag.tools.rebuild_vdb import rebuild_entities_vdb, rebuild_relationships_vdb, rebuild_chunks_vdb

async def main():
    workspace = "lightrag_workspace"
    print(f"Initializing LightRAG on {workspace} with 512-dim BAAI embeddings...")
    from lightrag.utils import EmbeddingFunc
    rag = LightRAG(
        working_dir=workspace,
        llm_model_func=get_minimax_llm_func(),
        embedding_func=EmbeddingFunc(
            embedding_dim=512,
            max_token_size=8192,
            func=get_local_embedding_func()
        ),
    )
    await rag.initialize_storages()
    
    config = rag._build_global_config()
    
    print("Rebuilding Entities...")
    await rebuild_entities_vdb(rag.chunk_entity_relation_graph, rag.entities_vdb, config, batch_size=50)
    
    print("Rebuilding Relationships...")
    await rebuild_relationships_vdb(rag.chunk_entity_relation_graph, rag.relationships_vdb, config, batch_size=50)
    
    print("Rebuilding Chunks...")
    await rebuild_chunks_vdb(rag.text_chunks, rag.chunks_vdb, batch_size=50)
    
    print("Rebuild complete!")

if __name__ == "__main__":
    asyncio.run(main())
