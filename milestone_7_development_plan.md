# Abachiwave Milestone 7 开发计划：MVP 稳定化与封闭试用准备

## 1. 阶段定位

Milestone 7 不继续增加音乐创作资产类型，目标是把已经完成的本地 MVP 从“功能可演示”提升为“可持续开发、可重复验收、可供少量用户封闭试用”的稳定版本。

当前主链路已经覆盖项目、SongSpec、歌词、和弦、MIDI、编曲、Demo、Revision、音频上传、版本恢复和导出。本阶段重点解决以下差距：

- Git 仓库尚无提交，CI 配置尚未在远端真实运行。
- 自动化测试主要使用 SQLite 和进程内 ASGI，真实 PostgreSQL、Redis、MinIO、Worker 链路未进入 CI。
- 前端工作台组件体量过大，缺少组件级和浏览器端到端测试。
- API 与 Worker 缺少统一请求标识、业务上下文日志和依赖就绪检查。
- 资产版本号采用“查询最大值再加一”，并发写入时需要数据库级保护。
- 缺少可执行的本地运维、故障排查、数据备份与恢复说明。

## 2. 阶段目标

本阶段完成后应满足：

1. 所有当前代码进入可追溯的 Git 基线，Pull Request 自动执行完整质量门禁。
2. CI 使用真实 PostgreSQL、Redis 和 MinIO 验证迁移、存储和异步任务主链路。
3. 同一项目并发创建资产版本时不会产生重复版本号或丢失历史。
4. API、Worker 和事件记录可通过 `request_id`、`project_id`、`generation_run_id` 关联排障。
5. 项目工作台拆分为可维护的领域模块，同时保持当前并行加载和用户行为不变。
6. Playwright 可以从浏览器跑通标准 Demo 场景，并覆盖至少一个失败恢复场景。
7. 新开发者可以只依赖仓库文档完成启动、测试、排障、备份和恢复。

## 3. 明确不做

Milestone 7 不包含：

- 真实 LLM、外部音乐生成模型、Basic Pitch、GPU Worker 或模型计费。
- 正式用户注册、团队空间、角色权限和公开分享页面。
- MP3/M4A 解码、Stem 分离、DAW 原生工程或专业混音母带。
- 新的歌词、和弦、MIDI、编曲或 Revision 产品功能。
- 通用 `ArtifactVersion` 重构或现有业务表的大规模合并。
- Kubernetes、跨区域高可用或大规模生产部署。

正式多用户认证和真实模型 Provider 作为 Milestone 8 的候选范围；Milestone 7 仍以单用户、受控环境试用为边界。

## 4. 关键变更

### 4.1 仓库基线与开发流程

- 检查 `.gitignore`、`.dockerignore`、许可证、README 和环境变量示例，确保不提交 `.env`、本地数据库、对象存储数据、构建产物或密钥。
- 创建首次 Git 基线提交，并使用 `main` 作为默认分支。
- 配置 GitHub 仓库后启用分支保护，要求后端、前端和集成检查通过才能合并。
- 增加 Pull Request 模板，要求说明数据库迁移、接口变化、测试结果和回滚方式。
- 增加依赖更新策略和基础安全检查，包括 Python/Node 依赖漏洞扫描与 secret scan。
- 明确版本规范：应用版本、迁移版本和 Demo/Provider 版本分别管理。

### 4.2 CI 与真实依赖集成测试

- 保留现有快速检查：`ruff`、`mypy`、`pytest`、ESLint、TypeScript、前端测试和 production build。
- 新增 integration job，通过 GitHub Actions service containers 启动 PostgreSQL、Redis 和 MinIO。
- integration job 必须从空 PostgreSQL 数据库执行 `alembic upgrade head`，不使用 `Base.metadata.create_all`。
- 启动 API 与 Arq Worker 后运行精简版 `scripts/smoke_mvp.py`，验证真实队列、数据库和对象存储。
- 将 smoke 测试产生的项目和对象使用唯一前缀隔离，并在测试完成后清理。
- 对 migration 增加 PostgreSQL upgrade smoke；SQLite migration 测试继续保留为快速反馈，但不再作为唯一迁移依据。
- CI 失败时上传 API、Worker 日志和 Playwright trace，缩短排障时间。

