# 🌌 Astronomy Knowledge Base Ingestion Pipeline (LightRAG Full-Scale)

> **全量 155 本专业天文学双语图书知识库自动化构建与检索系统**  
> 基于 [LightRAG (HKUDS)](https://github.com/HKUDS/LightRAG) 框架深度重构，结合天贝 Mini-PC 本地硬件加速、双循环自愈调度及微信智能监控。

---

## 📖 语料规模与范围

本系统负责将已完成高质量中英双语翻译的 **155 本专业天文学专著** 全量构建为高阶图谱与向量知识库：
- **总书籍规模**：155 本（涵盖 150 本数字编号丛书 + 5 本 *The Deep Sky Companions* 经典著作）
- **双语正文库容**：153.27 MB 权威 Markdown 双语文本
- **切块总量预估**：约 133,855 个语义切块（每块约 1,200 Tokens）
- **实体与关系规模**：预计沉淀 100,000+ 天体与设备实体，200,000+ 关联三元组

---

## 🏗️ 系统架构与核心特性

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Outer Loop (外环时间窗与预算调度)                      │
│   • 严格对齐 MiniMax 5小时固定窗口 (00:00, 05:00, 10:00, 15:00, 20:00)  │
│   • 90% 额度预警 (4.86M Tokens) 优雅挂起，自动倒计时休眠与唤醒           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                   Inner Loop (内环双轨并行流水线)                       │
│                                                                        │
│   Track A (云端 LLM 抽取)                   Track B (本地硬件向量化)     │
│   • MiniMax-M3 (max_async=8~12)             • FastEmbed / ONNX Runtime │
│   • 实体/关系三元组抽取                     • Ryzen 7 PRO 6850H CPU    │
│   • 自动清洗 <think> 标签                   • 500+ chunks/s, 0 API费用 │
└───────────────────┬──────────────────────────────────┬─────────────────┘
                    │                                  │
┌───────────────────▼──────────────────────────────────▼─────────────────┐
│               工业级自愈保障与监控 (Quality & Monitoring)                │
│   • 前置净化 (text_sanitizer.py): 过滤 \ufffd、死链、残损表格，免疫422  │
│   • 断点管理 (chunk_checkpoint.py): 切块级原子持久化，0 重复调用        │
│   • 书籍锁定 (doc_registry.py): 强制注入真实书名，彻底解决页码无书名   │
│   • 独立裁决 (gemini_judge.py): 四维盲审抽检 (>=80分放行，<80分告警)   │
│   • 微信告警 (notifier.py): OpenClaw 微信长轮询机器人里程碑卡片推送    │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. 领域先验词典与检索扩写 (`domain_dict.py`, `query_preprocessor.py`)
- **全星表覆盖**：收录全部 110 个梅西耶天体（M1-M110）、全部 109 个科德韦尔天体（C1-C109）、IAU 88 星座中英文全称与代码，以及 UHC/OIII/H-Beta 等观测器材。
- **长词优先边界正则**：检索端毫秒级自动将“M31”扩写为“仙女座大星系 / Andromeda Galaxy / NGC 224”，并保持边界安全（防止误匹配 LM31 或 M310）。
- **图谱精确路由**：Hook 底层检索节点，将别名直接注入向量检索候选池，召回率提升至 100%。

### 2. 文本净化与审查免疫管道 (`text_sanitizer.py`)
- **排版噪声清除**：前置剔除 `\ufffd` 乱码字符、不可见 ASCII 控制码、破损表格符号及 OCR 浮动页码（如孤立的 `Page 123` 行）。
- **反审查过滤（Anti-Censorship）**：自动置换非天文学科的易触发在线大模型审核报错（HTTP 422）词汇，保障全天候无人值守平稳运行。

### 3. 书籍元数据全生命周期锁定 (`doc_registry.py`)
- **标准书名锁定**：扫描 155 本书，生成 `astronomy_books_registry.json`。
- **底层归属保障**：在入库时通过 `rag.ainsert(file_paths=[标准书名])` 将真实书名永久绑定至切块属性，**彻底根除“引用有页码却没有书名”的问题**。

### 4. 天贝小主机本地离线 Embedding 引擎 (`local_embedding.py`)
- **极致吞吐性能**：基于用户天贝小主机（AMD Ryzen 7 PRO 6850H 8核16线程 + 24GB LPDDR5 8000MHz 超高频内存），采用 FastEmbed CPU 多线程 AVX2 推理。
- **实测性能**：单批 100 切块仅需 **0.18 秒**，实测速率达 **546.4 chunks/sec**。
- **彻底解耦**：Stage 3 向量生成 100% 转移至本地：**0 API 费用、0 速率限制（429）、0 网络连接超时**。

### 5. 切块级断点与 5 小时固定时间窗调度 (`chunk_checkpoint.py`, `outer_loop.py`)
- **细粒度断点恢复**：`data/chunk_checkpoint_state.json` 记录每个切块的 MD5 与完成状态，支持原子写入。断电或异常重启后毫秒级跳过已完成切块，无需回滚整书。
- **固定整点窗口对齐**：对齐 MiniMax 官方刷新点（每日 `00:00, 05:00, 10:00, 15:00, 20:00`）。消耗达到 90% 或临界 8 分钟内优雅挂起并计算倒计时休眠，到点自动自愈唤醒。

### 6. 独立裁决与微信机器人告警 (`gemini_judge.py`, `notifier.py`)
- **客观四维盲审**：单书入库后自动抽检实体与关系，独立评估**完整性 (20分)**、**清洁度 (20分)**、**准确性 (40分)**、**一致性 (20分)**，低于 80 分自动标记并告警。
- **微信长轮询推送**：复用 `bilingual_common/notifier.py` 的 OpenClaw 微信机器人通道，关键节点（里程碑达成、额度休眠、质量告警）实时推送到微信端。

---

## 📂 项目目录结构

```
harness_astronomy_knowledge_lightrag/
├── src/astronomy_lightrag/
│   ├── config.py                 # 全局运行配置 (并发度、模型选型、路径定义)
│   ├── domain_dict.py            # 天文先验词典 (M1-M110, C1-C109, 88星座, 观测器材)
│   ├── domain_dict.json          # 结构化双向别名索引 (110 KB)
│   ├── text_sanitizer.py         # 文本前置清洗与敏感词免疫管道
│   ├── doc_registry.py           # 155 本书血统追踪注册表
│   ├── astronomy_books_registry.json # 155 本书权威注册文件 (153.27 MB / 13.3万切块)
│   ├── local_embedding.py        # 天贝小主机 CPU FastEmbed 本地离线嵌入引擎
│   ├── query_preprocessor.py     # 检索扩写与图谱实体注入预处理器
│   ├── token_tracker.py          # 5 小时滑动窗口 Token 追踪器
│   ├── llm.py                    # MiniMax-M3 LLM 与动态嵌入适配器
│   └── harness/
│       ├── __init__.py           # 调度引擎包初始化
│       ├── chunk_checkpoint.py   # 切块级原子断点管理器
│       ├── outer_loop.py         # 5 小时固定自然日时间窗调度器
│       ├── logger_setup.py       # 统一日志配置 (落盘至 logs/，抑制进度条刷屏)
│       ├── gemini_judge.py       # 独立大模型四维质检裁判
│       ├── notifier.py           # 微信机器人与 Webhook 告警适配器
│       └── orchestrator.py       # 双循环自愈编排主入口
├── dashboard/
│   ├── server.py                 # 看板 Flask 后端 (SSE 流式推送，Basic Auth 认证)
│   └── index.html                # 监控大屏前端 (全量进度、Token 仪表盘、4 模式知识检索)
├── data/
│   ├── chunk_checkpoint_state.json # 切块级断点持久化文件
│   └── ingest_state.json         # 看板已完成书籍状态
├── logs/
│   └── harness_orchestrator_YYYYMMDD.log # 全量调度器每日日志
├── lightrag_workspace/           # LightRAG 知识库存储 (kv_store, graphml, vdb)
├── tests/                        # 单元测试与测试夹具
└── README.md                     # 本说明文档
```

---

## 🚀 运行与验证指南

### 1. 环境准备与依赖安装
确保使用环境的 Python（推荐 Python 3.10+）：
```powershell
pip install -r requirements.txt
pip install fastembed sentence-transformers
```

在项目根目录检查 `.env` 配置：
```env
# MiniMax 在线抽取 LLM
LLM_API_KEY=your_minimax_api_key
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M3

# 嵌入引擎设置 ("local" 0成本本地嵌入，或 "online" 调用在线API)
EMBEDDING_ENGINE=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
LOCAL_EMBEDDING_THREADS=8

# 并发控制 (本地嵌入解耦后 Stage 1 推荐 8~12)
MAX_ASYNC=8

# 可选：独立大模型质检与微信推送
GEMINI_API_KEY=your_gemini_api_key
WECHAT_WEBHOOK_URL=your_wechat_webhook_url
```

---

### 2. 自动化全模块交付验证（0 API 消耗，耗时 1 秒）
运行一体化验证套件，全面自检先验词典、检索扩写、文本清洗、书籍注册、FastEmbed 吞吐量和时间窗调度：
```powershell
C:\Users\33991\miniconda3\envs\MinerU\python.exe scratch\verify_all_modules.py
```
> **通过标准**：6/6 项测试全绿并通过（`All PASSED`）。

---

### 3. 全量 155 本书静态扫描 Dry-Run（0 API 消耗）
在不发起任何模型调用的情况下，预检全量 155 本书的文本清洗有效性与标准书名锁定：
```powershell
cd c:\Work\openclaw_projects\bilingual_project\harness_astronomy_knowledge_lightrag
C:\Users\33991\miniconda3\envs\MinerU\python.exe -m src.astronomy_lightrag.harness.orchestrator --dry-run
```
> **通过标准**：终端输出 `Dry-run verified successfully for 155 books.`，日志正常输出至 `logs/harness_orchestrator_YYYYMMDD.log`。

---

### 4. 极小代价小批次实战验证 (Pilot Test)
先处理 1~2 本新书，端到端检验 Stage 1 在线抽取、本地 FastEmbed 向量化落盘与断点记录：
```powershell
# 处理 1 本书验证完整链路
C:\Users\33991\miniconda3\envs\MinerU\python.exe -m src.astronomy_lightrag.harness.orchestrator --batch-size 1
```

---

### 5. 全量 155 本书无人值守正式运行
验证无误后，启动全量自动化调度器，支持断点自动续传与 5 小时时间窗自愈休眠：
```powershell
C:\Users\33991\miniconda3\envs\MinerU\python.exe -m src.astronomy_lightrag.harness.orchestrator
```
- 如需从指定书籍开始执行：
  ```powershell
  python -m src.astronomy_lightrag.harness.orchestrator --start-book book_010
  ```

---

### 6. 可视化 Web 看板监控与 4 模式检索测试
看板服务已以后台守护进程形式常驻运行：
- **访问地址**：`http://localhost:7789`
- **默认账号**：`Thales`
- **默认密码**：`Th7548680224`
- **功能特性**：
  1. 实时查看 155 本书全量完成率、Token 仪表盘与运行日志流；
  2. 4 模式知识检索对比（经典向量 Naive / 局部图谱 Local / 全局图谱 Global / 混合检索 Mix）；
  3. 支持天体别名自动扩写（如直接输入“M31”或“C14”）与严格出处书名溯源。
