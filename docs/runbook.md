# Abachiwave 本地运行手册

本文面向本地开发和受控封闭试用环境。当前 Compose 配置使用匿名单用户模式和默认开发凭据，不可直接用于公网部署。

## 1. 启动与停止

首次准备依赖：

```bash
uv sync --all-groups --frozen
cd web
npm ci
cd ..
```

启动完整服务：

```bash
docker compose up -d --build
docker compose ps
```

API 容器启动时会先执行 `alembic upgrade head`。`minio-init` 会创建 `abachiwave-dev` bucket，成功退出属于正常状态。

停止服务但保留 PostgreSQL 和 MinIO 数据：

```bash
docker compose down
```

`docker compose down --volumes` 会永久删除本地数据库、对象文件和前端依赖卷，只能在确认不需要数据时执行。

## 2. 服务入口

| 服务 | 地址 | 说明 |
|---|---|---|
| Web | <http://localhost:3000> | Next.js 开发工作台 |
| API | <http://localhost:8000> | FastAPI |
| API 文档 | <http://localhost:8000/docs> | OpenAPI UI |
| MinIO API | <http://localhost:9000> | S3-compatible endpoint |
| MinIO Console | <http://localhost:9001> | 默认账号 `minioadmin` / `minioadmin` |
| PostgreSQL | `localhost:5432` | 数据库、用户和密码均为 `abachiwave` |
| Redis | `localhost:6379` | Arq 队列 |

## 3. 健康检查

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

- `/health/live` 只确认 API 进程可响应。
- `/health/ready` 并行检查 PostgreSQL、Redis 和 MinIO bucket。任一依赖不可用时返回 `503`。
- `/health` 保留为兼容入口。

PowerShell 可使用：

```powershell
Invoke-RestMethod http://localhost:8000/health/ready
```

## 4. 迁移

查看当前迁移和 head：

```bash
docker compose exec api alembic current
docker compose exec api alembic heads
```

手动升级：

```bash
docker compose exec api alembic upgrade head
```

在宿主机执行时，先确认 `.env` 的 `DATABASE_URL` 指向宿主机端口：

```bash
uv run alembic upgrade head
```

迁移失败时先查看 PostgreSQL 和 API 日志，不要通过清空 volume 绕过错误：

```bash
docker compose logs --tail=200 postgres api
```

## 5. Worker 与任务队列

查看或重启 Worker：

```bash
docker compose logs -f worker
docker compose restart worker
```

确认 Redis 可用：

```bash
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli --scan --pattern "arq:*"
```

任务状态以 PostgreSQL 中的 `generation_runs` 为准。API 和 Worker 重启后，已完成资产仍可读取；异常中断的任务应通过 UI/API 重试，不要直接修改数据库状态。

`TASK_TIMEOUT_SECONDS` 控制 Demo 和 audio-to-MIDI 的执行上限。超时任务会记录为 `failed` 并保留可查询错误。

## 6. MinIO 与对象存储

检查 bucket：

```bash
uv run python scripts/ensure_bucket.py
```

如果 `/health/ready` 报告 MinIO 不可用：

```bash
docker compose ps minio minio-init
docker compose logs --tail=200 minio minio-init
docker compose restart minio
docker compose up minio-init
```

上传和生成流程先写对象，再提交 ready 元数据。数据库提交失败时会尽力删除孤立对象。单个 WAV 上限为 25 MB，单项目上传数量由 `MAX_PROJECT_UPLOADS` 控制。

## 7. 日志与关联排障

```bash
docker compose logs -f api worker
docker compose logs --since=10m api worker web
```

API 接受或生成 `X-Request-ID`，并在响应头原样返回。排障时记录以下标识：

- `request_id`: 单次 HTTP 请求。
- `project_id`: 项目业务上下文。
- `generation_run_id`: Demo 或 audio-to-MIDI Worker 任务。

调用示例：

```bash
curl -i -H "X-Request-ID: local-debug-001" http://localhost:8000/health/ready
```

未处理异常只向客户端返回安全的 `500` 信息，详细堆栈仅出现在服务端日志中。

## 8. 常见问题

### Docker Desktop 不可用

```bash
docker version
docker context show
docker compose ps
```

确认 Docker Desktop 已启动且当前 context 可访问 daemon。恢复后重新执行 `docker compose up -d`。

### 端口冲突

PowerShell：

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 3000,5432,6379,8000,9000,9001
```

修改 `compose.yaml` 的宿主机端口时，同时更新 `.env` 和 `NEXT_PUBLIC_API_BASE_URL`。

### Web 返回 React Client Manifest 错误

不要在正在运行的绑定挂载开发容器上同时写入 production `.next`。先尝试：

```bash
docker compose restart web
```

仍失败时停止 Web，删除生成目录，再启动：

```bash
docker compose stop web
rm -rf web/.next
docker compose start web
```

PowerShell 删除命令：

```powershell
Remove-Item -LiteralPath web/.next -Recurse -Force
```

### Redis 残留任务

先查看 `generation_runs` 和 Worker 日志。仅在可丢弃数据的本地环境中，停止 API/Worker 并重新创建 Redis 容器；不要在有待恢复任务的环境使用 `FLUSHDB`。

### MinIO bucket 缺失

重新执行 `docker compose up minio-init` 或 `scripts/ensure_bucket.py`，然后复查 `/health/ready`。

## 9. 验证命令

快速质量门禁：

```bash
uv run ruff check .
uv run mypy
uv run pytest
cd web
npm run lint
npm run typecheck
npm test
npm run build
```

真实依赖 smoke 和浏览器验收：

```bash
uv run python scripts/smoke_mvp.py
cd web
npm run test:e2e
```

Playwright 覆盖桌面 `1440x900`、移动端 `390x844`、瞬时 API 失败恢复，以及桌面完整 MVP 生成链路。

## 10. 备份

执行升级、清理 volume 或迁移数据前，遵循 [backup-restore.md](backup-restore.md)。架构和数据边界见 [architecture.md](architecture.md)。
