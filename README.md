# RepoMind

## 本地认证

业务接口（知识库、文档、任务、索引、问答、日志、反馈和评测）均要求 Bearer JWT；`/health`、`/ready` 与 `POST /auth/token` 保持公开。首次本地初始化可执行：

```powershell
.venv\Scripts\python.exe scripts\bootstrap_local_auth.py
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

服务第一次启动时会根据本地 `.env` 的 `BOOTSTRAP_ADMIN_*` 创建管理员。管理员用户名与随机生成的密码只保存在已忽略的 `.env` 中；不要提交、截图或粘贴它们。登录、Swagger 授权和重置说明见 [本地认证说明](docs/auth_setup.md)。

RepoMind 是面向后端项目文档的知识库服务。它将分散的 README、接口说明、部署文档等资料变成可管理、可检索、可追溯的问答数据源，降低新人熟悉项目、定位接口规则和复核回答依据的成本。

已完成一次固定公开语料的真实检索评测：7 份 MIT 许可的 FastAPI 模板文档、210 个索引片段、15 条人工标注问题，Top-1 命中 11/15（73.3%）、Recall@8 命中 15/15（100%）、MRR 0.8556；同时用 Ragas 的文档级 ID-based Context Precision/Recall 得到 0.2578/1.0000。完整来源、方法与限制见 [评测报告](docs/evaluation_report.md)；这些指标仅衡量该固定语料上的检索与上下文排序，不是生产数据或通用能力结论。

当前版本已完成 P0–P5：文档处理、混合检索、问答闭环、JWT 认证与工程化交付。项目的功能边界、技术选择和简历表述均以实际运行与测试证据为准。

详细图示见 [架构与数据流](docs/architecture.md)。

## 解决的问题

| 痛点 | RepoMind 的处理方式 |
| --- | --- |
| 项目文档分散，靠关键词难以定位上下文 | 以知识库、文档、分段三层管理资料，并建立关键词与向量索引 |
| 回答无法说明依据 | 返回文档片段引用，并保存候选、得分、耗时与问答记录 |
| 检索结果难复盘、难评测 | 保存关键词/向量候选、RRF 融合和确定性重排序结果；支持人工题集评测与 Ragas 上下文指标 |
| 线上问题难观察 | 请求使用脱敏结构化日志；问答记录保留检索阶段耗时；支持匿名有用/无用反馈 |

## 当前技术栈

FastAPI、Pydantic、SQLAlchemy 2、Alembic、MySQL 8、Chroma 本地持久化向量库、DeepSeek OpenAI 兼容 API（`deepseek-v4-flash`）、Ragas 0.4.3、pytest + HTTPX。容器与 CI 配置已纳入仓库，但是否已在目标环境运行要以本 README 的“验证状态”为准。

## 已实现功能

- 健康与就绪检查：`GET /health`、`GET /ready`；后者检查数据库、Chroma 持久化向量库和 DeepSeek 必要配置，但不会回显秘密，也不会调用模型。
- KnowledgeBase、Document、ChatMessage CRUD，以及 Swagger 参数校验和明确的 404/409/422/503 错误响应。
- `.md`、`.txt`、`.json`、`.yaml`、`.yml`、`.pdf`、`.docx` 上传、后台解析、分段与处理任务查询。
- 每个知识库独立建立 Chroma 索引；MySQL 关键词召回 + Chroma 向量召回，经 RRF 融合和确定性重排序后调用 DeepSeek 生成带引用的回答。
- 保存问答、引用、全部候选、关键词/向量/融合/重排序/模型耗时；支持查询检索日志与人工题集评测运行。
- 对既有问答提交匿名点赞/点踩与可选原因：`PUT /retrieval-logs/{id}/feedback`、`GET /retrieval-logs/{id}/feedback`。一个问答记录只保留最新一条匿名反馈，不收集用户身份。
- 脱敏 JSON 应用日志包含事件名、时间、请求标识、路径、状态码、耗时和错误类型；成功问答额外记录检索运行标识及各阶段耗时。日志不记录请求体、授权头、原始密码或 API 密钥。

## 本地启动

1. 从示例创建本地配置，并填写 MySQL 连接和 DeepSeek 密钥：

   ```powershell
   Copy-Item .env.example .env
   ```

   `DATABASE_URL` 中的密码若包含 `@`、`:`、`/` 等字符，需要进行 URL 编码；`.env` 已被 Git 忽略。

2. 安装依赖、执行数据库迁移并启动服务：

   ```powershell
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m alembic upgrade head
   .venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

