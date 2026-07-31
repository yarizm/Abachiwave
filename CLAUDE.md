# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

Abachiwave 是一个本地优先的 AI 音乐创作工作台：把灵感、歌词、哼唱旋律和参考方向转化为可编辑、可追溯、可导出的歌曲资产。后端 Python/FastAPI + 前端 Next.js，通过 Docker Compose 跑 PostgreSQL / Redis / MinIO 三件套。生成器当前是**本地确定性实现**，不需要外部 LLM、GPU、ffmpeg；外部文本 Provider 仅作可选增强。

详细架构见 `docs/architecture.md`，API 契约见 `docs/api.md`。本文件只补充读代码不易发现的关键约束。

## 常用命令

### 后端 (Python 3.12 + uv，在仓库根目录执行)

```bash
uv sync --all-groups --frozen          # 安装依赖(锁文件粉到底)
uv run ruff check .                    # lint
uv run mypy                            # 类型检查(strict, files=src+tests)
uv run pytest                          # 全量单测(默认 SQLite + ASGI 客户端)
uv run pytest tests/test_versioning.py -k "conflict"   # 跑单个文件/用例
uv run pytest --cov=abachiwave --cov-report=term-missing  # CI 用法,覆盖率门槛 70%
```

`pytest-asyncio` 的 `asyncio_mode = "auto"` 已开启,异步测试函数无需标记装饰器。测试默认依赖 SQLite in-memory(见 `tests/conftest.py`),不需要 Docker 服务起来。

### 前端 (Node 22,在 `web/` 执行)

```bash
npm ci
npm run dev          # http://localhost:3000
npm run lint
npm run typecheck    # tsc --noEmit
npm test             # tsx --test src/**/*.test.ts (Node 内置测试器,非 Jest/Vitest)
npm test -- src/lib/composition.test.ts    # 跑单个测试文件(CLI 传 tsx --test 的文件路径)
npm run build
npm run test:e2e     # Playwright,需要完整 Docker 栈先起来
```

前端单测跑的是 `tsx --test`,过滤器语法和 Node test runner 一致,不是 Jest/Vitest 的 `-t`。

### 本地完整栈

```bash
cd web && npm ci && cd ..
docker compose up -d --build            # 带 --reload,api 容器启动时自动 alembic upgrade head
docker compose ps
curl http://localhost:8000/health/ready # 检查 PG+Redis+MinIO 就绪
```

服务地址:Web `:3000` / API `:8000`(`/docs` 在此)/ MinIO Console `:9001`。

### 迁移 (Alembic,additive only)

```bash
uv run alembic upgrade head
uv run alembic revision -m "add_xxx"   # 生成新迁移,放 migrations/versions/
```

迁移文件命名约定:`YYYYMMDDNNNNN_snake_case_description.py`(NNNNN 是当日序号)。不允许 destructive/重建式迁移,见下文。

### 离线与冒烟脚本

```bash
uv run python scripts/smoke_mvp.py         # 真实 HTTP 端到端,需 API+Worker 在跑
uv run python scripts/audit_storage.py     # 对比 DB storage key 与 MinIO,默认只读
uv run python scripts/ensure_bucket.py      # CI 里建 bucket 用
```

## 架构关键约束(改代码前必读)

### 1. 版本化资产模型 — 不可变,新增不覆盖

所有专用资产走**版本表**(`song_spec_versions` / `lyrics_versions` / `chord_progression_versions` / `midi_asset_versions` / `arrangement_plan_versions` / `audio_demo_versions`)。编辑、Revision apply、restore 都**创建新版本**,绝不覆盖历史。未显式使用的专用 `ArtifactVersion` 通用表。

版本号分配在同一项目内串行:`lock_project_for_version_write` 先对 `projects` 行 `SELECT ... FOR UPDATE`,再在同一事务读 `max(version_number)` 并插入。唯一约束冲突只做**有限重试**(`VERSION_WRITE_MAX_RETRIES`,默认 2),耗尽抛 `VersionWriteConflictError` → 全局映射为稳定 `409 Conflict`。

SQLite 没有行锁,`lock_project_for_version_write` 通过 `UPDATE ... SET updated_at = updated_at` 触发写以串行化(见 `src/abachiwave/services/versioning.py`)。改版本写入逻辑时务必同时考虑 PostgreSQL 与 SQLite 路径,因为单元测试跑在 SQLite 上。

### 2. SongSpec 双轨结构 — `song_structure` 兼容字段 + `structure_sections` 规范化

SongSpec 同时保留兼容的 `song_structure` 和规范化的 `structure_sections`(每段带跨版本稳定的 `section_id`)。歌词、和弦、编曲段引用同一 `section_id`。结构编辑先落 `structure_change_previews`(**不产生资产版本**);确认应用时锁项目、重新校验 SongSpec 与资产快照,在单事务里创建所有受影响新版本。

