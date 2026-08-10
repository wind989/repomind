# RepoMind 系统与业务流程

本文档描述的是当前仓库已经实现、能够运行和测试的流程。RepoMind 是一个面向后端项目文档的知识库问答服务：它把项目文档处理为可检索的片段，结合关键词检索与向量检索生成带引用的回答，并留下可追溯的问答、候选、反馈和评测记录。

## 1. 系统流程图

```mermaid
flowchart TB
    Client["使用者 / Swagger / API 调用方"]

    subgraph Public["公开接口"]
        Health["GET /health\n仅确认应用进程存活"]
        Ready["GET /ready\n检查数据库、向量存储、必要配置\n不调用模型，不回显密钥"]
        Login["POST /auth/token\n用户名和密码换取 JWT"]
    end

    subgraph API["FastAPI 应用层"]
        Middleware["请求中间件\n生成/透传 X-Request-ID\n统计延迟，记录脱敏 JSON 日志"]
        Auth["JWT 校验依赖\n除公开接口外均需 Bearer Token"]
        KBAPI["知识库与文档 CRUD\n/knowledge-bases\n/documents\n/chat-messages"]
        ProcessAPI["上传与任务接口\n/documents/{id}/upload\n/documents/{id}/reprocess\n/document-processing-tasks"]
        RagAPI["索引、提问、追溯、反馈与评测查询\n/index · /ask · /retrieval-logs\n/feedback · /evaluation-runs"]
    end

    subgraph Domain["业务服务层"]
        FileService["文件存储服务\n文件名/大小/类型校验\n保存、删除与路径解析"]
        Background["FastAPI BackgroundTasks\n处理任务状态：queued → running → completed/failed"]
        Extract["文本提取与切分\nmd/txt/json/yaml/yml/pdf/docx\n1000 字符片段，150 字符重叠"]
        Index["索引服务\n按知识库替换旧索引并写入片段"]
        Retrieve["混合检索服务\n关键词召回 + 向量召回\nRRF 融合 + 确定性重排"]
        Generate["回答生成服务\n只把 top_k 证据片段交给 DeepSeek\n证据不足时要求明确说明"]
        Evaluate["离线检索评测服务\n统计 Top-1、召回命中与各阶段耗时"]
    end

    subgraph Data["持久化与外部依赖"]
        MySQL[("MySQL 8\n用户、知识库、文档、片段、任务\n问答、引用、候选、反馈、评测\n业务时间按 Asia/Shanghai 保存")]
        Files[("本地文件目录\n原始上传文件")]
        Chroma[("Chroma 持久化目录\n按 knowledge_base_id 隔离的向量索引")]
        DeepSeek["DeepSeek OpenAI 兼容 API\ndeepseek-v4-flash"]
    end

    Client --> Health
    Client --> Ready
    Client --> Login
    Client --> Middleware
    Login --> MySQL

    Middleware --> Auth
    Auth --> KBAPI
    Auth --> ProcessAPI
    Auth --> RagAPI

    KBAPI <--> MySQL
    ProcessAPI --> FileService
    FileService <--> Files
    ProcessAPI --> Background
    Background --> Extract
    Extract <--> Files
    Extract --> MySQL

    RagAPI --> Index
    Index --> MySQL
    Index <--> Chroma
    RagAPI --> Retrieve
    Retrieve --> MySQL
    Retrieve <--> Chroma
    RagAPI --> Generate
    Generate --> DeepSeek
    Generate --> MySQL
    RagAPI --> Evaluate
    Evaluate --> MySQL
    Evaluate <--> Chroma

    Middleware -. "访问日志：事件、请求标识、路径、状态、耗时\n不记录请求体、Authorization、密码或密钥" .-> MySQL
```

### 系统中的职责边界

| 层级 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| FastAPI 路由 | 参数校验、权限校验、状态码、协调服务调用 | 不直接实现复杂检索算法或解析文件内容 |
| MySQL | 业务实体关系、任务状态、问答审计、候选分数、反馈、评测结果 | 不保存向量索引 |
| 本地文件目录 | 保存原始上传文件，供后台任务重新处理 | 不参与在线召回 |
| Chroma | 以片段文本和元数据建立向量索引，按知识库过滤召回 | 不保存用户、问答和反馈等业务记录 |
| DeepSeek | 在给定证据范围内组织自然语言回答 | 不管理知识库、不自行检索、不保存项目数据 |
| 日志 | 观察请求、任务与检索阶段耗时，定位失败类别 | 不记录完整敏感内容或任何密钥 |

## 2. 核心数据关系与写入位置