3. 访问：

   - Swagger：`http://127.0.0.1:8000/docs`
   - 存活：`http://127.0.0.1:8000/health`
   - 就绪：`http://127.0.0.1:8000/ready`

## API 与数据流

典型流程：创建知识库与文档 → 上传并等待处理任务为 `completed` → `POST /knowledge-bases/{id}/index` 建立索引 → `POST /knowledge-bases/{id}/ask` 提问 → 通过 `GET /retrieval-logs/{id}` 复核引用、候选和耗时 → 可选提交反馈。

提问请求示例：

```json
{
  "question": "创建订单需要什么参数？",
  "top_k": 3,
  "recall_k": 8
}
```

文档上传、更新、重新处理或删除后会清除该知识库原有向量索引；需要重新调用索引接口，避免返回过期资料。

## 测试、离线演示与评测

完整隔离测试：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

可重复的离线演示（内存 SQLite + fake 向量/回答服务；不使用 MySQL、DeepSeek、网络或真实密钥）：

```powershell
.venv\Scripts\python.exe scripts\demo_offline.py
```

人工题集评测模板为 `evaluation_cases.example.json`。填写真实知识库 ID、问题和预期文档标题后执行：

```powershell
.venv\Scripts\python.exe scripts\evaluate_retrieval.py --cases 你的题集.json
```

评测只运行检索与重排序，不调用 DeepSeek，不产生模型调用费用。它会保存 Top-1、Recall@K、MRR、Ragas 文档级 ID-based Context Precision/Recall 和各阶段平均耗时。这里的 Ragas 指标把预期文档标题作为参考上下文 ID，衡量文档级上下文命中与排序；它不等同于 Faithfulness、Answer Relevancy 等需要评测模型的端到端回答指标。尚未用真实人工题集运行时，不应宣称命中率、引用覆盖率等质量数字。

## 时间与时区

面向用户、数据库记录和结构化日志的业务时间统一使用北京时间（`Asia/Shanghai`）：

- MySQL 的业务时间使用无时区的 `DATETIME` 保存北京时间墙上时间；API 响应和 JSON 日志会以 ISO 8601 的 `+08:00` 偏移明确标识，例如 `2026-08-10T12:00:00+08:00`。
- `20260810_0008` Alembic 迁移会将迁移前按 UTC 写入的既有 `DATETIME` 值整体加 8 小时，并把 MySQL 后续默认值改为 `UTC_TIMESTAMP() + INTERVAL 8 HOUR`。该数据迁移不可安全自动回退；生产升级前应先备份数据库。
- SQLAlchemy 新建或更新业务记录使用北京时间默认值；MySQL 连接也会设置为 `+08:00`，避免直接 SQL 的 `CURRENT_TIMESTAMP` 偏离。
- JWT 的 `iat`、`exp` 仍采用标准 UTC/Unix 安全语义；它们是令牌校验内部数据，不属于 API 向用户展示的业务时间。

## Docker 与 CI

容器环境使用 MySQL 8 和应用两个服务。首次运行可由脚本从本地 `.env` 读取模型连接配置，并为容器数据库、JWT 与管理员生成独立随机凭据；生成的 `.env.docker` 始终只保留在本机：

```powershell
python scripts/create_docker_env.py
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d
```

如需手动配置，可以 `.env.docker.example` 为模板；`MYSQL_PASSWORD` 与 `DATABASE_URL` 中的密码必须一致，且后者需要 URL 编码。Compose 会在应用启动前等待 MySQL 健康检查，应用容器启动时执行 `alembic upgrade head`，并将 MySQL 数据和 Chroma/上传文件分别写入命名卷。`Dockerfile`、`compose.yaml`、`.dockerignore` 和 GitHub Actions 测试工作流已提供；CI 只运行隔离测试与 fake 依赖，不需要真实 DeepSeek 密钥或外网模型下载。

## 验证状态与限制

- 已在本机通过：21 项隔离 pytest 测试（通过 fake 依赖）。
- Docker：`docker compose config --quiet` 已通过；MySQL 与应用容器已实际启动且为 healthy，`/health`、`/ready`、JWT 登录及受保护接口均已验证。
- GitHub Actions：首次远程工作流已成功运行，执行隔离测试与依赖检查。
- 当前为本地/受信任演示部署，使用 JWT 保护业务接口，并由本地 bootstrap 管理员初始化。尚未实现注册、用户管理、多用户角色或细粒度权限控制。
- 不包含 Agent、Redis、前端、神经重排序模型或 APISentinel 集成。
- DeepSeek 密钥只应保存在本地环境文件；不要粘贴到聊天、日志、截图或仓库。
