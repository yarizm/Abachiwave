# Abachiwave

[![CI](https://github.com/yarizm/Abachiwave/actions/workflows/ci.yml/badge.svg)](https://github.com/yarizm/Abachiwave/actions/workflows/ci.yml)

[中文](README.md) | [English](README.en.md)

Abachiwave 是一个面向音乐创作者的 AI 协作创作工作台，用来把零散灵感、歌词、哼唱旋律和参考方向逐步转化为可编辑、可追溯、可导出的歌曲创作资产。

当前仓库已经跑通 MVP 主链路：

1. 创建项目并记录歌曲灵感。
2. 澄清需求并生成结构化 `SongSpec`。
3. 生成和编辑歌词、和弦、MIDI 与编曲方案。
4. 生成可试听 WAV Demo，并通过任务队列追踪状态。
5. 通过自然语言 revision 创建局部新版本、对比和恢复。
6. 上传 WAV 哼唱/参考音频，展示基础波形，并提取 melody MIDI 草稿。
7. 生成项目交接摘要，并导出包含当前资产、Demo 和上传音频的 ZIP 项目包。

详细产品设计划分见 [abachiwave_development_plan.md](abachiwave_development_plan.md)。当前稳定化工作见 [milestone_7_development_plan.md](milestone_7_development_plan.md)。

## 当前状态

已完成 Milestone 0-6 的本地 MVP 能力，以及 Milestone 7 的工程稳定化、真实依赖 CI、浏览器验收、安全扫描和运行文档。公开仓库的 `main` 分支已启用保护，合并前必须通过 Backend、Frontend、Security、Integration 和 Browser 五项检查。

- FastAPI API、Pydantic v2、SQLAlchemy 2.x、Alembic。
- PostgreSQL、Redis、MinIO、Arq worker 的 Docker Compose 本地环境。
- Next.js + TypeScript 前端工作台。
- 可持久化的 English/中文 UI 语言设置，中文模式覆盖导航、表单、状态、错误、空状态和系统生成说明，保留 SongSpec、MIDI、Demo 等专有名词。
- Idea Intake、澄清问题、SongSpec 草稿、编辑、确认和版本化。
- 歌词、和弦、chord/melody/hook MIDI 生成、编辑和下载。
- 编曲方案、资产树、版本时间线、Demo/上传音频、含 handoff/评论/评审/事件的 ZIP 导出和下载令牌。
- Demo 异步生成、状态轮询、失败重试、取消和浏览器试听。
- Revision Planner、影响范围预览、局部 apply、diff、restore 和事件记录。
- WAV 音频上传、波形 peak、试听、下载，以及本地确定性单旋律转 MIDI。
- Project Review 本地确定性完整度评分、检查项和下一步建议。
- 轻量项目评论，可绑定项目或当前资产，并支持 open/resolved 状态。
- Project Handoff 聚合当前资产、完整度评分、open comments、recent activity 和 Markdown 摘要。
- 工作台按 Project Overview、SongSpec、Composition、Delivery、Demo、Revision、Audio、Collaboration 领域拆分。
- Playwright 覆盖桌面、移动端、瞬时 API 失败恢复和完整 MVP 浏览器链路。
- API live/ready 健康检查、request ID、结构化日志、版本并发保护、任务超时和孤立对象清理。

生成逻辑仍以本地确定性实现为主：不依赖真实 LLM、外部音乐模型、GPU 或 ffmpeg。

## 环境要求

- Python `>=3.12`
- `uv`
- Node.js `22+`
- Docker Desktop

## 快速开始

### 安装后端依赖

```bash
uv sync --all-groups
```

### 安装前端依赖

```bash
cd web
npm install
```

### 启动完整本地环境

```bash
docker compose up -d --build
docker compose ps
```

本地服务：

- API: <http://localhost:8000>
- Web: <http://localhost:3000>
- MinIO Console: <http://localhost:9001>

确认依赖就绪：

```bash
curl http://localhost:8000/health/ready
```

### 运行自动 MVP smoke

在 Docker Compose 服务启动后执行：

```bash
uv run python scripts/smoke_mvp.py
```

脚本会通过真实 HTTP API 验证：项目创建、SongSpec、歌词/和弦/MIDI、编曲、交接摘要、导出、Demo、revision、评论、WAV 上传、音频转 melody MIDI，并检查 ZIP/WAV/MIDI 文件可读；ZIP 中会包含 handoff 摘要、评论、Project Review、Activity 事件、Demo WAV 和上传 WAV。

如需指定 API 地址：

```bash
ABACHIWAVE_API_BASE_URL=http://localhost:8000 uv run python scripts/smoke_mvp.py
```

## 常用检查

后端：

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

前端：

```bash
cd web
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

`test:e2e` 需要已经运行的 Docker Compose 服务。生产构建和绑定挂载的 Next.js 开发容器会共用 `.next`，建议在构建后重启 Web 容器。

## 当前限制

- 匿名单用户模式，没有正式登录、项目所有权或团队权限。
- 所有 Agent 和音乐 Provider 都是本地确定性实现，不代表商业生成质量。
- 音频分析只支持 WAV；不支持 MP3/M4A、Stem、Basic Pitch 或 ffmpeg。
- 单个 WAV 上限 25 MB，单项目素材数量默认上限 100，可通过 `MAX_PROJECT_UPLOADS` 调整。
- Docker Compose 默认账号和绑定挂载开发服务器仅用于本地或受控封闭试用，不能直接暴露到公网。

## 开发与运维文档

- [本地运行与排障](docs/runbook.md)
- [系统架构与数据流](docs/architecture.md)
- [PostgreSQL 与 MinIO 备份恢复](docs/backup-restore.md)

## 核心 API 概览

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/projects`
- `POST /api/v1/projects/{project_id}/intake`
- `POST /api/v1/projects/{project_id}/song-spec/generate`
- `POST /api/v1/projects/{project_id}/lyrics/generate`
- `POST /api/v1/projects/{project_id}/chords/generate`
- `POST /api/v1/projects/{project_id}/midi/generate`
- `POST /api/v1/projects/{project_id}/arrangement/generate`
- `POST /api/v1/projects/{project_id}/demo/generate`
- `POST /api/v1/projects/{project_id}/audio-uploads`
- `POST /api/v1/projects/{project_id}/audio-uploads/{audio_upload_id}/extract-midi`
- `POST /api/v1/projects/{project_id}/revisions`
- `POST /api/v1/projects/{project_id}/comments`
- `POST /api/v1/projects/{project_id}/exports`
- `GET /api/v1/projects/{project_id}/review`
- `GET /api/v1/projects/{project_id}/handoff`
- `GET /api/v1/tasks/{task_id}`

API 会接受或生成 `X-Request-ID`，并在响应头回传相同值。`/health/ready` 会检查 PostgreSQL、Redis 和 MinIO，可用于区分“进程存活”和“依赖已就绪”。

## 技术栈

- 后端：FastAPI、Pydantic、SQLAlchemy、Alembic
- Agent/Workflow：LangGraph
- 存储：PostgreSQL、MinIO/S3-compatible object storage
- 异步任务：Redis、Arq worker
- 音乐处理：mido、本地确定性 WAV/MIDI provider
- 前端：Next.js、React、TypeScript

## 开源协议

本项目采用 MIT License，详见 [LICENSE](LICENSE)。