### 4.3 后端一致性与可靠性

- 为 SongSpec、歌词、和弦、MIDI、编曲和 Demo 的版本分配增加事务保护。
- 创建新版本前锁定对应 `Project` 行，在同一事务内读取当前最大版本号并插入新版本。
- 对唯一约束冲突增加有限重试；超过重试次数返回明确的 `409 Conflict`，不暴露数据库异常。
- 审核生成任务状态机，确保 `queued -> running -> succeeded | failed | cancelled` 为唯一合法主路径。
- Worker 在读取输入资产后、调用 Provider 前、写入对象存储前和提交数据库前检查取消状态。
- 为 Demo 与音频转 MIDI 任务增加可配置执行超时；超时记录为 `failed` 并保留可重试信息。
- 对对象存储上传采用“先写对象、再提交 ready 元数据”的约定；数据库提交失败时尽力删除孤立对象。
- 为上传、导出和生成任务保留明确的大小、时长和数量限制。

### 4.4 健康检查、错误与可观测性

- 保留 `GET /health` 作为兼容入口。
- 新增 `GET /health/live`，只验证 API 进程可响应。
- 新增 `GET /health/ready`，并行检查 PostgreSQL、Redis 和 MinIO bucket；任一依赖不可用时返回 `503`。
- 增加请求上下文中间件：接受或生成 `X-Request-ID`，并在响应头返回相同值。
- 使用 `structlog.contextvars` 绑定 `request_id`、路由、HTTP 方法和响应状态。
- 进入项目业务后绑定 `project_id`；Worker 任务绑定 `generation_run_id` 和相关资产 ID。
- 统一未处理异常日志格式，但 API 响应不返回堆栈或内部连接信息。
- 为关键操作补齐事件记录，包括音频素材更新/归档/恢复、导出失败和任务重试。

### 4.5 前端工作台重构

- 将当前工作台按领域拆分到 `components/workspace` 和 `hooks`：
  - `ProjectOverview`
  - `SongSpecWorkspace`
  - `CompositionWorkspace`
  - `DeliveryWorkspace`
  - `DemoWorkspace`
  - `RevisionWorkspace`
  - `AudioWorkspace`
  - `CollaborationWorkspace`
- 将 URL 构造、请求执行、错误解析和轮询逻辑从页面组件移入类型化 API client 与领域 hooks。
- 初始页面数据继续并行请求，避免因组件拆分形成串行 waterfall。
- 仅在实际使用时加载较重的 Revision diff、Demo compare 和 Audio 编辑区域；保持静态可分析的动态导入路径。
- 将运行状态与表单草稿分离，避免一次输入导致整个工作台无关区域重新渲染。
- 不引入 Redux 等全局状态库；优先使用领域 hook、局部 state 和服务端返回数据。
- 保持现有 API 和可见功能不变，重构期间不调整业务语义。

### 4.6 浏览器测试与体验验收

- 引入 Playwright，使用独立测试项目和唯一数据前缀。
- 建立标准桌面主链路：创建项目、生成并批准 SongSpec、生成资产、生成 Demo、提交 Revision、导出 ZIP。
- 建立音频路径：上传 WAV、显示波形、提取 MIDI、下载并验证结果入口。
- 建立失败恢复路径：缺失依赖时按钮禁用、任务失败后重试、运行任务取消。
- 覆盖项目归档/恢复、版本 diff/restore、评论 resolve 和导出下载。
- 至少验证桌面 `1440x900` 与移动端 `390x844`，检查内容溢出、按钮可达性和播放器布局。
- 对关键页面执行基础可访问性检查：label、键盘焦点、状态提示、对比度和 reduced motion。

### 4.7 文档与本地运维

