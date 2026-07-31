# Abachiwave 架构说明

## 1. 系统边界

Abachiwave 当前是单用户、本地优先的音乐创作产品底座。API 契约和资产版本模型已经稳定；文本创作支持可选的服务端外部 Provider，身份认证、团队权限和外部音乐模型仍不在当前范围。

```mermaid
flowchart LR
    U["Browser / Next.js"] -->|"REST + X-Request-ID"| A["FastAPI API"]
    A --> P[("PostgreSQL")]
    A --> R[("Redis / Arq")]
    A --> M[("MinIO")]
    R --> W["Arq Worker"]
    W --> P
    W --> M
    W --> D["Deterministic Providers"]
    W --> T["Optional Text Provider"]
    A --> S["SongSpec and Composition Services"]
    S --> P
```

## 2. 组件职责

### Web

- Next.js App Router + React + TypeScript。
- `useWorkspaceData` 在进入项目时通过单个 `Promise.all` 并行加载项目资源、Provider 能力和生成候选。
- 进入页面后的任务更新只轮询 active run 对应的 `/api/v1/tasks/{id}`；任务进入终态后再做一次完整刷新，避免固定周期重复加载整个工作台。
- `components/workspace` 按 Project Overview、SongSpec、Structure、AI Candidates、Composition、Delivery、Demo、Revision、Audio、Collaboration 拆分。
- Audio、Composition、Demo 和 Revision 面板通过 `next/dynamic` 延迟加载；写操作按业务域维护 pending 状态，互不阻塞无关面板。
- API URL、排序、校验和状态判断位于 `web/src/lib`。
- 下载按钮通过 `fetch -> Blob -> object URL` 保存跨源 API 文件，播放器继续直接使用流式 URL。

### API

- FastAPI 提供版本化 `/api/v1` REST 接口。
- Pydantic v2 schema 负责输入和输出契约。
- SQLAlchemy 2.x AsyncSession 管理事务，Alembic 管理 additive migration。
- Request context middleware 接受或生成 `X-Request-ID`，结构化日志绑定请求、项目和任务标识。
- 列表接口统一使用有上限的 `limit/offset`，常用项目历史查询带复合索引。
- CORS 使用明确的来源、方法和请求头白名单，响应包含 CSP、frame、MIME sniffing 和 referrer 安全头。
- `/health/live` 检查进程；`/health/ready` 检查 PostgreSQL、Redis 和 MinIO。

### Worker

- API 创建 `generation_runs` 并将 Arq job 写入 Redis。
- Worker 执行文本候选、文本评测、Demo 和 audio-to-MIDI 生成，检查取消状态和超时。
- Provider 与对象存储的同步调用通过线程卸载，避免阻塞事件循环。
- 成功后写入版本元数据；失败或取消时不创建 ready 资产，并尽力清理孤立对象。

### PostgreSQL

保存项目、输入、所有专用资产版本、任务状态、Revision、评论和事件。对象二进制不进入数据库，只保存 storage key、checksum、size 和来源版本标识。

文本生成元数据保存在 `provider_profiles`、`prompt_template_versions` 和
`generation_candidates` 和 `evaluation_runs`。Provider profile 不保存 API key；未选择候选
不会进入正式资产表。评测保存 Prompt/Provider 来源、自动指标和盲评结果，不把私有 A/B
映射暴露给 API 调用方。

### MinIO

保存 MIDI、WAV、上传素材和 ZIP 导出包。浏览器不直接依赖公开 bucket，文件统一经 API 下载。

### Redis

只承担 Arq 队列和 Worker 通信。API 进程复用一个延迟创建的 Arq Redis pool，关闭时由 FastAPI lifespan 统一释放。业务事实、任务终态和生成结果均以 PostgreSQL 为准。

## 3. 资产与版本模型

当前使用专用版本表，不引入通用 `ArtifactVersion`：

- `song_spec_versions`
- `lyrics_versions`
- `chord_progression_versions`
- `midi_asset_versions`
- `arrangement_plan_versions`
- `audio_demo_versions`

编辑、Revision apply 和 restore 都创建新版本，不覆盖历史。当前资产由聚合服务按以下规则选取：

