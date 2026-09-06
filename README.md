# 福小禾 · 南大复合型人才学习助手

基于 LangGraph 多智能体 + RAG 的一站式跨学科成长助手，覆盖辅修政策答疑、专业推荐、课程规划、伴学辅导、职业探索全流程。

## 项目背景

项目面向南京大学本科生的跨学科学习场景。辅修选择通常涉及培养方案理解、课程冲突、校区安排和信息分散等问题，福小禾希望串联「决策—规划—学习—就业」流程。项目不再展示缺少可追溯来源的统计数字。

## 用户分层

| 分层 | 特征 | 核心需求 |
|------|------|---------|
| 核心辅修用户 | 大二/大三，有明确辅修计划 | 无冲突课表、难度评估、复合岗位查询 |
| 观望意向用户 | 大一/大二，有想法无决策 | 方向匹配、投入回报判断、低风险试错 |
| 自学轻量用户 | 全年级，不需证书 | 模块化知识树、自学资源整合 |
| 无需求新生 | 大一，未接触辅修 | 大类分流、专业分流政策查询 |

## 核心功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 辅修政策答疑 | 自然语言问答，按年份/专业检索政策条款，逐条引用原文 | ✅ |
| 辅修专业推荐 | 画像采集 → 硬门槛过滤 → 多指标评分 → 推荐报告 | ✅ |
| 个性化课程规划 | 规则引擎排课，解决时间冲突/跨校区通勤 | ✅ |
| 复合方向伴学 | 双模式（在校辅修/独立自学），智能讲解（知识树可视化待做） | ✅ |
| 职业方向探索 | 复合背景岗位匹配，简历优化建议 | ✅ |
| 账号体系 | 用户名+密码注册登录，每用户独立画像 | ✅ |

## 架构概览

```
用户 → Vue3 前端 → FastAPI SSE → LangGraph 根图
                                      ├── Policy Agent (RAG)
                                      ├── Recommendation Agent
                                      ├── Course Planning Agent
                                      ├── Tutor Agent
                                      └── Career Agent
                                      ↑
                              MCP 工具层 / Search Agent / Docker 沙箱
```

**关键设计决策：**

- **证据优先**：政策与岗位结论必须关联可回溯来源、版本和抓取时间
- **确定性优先**：学分、先修、时间冲突、校区通勤由规则引擎处理，不靠 LLM
- **分层可信**：S 级（校级正式政策）→ A 级（院系文件）→ B 级（企业官网）→ C 级（社区经验）
- **RAG 与 Search 分离**：受治理知识走 RAG，高时效网页检索走独立 Search Agent
- **先模块化单体后拆分**：MVP 单进程部署，Search/Sandbox 因安全边界独立

## 技术栈

| 层 | 组件 |
|---|------|
| 前端 | Vue 3 + Vite + TypeScript + Pinia |
| 后端 | Python 3.12 + FastAPI + LangGraph 1.x |
| 向量库 | PostgreSQL 16 + pgvector |
| 向量服务 | 可配置的外部 OpenAI 兼容 Embedding API（不安装本地模型） |
| 编排 | LangGraph StateGraph + 子图 + SSE Streaming |
| 任务 | Celery/Dramatiq + Redis |
| 隔离 | Docker 沙箱（代码执行/文档解析/浏览器） |
| 图数据库 | Neo4j（知识图谱，P1 阶段） |

## 快速开始

```bash
# 1. 启动基础设施
cd infra/compose
docker compose up -d postgres redis

# 2. 安装依赖
pip install -r requirements.txt

# 3. 同步南京大学官方辅修培养方案（也可通过 --pdf 使用已下载文件）
PYTHONPATH=. python scripts/sync_official_minor_data.py

# 4. 启动后端 (默认 MOCK_LLM=true 走 mock，无需 LLM；接真实 LLM 见下文)
uvicorn apps.api.main:app --reload --port 8000

# 5. 启动前端
cd apps/web && npm install && npm run dev
```

### 可选：启动通知 worker

通知 worker 负责按账号生成到期学习提醒、重试验证码投递，并投递已经入队的外部通知。未配置
`NOTIFICATION_PROVIDER_URL` 时不会访问外部网络，外部通知会保持 `queued`，因此
mock 开发不需要短信、邮件或本地大模型。

```bash
PYTHONPATH=. python scripts/notification_worker.py
```

Docker Compose 已包含同一个 `notification-worker` 服务；如需接入自有 webhook
供应商，可在 `.env` 中配置 `NOTIFICATION_PROVIDER_URL`、可选的
`NOTIFICATION_PROVIDER_API_KEY` 和 `NOTIFICATION_WORKER_INTERVAL_SECONDS`。验证码
投递使用 `VERIFICATION_PROVIDER_URL` 与可选的 `VERIFICATION_PROVIDER_API_KEY`，失败
后最多按退避规则重试 3 次。provider 返回 `message_id` 后，可向
`/api/v1/auth/verification/provider-callback` 携带 `X-Verification-Provider-Secret`
回传 `delivered`、`failed` 等状态，服务端会更新对应投递记录。