- 更新 README，将“已实现能力”“当前限制”“快速验证”和“故障排查”分开。
- 新增 `docs/runbook.md`，覆盖服务启动、迁移、Worker、MinIO bucket、常见错误和日志定位。
- 新增 `docs/backup-restore.md`，记录 PostgreSQL dump/restore 和 MinIO 数据备份步骤。
- 新增 `docs/architecture.md`，说明 API、Worker、存储、版本模型和 Provider 边界。
- 记录 Docker Desktop 不可用、端口冲突、迁移失败、Redis job 残留和 MinIO bucket 缺失的处理步骤。
- 保留开发环境匿名模式，并在文档中明确其不可用于公网部署。

## 5. Public Interfaces

### 5.1 新增接口

- `GET /health/live`
  - 成功：`200 { "status": "ok" }`
- `GET /health/ready`
  - 成功：`200 { "status": "ready", "dependencies": { ... } }`
  - 依赖异常：`503 { "status": "not_ready", "dependencies": { ... } }`

### 5.2 HTTP 行为调整

- 所有 API 响应增加 `X-Request-ID`。
- 客户端传入合法 `X-Request-ID` 时沿用该值，否则由 API 生成 UUID。
- 并发版本冲突返回 `409 Conflict` 和稳定错误消息。
- 未处理内部错误继续返回 `500`，但响应不包含堆栈、数据库 URL 或对象存储凭据。

### 5.3 新增环境变量

- `TASK_TIMEOUT_SECONDS`：异步生成任务最大执行时间。
- `VERSION_WRITE_MAX_RETRIES`：版本唯一约束冲突重试次数。
- `READINESS_TIMEOUT_SECONDS`：单个依赖就绪检查超时。
- `REQUEST_ID_HEADER`：默认 `X-Request-ID`。
- `MAX_PROJECT_UPLOADS`：单项目可用音频素材数量上限。

所有变量必须提供安全默认值并写入 `.env.example`；production 环境不得使用空密钥或默认对象存储凭据。

## 6. 数据库与迁移策略

- 本阶段原则上不新增业务实体。
- 如任务超时需要持久化原因，优先复用 `generation_runs.error_message` 和 provider 参数，不新增状态枚举。
- 版本并发保护优先使用现有 `projects` 行锁与唯一约束，不建立通用 Artifact 表。
- 每个迁移必须同时通过 SQLite 快速 smoke 和 PostgreSQL integration smoke。
- 升级必须兼容 Milestone 0-6 的现有数据，不要求清空 Docker volume。
- 新增迁移必须提供 downgrade，并在 PR 中写明数据影响。

## 7. 测试计划

### 7.1 后端测试

- `X-Request-ID` 生成、透传和响应头测试。
- readiness 对 PostgreSQL、Redis、MinIO 成功、超时和失败的测试。
- 同项目并发创建歌词、MIDI、编曲和 Demo 版本，版本号唯一且连续。
- Provider 超时、对象存储失败、数据库提交失败和孤立对象清理测试。
- queued/running 任务取消与取消后不生成资产测试。
- PostgreSQL 从 base 升级到 head，并验证表、外键、索引和唯一约束。
- Worker 日志包含 `generation_run_id`，项目事件包含关联 ID。

### 7.2 前端测试

- 拆分后的 hooks 覆盖加载、错误、轮询、重试和取消状态。
- 面板组件覆盖 empty、loading、ready、failed、archived 状态。
- API client 验证 request ID、错误解析和下载 URL。
- 保持现有 21 个工具逻辑测试全部通过。
- production build 的项目工作台首屏 JS 不应因重构显著增长。

### 7.3 端到端与集成测试

- Docker Compose 冷启动后执行完整主链路。
- 重启 API 和 Worker 后资产、任务与 MinIO 文件仍可读取。
- Playwright 在 Chromium 跑通标准 Demo 与音频上传路径。
- 下载的 MIDI 可被 `mido.MidiFile` 解析，WAV 包含 `RIFF/WAVE`，ZIP 可正常解压且 manifest 完整。
- CI 失败时保留服务日志、截图、trace 和下载文件样本。

### 7.4 手工体验测试