- approved SongSpec。
- 最新歌词和和弦。
- 每种 MIDI 的最新版本。
- 最新编曲方案和 Demo。

同项目写入新版本前会锁定 `projects` 行，在同一事务读取最大版本号并插入。唯一约束冲突只进行有限重试，耗尽后返回稳定 `409 Conflict`。

SongSpec 同时保留兼容字段 `song_structure` 和规范化的 `structure_sections`。后者为每个段落
提供跨版本稳定的 `section_id`，歌词、和弦和编曲段落引用同一标识。结构编辑先持久化
`structure_change_previews`，不产生资产版本；确认应用时锁定项目、重新校验 SongSpec 与资产
快照，并在单个事务中创建所有受影响的新版本。MIDI 和 Demo 当前没有段落级结构数据，
因此保留历史文件并明确要求重新生成，不把旧文件标记为已同步。

歌词版本使用 schema v2 的受控行结构。每个段落同时保存兼容 `text` 与规范化 `lines`；
每一行具有稳定 `line_id`、正文和可选韵脚标记，字符数、单词数、音节、韵脚与重音提示由
schema 计算。旧版本在迁移时获得确定性的行 ID，后续编辑、段落复制和 Revision 会保留来源
行标识，避免仅靠文本位置追踪修改。

歌词编辑器的逐行修改、候选接受、撤销/重做和词汇偏好先保存在浏览器本地草稿。Rewrite
接口可接收当前未保存段落，只返回差异预览，不写入资产表；用户显式保存时才通过 `PATCH`
创建不可变的新歌词版本。页面离开前会提示未保存内容，且本地草稿仅在来源版本 ID 一致时恢复。

和弦版本使用 schema v2 的小节/拍点事件结构，并继续维护兼容的 `bars/chords` 投影。每个事件
具有稳定 `event_id`、拍点、时值、符号和转位；`music21` 理论层统一产生根音、低音、和弦
性质、延伸音、音级集合、试听 MIDI 音高、罗马数字、Nashville 数字谱与借用和弦标记。
旧版本由迁移补齐确定性事件 ID，新写入会拒绝非法符号、越界时值和重叠事件。

和弦本地草稿、撤销/重做和未保存离开提示与歌词编辑器遵循同一语义。预检接口只分析当前
草稿，不创建版本；保存和全曲/段落移调继续创建不可变版本。浏览器仅消费服务端返回的
MIDI 音高，并在用户点击试听时动态加载 Tone.js，提供和弦播放、节拍器与循环。

资产聚合、编曲、Demo 与导出入口都会校验来源 SongSpec。同一 SongSpec 内的歌词、旋律等
局部版本演进可继续复用兼容资产；跨 SongSpec 的 MIDI 或编曲引用会作为缺失前置条件处理，
直到对应资产重新生成，避免历史文件被误当作当前交付链。

## 4. 同步创作链路

```mermaid
flowchart TD
    I["Idea Intake"] --> C["Requirement Clarifier"]
    C --> S["SongSpec Draft"]
    S --> A["Approve SongSpec"]
    A --> L["Lyrics Version"]
    A --> H["Chord Version"]
    L --> MI["MIDI Versions"]
    H --> MI
    MI --> AR["Arrangement Version"]
    AR --> E["Asset Tree / ZIP Export"]
```

现有直接生成接口继续使用确定性 Agent。AI Candidates 链路可选择服务端配置的外部
Provider，也可以使用本地 deterministic fallback；两者都通过同一 Pydantic schema 校验。
四个直接生成接口只有在显式传入 `provider_profile_id` 或 `candidate_count` 时切换为异步
候选模式，因此旧客户端的响应形状保持不变。

## 5. AI 候选链路

```mermaid
sequenceDiagram
    participant Web
    participant API
    participant Queue as Redis
    participant Worker
    participant Provider
    participant DB as PostgreSQL
    Web->>API: POST candidates/generate
    API->>DB: create queued text_generation run
    API->>Queue: enqueue run id
    Worker->>Provider: versioned prompt + JSON schema
    Provider-->>Worker: 1-3 structured candidates
    Worker->>DB: validate and save candidates
    Web->>API: POST candidate/select
    API->>DB: materialize one asset version atomically
```