反馈附件默认使用本地文件签名校验和数据库存储。生产环境可配置
`FEEDBACK_SCAN_URL`（扫描 gateway 接收 multipart 字段 `file`，返回
`{"clean": true}` 或 `{"status": "clean"}`）以及 `FEEDBACK_STORAGE_URL`
（上传后返回 `{"key": "..."}`，下载时使用同一地址加 key）；两者均可配对应的
`*_API_KEY`。任一服务不可用时，接口会拒绝本次附件，不会留下半成品记录。

数据同步默认只保留本地快照与检查点。生产环境可配置 `SYNC_PROVIDER_URL` 和可选的
`SYNC_PROVIDER_API_KEY`，调用 `/api/v1/sync/provider/push` 或启动 Compose 中的
`sync-worker` 将脱敏快照推送到云端。provider 可在响应中返回另一端快照，服务端会把它
交给前端继续走“预览/确认导入”，不会未经确认覆盖本地数据；`SYNC_WORKER_INTERVAL_SECONDS`
控制自动推送周期。也可调用 `/api/v1/sync/provider/pull` 主动获取远端快照；正式冲突
合并仍通过现有 `/api/v1/sync/import` 的确认流程完成，可选择默认的 `remote_wins`
或保留本地数据的 `keep_local` 策略。

## 接入真实 LLM / Embedding（可选）

默认 `MOCK_LLM=true`，后端对问答走 mock 回复，且不会加载本地模型；无需任何 LLM 或外部服务即可跑通画像、推荐、课程规划、落库和安全策略。真实问答需要分别配置聊天与向量接口，项目不会安装 `sentence-transformers`、torch、CUDA 或 Ollama。

| 变量 | 含义 | 示例（硅基流动） |
|------|------|------------------|
| `LLM_BASE_URL` | OpenAI 兼容端点 | `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | 对话模型 | `Qwen/Qwen2.5-7B-Instruct` |
| `LLM_API_KEY` | API Key | `sk-...` |
| `EMBEDDING_BASE_URL` | 独立向量端点 | provider 的 OpenAI 兼容地址 |
| `EMBEDDING_API_KEY` | 向量 API Key | 可与聊天 Key 相同，也可不同 |
| `EMBEDDING_API_MODEL` | 向量模型 | `BAAI/bge-m3` |
| `EMBEDDING_DIMENSION` | pgvector 维度 | 当前固定为 `384` |
| `MOCK_LLM` | 关闭 mock | `false` |

> 对话与向量服务独立配置。当前数据库向量列为 384 维，必须选择直接返回 384 维的模型/接口；维度不符时系统会明确报错，不会静默使用伪向量。

配置完成后先执行 `PYTHONPATH=. python scripts/reembed_documents.py` 重建知识库向量，再访问 `/api/readiness`；只有模型配置完整且全部文档使用当前向量签名时，真实模式才会返回 ready。

## 项目结构

```
fuxiaohe/
├── apps/
│   ├── api/                # FastAPI BFF / REST / SSE
│   │   ├── routes/         # chat, knowledge 路由
│   │   ├── models.py       # ORM 模型
│   │   └── config.py       # 配置
│   └── web/                # Vue 3 前端
│       └── src/
│           ├── api/        # SSE 客户端
│           ├── stores/     # Pinia 状态
│           ├── views/      # 页面
│           └── components/ # 组件
├── services/
│   ├── agent_runtime/      # LangGraph 根图 + 子图代理
│   │   ├── graph.py        # 根图编排
│   │   ├── policy_agent.py # 政策答疑子图
│   │   └── state.py        # 状态定义
│   └── rag/                # 检索增强生成
│       ├── retrieval.py    # 混合检索（向量+全文）
│       └── ingestion.py    # 文档摄取
├── packages/contracts/     # 共享 Pydantic 模型
├── infra/                  # Docker Compose / 迁移 / 部署
├── scripts/                # 种子数据 / 验证脚本
└── docs/                   # 需求与架构文档
```

## 验证

```bash
PYTHONPATH=. python scripts/verify_core.py
```

## 持续集成与分支规范

每次 push 到任意分支，GitHub Actions 会自动跑自测（见 `.github/workflows/ci.yml`）：

- **后端**：`pip install` + `PYTHONPATH=. python scripts/verify_core.py`（无需数据库、无需 LLM）
- **前端**：`npm ci` + `npm run build`（vue-tsc 类型检查 + vite 构建）

分支规范：`dev` 为开发主分支，`main` 为受保护主干，**更新只允许从 `dev` 合并到 `main`**（PR 流程），禁止直接 push 到 `main`。

## 团队

管泽昊、仲嘉辉、叶颖、张佳怡