```mermaid
erDiagram
    USER ||--o{ KNOWLEDGE_BASE : "JWT 访问（当前不做资源归属隔离）"
    KNOWLEDGE_BASE ||--o{ DOCUMENT : contains
    DOCUMENT ||--o{ DOCUMENT_CHUNK : splits_into
    DOCUMENT ||--o{ DOCUMENT_PROCESSING_TASK : has
    KNOWLEDGE_BASE ||--o{ CHAT_MESSAGE : records
    KNOWLEDGE_BASE ||--o{ RETRIEVAL_LOG : answers
    RETRIEVAL_LOG ||--o{ ANSWER_CITATION : cites
    RETRIEVAL_LOG ||--o{ RETRIEVAL_CANDIDATE : preserves
    RETRIEVAL_LOG ||--o| ANSWER_FEEDBACK : receives
    KNOWLEDGE_BASE ||--o{ EVALUATION_RUN : evaluates
    EVALUATION_RUN ||--o{ EVALUATION_CASE_RESULT : contains

    USER {
        int id
        string username
        string password_hash
        boolean is_active
    }
    KNOWLEDGE_BASE {
        int id
        string name
        string description
        datetime created_at
    }
    DOCUMENT {
        int id
        int knowledge_base_id
        string title
        string storage_path
        string processing_status
        datetime processed_at
    }
    DOCUMENT_CHUNK {
        int id
        int document_id
        int chunk_index
        text content
        int char_start
        int char_end
    }
    DOCUMENT_PROCESSING_TASK {
        int id
        int document_id
        string operation
        string status
        datetime started_at
        datetime completed_at
    }
    RETRIEVAL_LOG {
        int id
        int knowledge_base_id
        text question
        text answer
        int keyword_latency_ms
        int vector_latency_ms
        int fusion_latency_ms
        int rerank_latency_ms
        int latency_ms
    }
```

说明：`User` 已用于 JWT 登录，但当前是本地/受信任演示部署；知识库、文档和问答记录**尚未**按用户进行资源级隔离。因此图中的 `User → KnowledgeBase` 是“通过登录访问”，不是“数据所有权关系”。

## 3. 业务流程图一：首次使用、建库和文档入库

```mermaid
flowchart TD
    Start([开始]) --> Bootstrap["服务启动\n如未存在则依据本地配置创建 bootstrap 管理员"]
    Bootstrap --> Token["POST /auth/token\n提交用户名、密码"]
    Token --> TokenOK{用户名、密码是否正确且用户启用？}
    TokenOK -- 否 --> E401["返回 401\n不签发令牌"]
    TokenOK -- 是 --> JWT["签发 Bearer JWT\n仅 iat/exp 使用 UTC Unix 语义"]
    JWT --> KB["POST /knowledge-bases\n创建知识库"]
    KB --> KBOK{名称是否唯一？}
    KBOK -- 否 --> E409KB["返回 409：知识库名称已存在"]
    KBOK -- 是 --> Document["POST /documents\n创建文档元数据\n标题、来源类型、知识库 ID 等"]
    Document --> Upload["POST /documents/{id}/upload\n上传文件"]
    Upload --> Valid{文件类型、文件名、大小是否合规？}
    Valid -- 否 --> E422["返回 422\n不创建处理任务"]
    Valid -- 是 --> Save["保存原始文件至本地目录\n更新 document.storage_path\n创建 queued 处理任务"]
    Save --> Invalidate["清空该知识库旧 Chroma 索引\n避免文档变动后返回陈旧向量结果"]
    Invalidate --> Accepted["立即返回 202 + task_id\nHTTP 请求不等待全文解析"]
    Accepted --> Background["BackgroundTasks 异步执行"]
    Background --> Running["任务 = running\n文档 processing_status = processing"]
    Running --> Parse["依据文件类型提取文本\n支持 md/txt/json/yaml/yml/pdf/docx"]
    Parse --> TextOK{文本可提取且非空？}
    TextOK -- 否 --> Failed["任务 = failed\n保存脱敏错误信息\n文档状态 = failed"]
    TextOK -- 是 --> Split["按字符切片\n目标 1000，重叠 150\n最多 2000 个片段"]
    Split --> Replace["删除该文档旧 DocumentChunk\n批量写入新片段"]
    Replace --> Done["任务 = completed\n文档状态 = completed\n写入 processed_at（北京时间）"]
    Done --> QueryTask["GET /document-processing-tasks/{id}\n确认任务 completed"]
    QueryTask --> Index["POST /knowledge-bases/{id}/index"]
    Index --> HasChunk{存在可索引片段？}
    HasChunk -- 否 --> E409Index["返回 409\n提示先完成文档处理"]
    HasChunk -- 是 --> Chroma["删除该知识库原索引\n按 chunk 写入 Chroma\n元数据包含知识库、文档、片段序号"]
    Chroma --> Ready([知识库可提问])
```

### 文档状态机

```mermaid
stateDiagram-v2
    [*] --> draft: 创建文档元数据
    draft --> queued: 上传或重处理任务创建
    queued --> processing: 后台任务开始
    processing --> completed: 提取、切分和入库成功
    processing --> failed: 文件格式、内容或解析失败
    completed --> queued: 上传新版本 / 请求重处理
    failed --> queued: 修正文件后重试
    completed --> draft: 删除文件或删除文档
```

