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

## 本地开发

项目默认处于 `MOCK_LLM=true` 模式，不会下载或启动本地模型。前端、API、PostgreSQL 和 Redis 一次启动：

```bash
cp .env.example .env
docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build
```

打开 `http://127.0.0.1:5173`，API 健康检查为 `http://127.0.0.1:8000/api/health`。

首次空数据库需要导入政策和专业目录。真实 LLM 模式下先按“接入真实 LLM”完成预检；mock 模式可直接导入：

```bash
docker compose --env-file .env -f infra/compose/docker-compose.yml exec -T api python scripts/seed_real_policy.py
docker compose --env-file .env -f infra/compose/docker-compose.yml exec -T api python scripts/sync_official_minor_data.py
docker compose --env-file .env -f infra/compose/docker-compose.yml exec -T api python scripts/import_policy_sources.py
```

第二条命令会从南京大学本科生院官方链接下载 2025 版培养方案；服务器无法访问该链接时，先自行下载 PDF，再将文件传入容器并使用 `--pdf /path/to/file.pdf`。
第三条命令导入仓库内经审核的 2025 学生手册正文，并保留 2024 版为不可默认检索的历史档案；来源和去重依据见 [政策知识库来源清单](docs/policy-source-inventory.md)。

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

## 接入真实 LLM / Embedding

真实模式只使用你提供的外部 OpenAI 兼容接口，不安装 `sentence-transformers`、torch、CUDA 或 Ollama。聊天服务需兼容 Chat Completions，向量服务需兼容 `/embeddings`；二者可以是同一供应商，也可以使用不同密钥。

在服务器的 `.env.production`（本地开发则是 `.env`）中填写以下字段。`BASE_URL` 填到 `/v1`，不要填到 `/chat/completions` 或 `/embeddings`。

| 变量 | 作用 | 推荐填写方式 |
|------|------|-------------|
| `MOCK_LLM` | 开启真实模式 | `false` |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 聊天 API 地址、密钥、模型名 | 使用供应商给出的 OpenAI 兼容值 |
| `LLM_MAX_TOKENS` | 单次回答最大输出长度 | 默认 `600`，保持政策答复简洁并缩短等待 |
| `AGENT_RESPONSE_TIMEOUT_SECONDS` | 一次智能体请求的总时限 | 默认 `75`，必须小于 Nginx 的 `120` 秒读超时 |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_API_MODEL` | 向量 API 地址、密钥、模型名 | 可与聊天 API 独立 |
| `EMBEDDING_DIMENSION` | 数据库向量长度 | 固定为 `1024`，不可随意修改 |
| `EMBEDDING_API_DIMENSIONS` | 可选地传给兼容 API 的 `dimensions` 参数 | 供应商支持降维时填写 `1024`；不支持则填 `0` 并选择原生 1024 维模型 |

例如，百炼 `text-embedding-v4` 可设置 `EMBEDDING_API_DIMENSIONS=1024`。若服务返回的向量不是 1024 维，项目会明确失败，不会静默退回 hash 向量或写入错误数据。

配置完成、重启 API 后，按顺序执行：

```bash
# 只发送固定的连通性文本，不读取或写入用户数据，不输出密钥。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/check_external_llm.py

# 旧库从 mock 切换到真实 embedding 时必须执行；新库导入政策后执行一次也安全。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/reembed_documents.py

# 只有返回 200 / status=ready 才表示模型、向量和知识库已完整对齐。
curl -fsS http://127.0.0.1:8080/api/readiness
```

`check_external_llm.py` 会验证一次 embedding 的实际维度和一次聊天回复；失败时先修正地址、模型名、密钥权限或 `EMBEDDING_API_DIMENSIONS`，不要直接执行重建。

如需进一步确认每个面向用户的智能功能都能实际完成一次回答，可运行下列验收。它会对政策问答、个性化推荐、课程规划、伴学问答和职业探索各创建一个随机临时账号，读取完整 SSE 回答后自动删除该账号和临时岗位；不会读取、修改或输出真实用户数据和密钥。真实模型偶发冷启动较慢时，可按 `--intent` 单独重试。

```bash
# 依次验收全部五条智能链路。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/verify_real_llm_agents.py