SongSpec、歌词、编曲和 Revision 使用独立 Prompt 模板。输出解析只允许一次有限 JSON
提取修复，随后必须通过对应 Pydantic schema；失败 run 记录稳定 `error_code`。

固定 `creative-briefs-v1` 样例集包含 32 条用例，每个 workflow 8 条。Evaluation Worker
逐条调用同一 Provider contract，记录 schema 合法率、约束遵循率、段落完整率、重复度和
token usage；Provider 输出与 deterministic baseline 以稳定但隐藏的 A/B 顺序提供人工盲评。
Prompt 或模型升级应建立新 EvaluationRun，并与历史基线比较，而不是只检查接口成功。

## 6. 异步生成链路

```mermaid
sequenceDiagram
    participant Web
    participant API
    participant DB as PostgreSQL
    participant Queue as Redis
    participant Worker
    participant Store as MinIO
    Web->>API: POST demo/generate
    API->>DB: create queued GenerationRun
    API->>Queue: enqueue run id
    API-->>Web: 202 queued
    Worker->>DB: lock run, mark running
    Worker->>Worker: deterministic provider
    Worker->>Store: put WAV/MIDI bytes
    Worker->>DB: create asset version, mark succeeded
    Web->>API: poll GET task
    API-->>Web: succeeded + result id
```

合法主状态路径为 `queued -> running -> succeeded | failed | cancelled`。Worker 在 Provider 前、对象写入前和数据库提交前检查取消状态。

## 7. 存储一致性

- 上传和 Worker 生成采用“先写对象，再提交 ready 元数据”。
- 数据库提交失败时，调用 `delete_bytes` 尽力删除已写对象。
- 下载时同时校验项目归属和元数据，避免跨项目访问。
- 上传、下载和 ZIP 归档按块传输；ZIP 使用可落盘的临时缓冲并受 `MAX_EXPORT_BUNDLE_BYTES` 限制，避免大文件链路常驻内存。
- `checksum` 和 `size_bytes` 用于导出与排障，不替代对象存储自身完整性机制。
- `MAX_PROJECT_UPLOADS` 和 25 MB 单文件上限控制本地素材增长。
- `scripts/audit_storage.py` 对比数据库 storage key 与 MinIO inventory；默认只读，显式指定 `--delete-orphans` 才删除孤立对象。

## 8. 可观测性

- HTTP: `request_id`、method、route、status。
- 项目操作: `project_id`、artifact/revision id。
- Worker: `generation_run_id`、project id、结果资产 id。
- `project_events` 记录关键业务动作，供 handoff、导出和试用复盘使用。

日志不应记录完整歌词、上传音频内容、数据库 URL 或对象存储密钥。

## 9. 测试层次

- 单元/API: SQLite + ASGI，覆盖 schema、服务、状态机和快速迁移 smoke。
- Integration CI: PostgreSQL、Redis、MinIO、API、Worker 和真实对象文件。
- Browser CI: Chromium 桌面/移动端、失败恢复和完整 MVP UI 链路。
- Agent evaluation: 32 条固定样例作为离线 deterministic 基线；真实 Provider 评测通过显式
  服务端配置运行，目标 schema 合法率不低于 98%。
- `scripts/smoke_mvp.py`: 真实 HTTP、并发版本写入、WAV/MIDI/ZIP 内容检查。

## 10. 当前限制

- 匿名单用户模式，无正式认证和授权。
- 外部文本 Provider 需要显式环境配置；无配置时完整链路使用本地确定性 fallback。
- 真实 Provider 的人工质量优势必须由盲评提交证明；离线测试只能证明 contract 和基线稳定。
- Demo 和 audio-to-MIDI Provider 仍是本地确定性实现，不代表商业生成质量。
- 只分析 WAV，不支持 MP3/M4A 解码。
- 无 GPU、Basic Pitch、Stem、DAW 工程或公开分享页。
- 专业编辑器已完成统一段落时间线、歌词逐行工具和和弦网格试听；结构化 MIDI 与钢琴卷帘仍在 Milestone 9 后续切片中。
- Compose 默认凭据、开发服务器和绑定挂载仅适合本地或受控环境。
