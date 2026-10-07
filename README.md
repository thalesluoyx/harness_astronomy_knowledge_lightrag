# Astronomy Knowledge Base Ingestion Pipeline (LightRAG POC)

## 概述
本项目为天文学中英双语知识库的 POC 摄入流水线，基于 [LightRAG (HKUDS)](https://github.com/HKUDS/LightRAG) 框架构建，严格遵循 `python-standard-layout` 和 `python-testing-standard`。

## 目标语料范围 ("The Deep Sky Companions" 丛书)
- `bilingual_output\book_Hidden Treasures (2007)`
- `bilingual_output\book_Southern Gems (2013)`
- `bilingual_output\book_The Caldwell Objects (2003)`
- `bilingual_output\book_The Messier Objects (1998)`
- `bilingual_output\book_The Secret Deep (2011)`

## 架构与核心特性
1. **云端 LLM 推理**：使用 MiniMax-M3 提取实体与关系，自动清洗 `<think>` 标签以避免 CoT 干扰结构化抽取。
2. **向量化**：对接 MiniMax `embo-01` 嵌入接口（1536 维），使用本地 NanoVectorDB 存储。
3. **断点续传与去重**：维护 `data/ingest_state.json` 状态记录，自动计算文件哈希，避免重复处理，确保原子级状态安全（若文档发生部分失败将自动清理缓存重新执行）。
4. **智能配额与退避系统**：
   - 自动跟踪 5 小时内 540 万 Token 的动态配额，在触及软限 (90%) 时安全熔断并休眠（*避免由于 Token 过载导致账号冻结*），并在刷新后自动唤醒。
   - 对 1002 RPM 频控及 402 余额不足等异常实现 Exponential Backoff 退避处理。
5. **统一日志规范**：日志同时输出到终端并归档至 `logs/lightrag_ingest_<timestamp>.log`。
6. **可视化 Web 监控看板**：
   - 自带一个交互式的 Web 看板服务，通过 SSE 长链接实时推送数据。
   - 精准追踪 LightRAG 内部的完整流水线阶段（阶段 1：文本切块实体抽取，阶段 2：跨切块实体消歧融合，阶段 3：embo-01 向量计算与落盘）。

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

# 可选：配置看板登录认证
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your_dashboard_password
```

### 3. 执行摄入流水线 (后台任务)
流水线将自动开始提取并在日志目录记录全量日志：
```bash
python scripts/run_ingestion.py
```

### 4. 启动可视化看板
```bash
python dashboard/server.py
```
启动后在浏览器打开 `http://localhost:7789`，即可查看全库处理进度测算、单本书细分阶段的实施进度以及流式的 Log 终端。

### 5. 运行测试
```bash
pytest
```