# 只重试某一条链路。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/verify_real_llm_agents.py --intent policy
```

## 部署到自己的 Linux 服务器

### 1. 准备服务器

- 一台可运行 Docker Compose v2 的 Linux 服务器；建议至少 2 核、4 GB 内存和 20 GB 可用磁盘。
- 域名的 A/AAAA 记录指向服务器公网 IP；防火墙仅开放 `80` 和 `443`。PostgreSQL、Redis 和 API 不应暴露到公网。
- 服务器须能通过 HTTPS 访问你的 LLM/embedding 服务；首次同步时还须能访问南京大学官方培养方案链接。

### 2. 获取代码和生产配置

```bash
git clone https://github.com/jiahuizhong205/fxh-nju.git fuxiaohe
cd fuxiaohe
git checkout dev  # 发布稳定版本后可改为 main 或固定的提交号

cp .env.production.example .env.production
chmod 600 .env.production
```

编辑 `.env.production`：替换 `POSTGRES_PASSWORD`、LLM 和 embedding 的占位值。数据库密码请使用长随机字母数字串；该文件已被 Git 忽略，绝不要把它提交、复制到聊天记录或上传到仓库。

如果服务器从官方 PyPI 下载依赖很慢或超时，可在 `.env.production` 中把 `PIP_INDEX_URL` 改为你信任的区域镜像，并保留 `PIP_DEFAULT_TIMEOUT=300`、`PIP_RETRIES=5`。这些值只用于镜像构建阶段，不会传给应用；镜像源可用性和供应链风险由服务器维护者自行确认。

### 3. 启动生产服务

```bash
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml ps
```

生产 Compose 使用独立数据卷、关闭热重载和源码挂载；网页容器默认仅绑定服务器本机的 `127.0.0.1:8080`。API 会自动创建 pgvector/pg_trgm 扩展、表和已编号迁移，通知与同步 worker 会等 API 就绪后再启动。

如仅用于临时公网体验、不绑定域名和 HTTPS，可在 `.env.production` 明确设置 `WEB_BIND_ADDRESS=0.0.0.0`，并在云安全组和系统防火墙中放行 `APP_PORT`（例如 `8080`）。此模式的登录密码和对话内容通过明文 HTTP 传输，只适合短期、非敏感测试；正式使用应保持默认值并经由 HTTPS 反向代理暴露服务。

### 4. 初始化真实数据并验收

```bash
# 先确认真实聊天和向量接口可用。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/check_external_llm.py

# 写入 2021、2025 官方政策与培养方案，并以真实 embedding 建立索引。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/seed_real_policy.py
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/sync_official_minor_data.py

# 对全部切片重建一次，随后执行 API 级新用户验收（验收账号会自动删除）。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/reembed_documents.py
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/verify_user_journey.py --base-url http://api:8000
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T api python scripts/verify_real_llm_agents.py
curl -fsS http://127.0.0.1:8080/api/readiness
```

最后一条应返回 `status: ready`。验收脚本会覆盖注册、画像保存、头像回读、引导、推荐、课程规划、政策检索/问答、会话历史和学习进度；它只创建并删除随机临时账号，不触碰真实用户。

### 5. 绑定域名与 HTTPS

推荐让 Caddy 或 Nginx 在宿主机终止 TLS，再反向代理到 `127.0.0.1:8080`。以 Caddy 为例，Caddyfile 只有：

```caddyfile
your.domain.example {
    reverse_proxy 127.0.0.1:8080
}
```

替换域名后重载 Caddy。网页、REST API 和 SSE 问答均从同一域名访问；容器内的 Nginx 已禁用 SSE 缓冲，流式回答不会被攒到最后才输出。

### 日常更新与备份

```bash
# 更新代码并重建；不要使用 down -v，它会删除数据库卷。
git pull --ff-only origin dev
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml up -d --build

# 在升级前备份数据库。
docker compose --env-file .env.production -f infra/compose/docker-compose.prod.yml \
  exec -T postgres pg_dump -U fuxiaohe fuxiaohe > fuxiaohe-$(date +%F).sql
```

模型、embedding 模型或 `EMBEDDING_API_DIMENSIONS` 任一变更后，都必须先运行 `check_external_llm.py`，再运行 `reembed_documents.py`，最后确认 `/api/readiness` 返回 200。

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