## 4. 业务流程图二：提问、混合检索、回答与可追溯记录

```mermaid
flowchart TD
    AskStart([已登录用户提问]) --> Input["POST /knowledge-bases/{id}/ask\nquestion, top_k, recall_k"]
    Input --> Validate["Pydantic 校验：参数范围、必填字段\nJWT 校验：Bearer Token"]
    Validate --> KBExists{知识库存在？}
    KBExists -- 否 --> E404["返回 404"]
    KBExists -- 是 --> Parallel

    subgraph Parallel["混合召回（相同 question 与 recall_k）"]
        direction LR
        Keyword["关键词召回\n从问题提取英文词、数字词、中文二元词\n扫描 MySQL 文档标题和片段文本\n按关键词覆盖率排序"]
        Vector["向量召回\n在 Chroma 中按 knowledge_base_id 过滤\n返回距离、文档和片段元数据"]
    end

    Parallel --> Available{是否有向量索引且存在候选？}
    Available -- 否 --> E409["返回 409\n提示先完成文档处理和索引"]
    Available -- 是 --> Fusion["RRF 融合\n每路得分累加 1 / (60 + rank)"]
    Fusion --> Rerank["确定性重排\nrerank_score = RRF×1000 + 关键词分×10 + 向量相似度\n相同分数按 document_id、chunk_index 稳定排序"]
    Rerank --> TopK["取前 top_k 个候选作为证据\n保留全部候选用于审计"]
    TopK --> Prompt["构造受约束提示词\n包含问题、文档标题、片段序号和内容\n要求只基于证据回答"]
    Prompt --> LLM{DeepSeek 服务可用？}
    LLM -- 否 --> E503["返回 503\n不写入伪造回答"]
    LLM -- 是 --> Answer["生成简洁回答\n模型为 deepseek-v4-flash"]
    Answer --> Persist["单次提交写入 MySQL\n2 条 ChatMessage（用户问题、助手回答）\n1 条 RetrievalLog\n多条 AnswerCitation 与 RetrievalCandidate"]
    Persist --> RetrievalLog["记录检索阶段耗时\n关键词、向量、融合、重排、模型\n记录模型名、候选分数和引用摘要"]
    RetrievalLog --> Audit["记录 retrieval_completed 脱敏结构化日志\n含 retrieval_log_id、各阶段耗时"]
    Audit --> Response["返回 answer、retrieval_log_id、引用列表"]

    Response --> Review["可选：GET /retrieval-logs/{id}\n复核回答、引用、所有候选和耗时"]
    Review --> Feedback["可选：PUT /retrieval-logs/{id}/feedback\nhelpful（赞/踩）+ 可选 comment"]
    Feedback --> FeedbackStore["每条问答仅保留最新一条匿名反馈\n不采集用户身份"]
```

## 5. 业务流程图三：离线检索评测闭环

```mermaid
flowchart LR
    Dataset["人工题集 JSON\n知识库 ID、问题、期望文档标题"] --> Script["scripts/evaluate_retrieval.py"]
    Script --> Check["校验题集非空\n全部用例属于同一知识库"]
    Check --> Each["逐题调用 hybrid_retrieve\n不调用 DeepSeek，不产生模型费用"]
    Each --> Compare["比较 Top-1 文档与期望文档\n检查候选列表是否召回期望文档"]
    Compare --> Metrics["计算 Top-1 命中、召回命中\n关键词/向量/融合/重排平均耗时"]
    Metrics --> Store["写入 EvaluationRun\n写入每题 EvaluationCaseResult"]
    Store --> Inspect["GET /evaluation-runs\n查看历史评测记录"]
```

## 6. 故障处理、观测与安全边界

```mermaid
flowchart LR
    Request["任意 HTTP 请求"] --> Trace["X-Request-ID\n合法则透传，否则生成 UUID"]
    Trace --> Handle["执行业务接口"]
    Handle --> Success{执行成功？}
    Success -- 是 --> LogOK["JSON 日志：request_completed\n方法、路径、状态码、延迟"]
    Success -- 否 --> LogError["JSON 日志：request_failed\n错误类别、请求标识、延迟\n不记录请求体与敏感头"]
    LogOK --> Response["响应含 X-Request-ID"]
    LogError --> ErrorResponse["按场景返回 401/404/409/422/500/503"]

    Ready["/ready"] --> ReadyCheck["数据库连通性\nChroma 可用性\nDeepSeek 配置是否存在\nJWT 密钥配置是否存在"]
    ReadyCheck --> ReadyResult["ready / not_ready\n只返回组件状态，不返回秘密"]
```

当前不包含 Agent、Redis、前端、神经网络重排序模型、注册/用户管理、资源级多用户权限控制或 APISentinel 集成。Docker、MySQL、Chroma 和应用可容器化运行；CI 使用隔离测试与 fake 依赖，不需要真实模型密钥。
