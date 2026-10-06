# Astronomy Knowledge Base Ingestion Pipeline (LightRAG POC)

## 概述
本项目为天文学中英双语知识库的 POC 摄入流水线，基于 [LightRAG (HKUDS)](https://github.com/HKUDS/LightRAG) 框架构建，严格遵循 `python-standard-layout` 与 `python-testing-standard`。

## 目标语料范围 ("The Deep Sky Companions" 丛书)
- `bilingual_output\book_Hidden Treasures (2007)`
- `bilingual_output\book_Southern Gems (2013)`
- `bilingual_output\book_The Caldwell Objects (2003)`
- `bilingual_output\book_The Messier Objects (1998)`
- `bilingual_output\book_The Secret Deep (2011)`

## 架构与核心特性
1. **云端 LLM 推理**：使用 MiniMax-M3 提取实体与关系，自动清洗 `<think>` 标签以避免 CoT 干扰结构化抽取。
2. **向量化**：对接 MiniMax `embo-01` 嵌入接口（1536 维），使用本地 NanoVectorDB 存储。
3. **断点续传与去重**：维护 `data/ingest_state.json` 状态记录，自动计算文件哈希，避免重复处理。
4. **统一日志规范**：日志同时输出到终端并归档至 `bilingual_output/lightrag_ingest_<timestamp>.log`。

## 运行指南

### 1. 安装依赖
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. 配置环境
在根目录配置 `.env`：
```env
LLM_API_KEY=your_minimax_api_key
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M3
```

### 3. 运行测试
```bash
pytest
```

### 4. 执行摄入流水线
```bash
python scripts/run_ingestion.py
```