- 使用开发文档中的“深夜回家 Indie Rock”场景完成一次无中断创作。
- 在窄屏设备完成项目查看、Demo 播放、Revision 确认和文件下载。
- 人为关闭 Redis、MinIO 或 Worker，确认 UI 提示可理解且恢复服务后可继续操作。
- 使用两个并发浏览器窗口触发版本保存，确认不会覆盖历史或产生重复版本号。

## 8. 实施顺序

### 第 1 周：仓库与真实 CI

- 建立 Git 基线、远端仓库和分支保护。
- 完成 PostgreSQL/Redis/MinIO integration job。
- 将 migration 和 smoke MVP 纳入 CI。
- 建立 PR 模板和基础安全检查。

### 第 2 周：后端可靠性

- 实现 request ID、结构化上下文日志和 readiness。
- 完成版本写入事务保护与并发测试。
- 完成任务超时、取消检查和存储失败清理。
- 补齐关键项目事件。

### 第 3 周：前端重构与浏览器验收

- 拆分项目工作台组件、API client 和领域 hooks。
- 保持初始数据并行加载，控制 bundle 和重渲染。
- 建立 Playwright 主链路、失败恢复和移动端测试。
- 完成 runbook、架构和备份恢复文档。

## 9. 验收标准

### 工程验收

- [ ] Git 仓库存在可恢复的基线提交，远端 PR CI 可运行。
- [ ] `ruff`、`mypy`、`pytest`、ESLint、TypeScript、前端测试和 build 全部通过。
- [ ] CI 在真实 PostgreSQL、Redis、MinIO 和 Arq Worker 上跑通 smoke MVP。
- [ ] PostgreSQL 可从空库迁移到 head，并通过约束检查。
- [ ] 同项目并发创建版本不会产生重复版本或未处理的 500。
- [ ] API 和 Worker 日志可通过 request/run/project ID 关联。
- [ ] readiness 能准确反映数据库、队列和对象存储状态。

### 产品与体验验收

- [ ] 浏览器端可以从项目创建走到 Demo、Revision 和 ZIP 导出。
- [ ] WAV 上传、波形、音频转 MIDI 和 MIDI 下载通过浏览器验收。
- [ ] 任务失败、重试、取消和依赖不可用都有明确状态提示。
- [ ] 桌面与移动端关键流程没有内容重叠或不可点击控件。
- [ ] 工作台重构后现有功能、API 契约和版本历史无回归。

### 文档验收

- [ ] README 与当前能力一致，不再把已完成项目保留为未完成清单。
- [ ] 新开发者可按文档完成启动、测试和 smoke。
- [ ] PostgreSQL 与 MinIO 的备份恢复步骤至少手工验证一次。
- [ ] 当前单用户、无真实模型的限制在 README 中清晰可见。

## 10. 风险与控制

| 风险 | 影响 | 控制方式 |
|---|---|---|
| 工作台拆分造成行为回归 | 影响完整主链路 | 先补 Playwright 基线，再按领域逐块迁移 |
| CI 真实服务运行时间过长 | 降低开发反馈速度 | 快速单元 job 与 integration job 分离，缓存依赖和镜像 |
| SQLite 与 PostgreSQL 行为差异 | 本地通过、CI 失败 | PostgreSQL migration 和并发测试作为合并条件 |
| Worker 取消与对象写入竞态 | cancelled run 留下脏资产 | 多检查点取消、事务提交顺序和孤立对象清理 |
| 结构化日志泄露输入内容 | 暴露创作内容或密钥 | 日志只记录 ID、状态和错误类别，不记录完整歌词或凭据 |
| 范围再次扩张 | 稳定化工作被新功能打断 | Milestone 7 冻结业务接口，只接受可靠性和验收相关变更 |

## 11. 完成定义

Milestone 7 完成意味着 Abachiwave 达到“单用户封闭试用版”标准：已有主链路可重复运行、失败可定位、数据可恢复、浏览器流程有自动化保护。

完成本阶段后，再评估 Milestone 8 的两个方向：

1. 接入真实 LLM/TextGenerationProvider，并建立 Agent Evaluation 与成本控制。
2. 实现正式认证、项目所有权和多人协作权限，进入受邀用户试用。

