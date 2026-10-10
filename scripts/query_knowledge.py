"""
scripts/query_knowledge.py
Interactive CLI for querying the Astronomy LightRAG Knowledge Base.
Supports hybrid, local, global, and naive search modes.
"""
import os
import sys
import asyncio
from pathlib import Path

# Add src to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from astronomy_lightrag.config import LIGHTRAG_WORKSPACE, DEFAULT_LLM_TIMEOUT
from astronomy_lightrag.llm import get_minimax_llm_func, get_minimax_embedding_func
from astronomy_lightrag.token_tracker import get_token_tracker

try:
    from lightrag import LightRAG, QueryParam
except ImportError:
    print("Error: lightrag is not installed. Please check environment.")
    sys.exit(1)


async def execute_query(rag: LightRAG, question: str, mode: str = "hybrid") -> str:
    """Executes a query against the LightRAG knowledge base."""
    param = QueryParam(mode=mode)
    response = await rag.aquery(question, param=param)
    return response


async def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    tracker = get_token_tracker()
    rag = LightRAG(
        working_dir=str(LIGHTRAG_WORKSPACE),
        llm_model_func=get_minimax_llm_func(tracker=tracker),
        embedding_func=get_minimax_embedding_func(tracker=tracker),
        default_llm_timeout=DEFAULT_LLM_TIMEOUT
    )
    
    print("\n" + "=" * 60)
    print("🔭 初始化天文学知识图谱检索系统 (LightRAG Astronomy Knowledge Base)...")
    print("=" * 60)
    await rag.initialize_storages()
    print("✅ 知识库加载完成！包含 15,490 实体、33,057 关系及 2,541 向量文本切块。\n")

    # If query provided via command-line arguments
    if len(sys.argv) > 1:
        query_text = " ".join(sys.argv[1:])
        mode = "hybrid"
        print(f"🔍 查询模式: [{mode}]")
        print(f"❓ 问题: {query_text}\n")
        print("⏳ 正在检索图谱与向量数据库并生成回答...")
        res = await execute_query(rag, query_text, mode=mode)
        print("\n" + "-" * 60)
        print("🌟 回答：\n")
        print(res)
        print("-" * 60 + "\n")
        return

    # Interactive REPL mode
    print("💡 模式提示: 输入您的问题并按回车。输入 'exit' 或 'quit' 退出。")
    print("💡 切换模式: 输入 ':mode hybrid|local|global|naive' (默认: hybrid)\n")

    current_mode = "hybrid"
    while True:
        try:
            prompt = input(f"\n[LightRAG:{current_mode}] > ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit", "q"]:
                print("👋 再见！")
                break
            if prompt.startswith(":mode"):
                parts = prompt.split()
                if len(parts) > 1 and parts[1].lower() in ["hybrid", "local", "global", "naive"]:
                    current_mode = parts[1].lower()
                    print(f"🔄 检索模式已切换为: {current_mode}")
                else:
                    print("⚠️ 支持的模式: hybrid (图谱+向量), local (实体细节), global (宏观总结), naive (纯向量)")
                continue

            print(f"⏳ 正在检索 [{current_mode}] 模式...")
            response = await execute_query(rag, prompt, mode=current_mode)
            print("\n" + "=" * 60)
            print(response)
            print("=" * 60)

        except (KeyboardInterrupt, EOFError):
            print("\n👋 退出会话。")
            break
        except Exception as e:
            print(f"\n❌ 查询发生错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