歌词(schema v2)用受控行结构:每段同时存兼容 `text` 与规范化 `lines`(每行有稳定 `line_id`);字符数/音节/韵脚由 schema 计算。和弦(schema v2)用小节/拍点事件结构(每事件有稳定 `event_id`),并投影兼容的 `bars/chords`;`music21` 提供根音/罗马数字/Nashville 等理论层。

**改这些表先看现有迁移范式**(`migrations/versions/20260714000*.py`):旧数据会被补齐确定性 ID,新写入要拒绝非法符号/越界时值/重叠事件。本地草稿、撤销重做、未保存离开提示在歌词/和弦编辑器遵循同一语义。

### 3. 同步 vs 异步链路 — 四个直接生成接口的响应形状陷阱

四个直接生成接口(歌词/和弦/编曲/SongSpec):**只有显式传 `provider_profile_id` 或 `candidate_count` 时才切到异步候选模式**,否则走同步确定性生成,旧客户端的响应形状不变。改这些接口的请求/响应 schema 时两者都要维护。

异步生成走 Arq:`queued -> running -> succeeded | failed | cancelled`。API 建 `generation_runs` + 入 Redis job → Worker 执行 → 产物写 MinIO → 提交 ready 元数据到 PG。Worker 在 Provider 前、对象写入前、DB 提交前**三处检查取消状态**。失败/取消不创建 ready 资产,并尽力 `delete_bytes` 清理孤立对象(先写对象后提交 ready,提交失败要回滚已写对象)。

### 4. 三方数据边界

- **数据库**:只存 storage key、checksum、size、来源版本标识。对象二进制不进 DB。
- **MinIO**:存 MIDI/WAV/上传素材/ZIP。浏览器不直接访问公开 bucket,文件统一经 API 下载。
- **Redis**:只承担 Arq 队列和 Worker 通信。业务事实、任务终态、生成结果**一律以 PostgreSQL 为准**。
- **Provider 凭据**:`provider_profiles` 不存 API key;外部文本 Provider 需显式 env 配置(`TEXT_PROVIDER_API_*`),无配置时整链路走本地确定性 fallback。

### 5. 安全与可观测性硬约束

- 生产环境拒绝默认 MinIO 凭据(`reject_default_production_storage_credentials`,`core/config.py`)。
- CORS 白名单 + CSP/frame/MIME sniffing/referrer 安全头由 `request_context_middleware` 等 middleware 管。
- **日志禁止记录**:完整歌词、上传音频内容、数据库 URL、对象存储密钥。绑定 `request_id`/`project_id`/`generation_run_id` 即可。
- `/health/live` 查进程,`/health/ready` 查 PG+Redis+MinIO。
- 列表接口统一 `limit/offset` 上限,历史查询带复合索引(`migrations/versions/202607130001_*.py`)。

## 代码布局快速索引

- `src/abachiwave/`
  - `api/v1/` — FastAPI 路由,对应各业务域;`api/router.py` 统一挂 `/api/v1` 前缀
  - `schemas/` — Pydantic v2 输入输出契约(与 ORM 分层,不直接复用)
  - `models/` — SQLAlchemy 2.x async ORM,`core/database.py` 的 `Base` 用统一 `NAMING_CONVENTION`
  - `services/` — 业务逻辑(`versioning.py` / `storage.py` / `generation_runs.py` / `task_queue.py` 是地基;`*_provider.py` 是确定性生成器)
  - `agents/` — prompt 模板与 LangGraph 风格的确定性 agent 编排
  - `core/` — config(pydantic-settings,env via `validation_alias`) / database / logging / request_context
  - `worker.py` — Arq `WorkerSettings`,注册所有 generation job + health_check
  - `main.py` — `create_app()`,lifespan 统一释放 task queue / 对象存储 / engine
- `migrations/versions/` — Alembic,additive only
- `tests/` — 单测全跑 SQLite + ASGI transport(`conftest.py` override `get_session`);`test_migrations.py` 验证迁移可往返
- `web/src/`
  - `app/projects/[projectId]/` — 项目工作台入口及 `hooks/`(`useWorkspaceData` 用单 `Promise.all` 并行加载,之后只轮询 active run)
  - `components/workspace/` — 按业务域面板拆分,Audio/Composition/Demo/Revision 用 `next/dynamic` 延迟加载
  - `lib/` — API URL、排序、校验、状态判断(纯逻辑,带单测)
  - `i18n/translations.ts` — EN/中文 翻译,UI 语言设置可持久化
- `scripts/` — 离线审计与冒烟,CI 也会调用

## CI 四个 job

`.github/workflows/ci.yml`:security(pip-audit / npm audit / gitleaks) / backend(ruff+mypy+pytest) / frontend(lint+typecheck+test+build) / integration(PG+Redis+MinIO 起来跑 smoke_mvp) / browser(docker compose 全栈跑 Playwright)。PR 全绿才可合并,`main` 受保护。

## 红线提醒

数据库 schema 变更、数据迁移、删文件/分支、改 `.env`/密钥/CI、`git push`/rebase/reset、发布 — 都需先与用户确认。