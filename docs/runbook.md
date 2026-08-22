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
| Basic Pitch（可选） | <http://localhost:8010/health/ready> | 隔离的 audio-to-MIDI 推理健康检查 |

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

# Dedicated audio-to-MIDI worker (started by the default Compose stack)
docker compose logs -f audio-midi-worker
docker compose restart audio-midi-worker

# Audio normalization worker (optional isolated profile)
docker compose --profile ffmpeg up -d ffmpeg-worker
docker compose logs -f ffmpeg-worker
```

WAV 上传可由 API 直接解析；MP3、M4A、FLAC、OGG 上传会自动排入 `arq:audio-ffmpeg`，因此
使用这些格式前必须启动 `ffmpeg-worker`。队列、解码或取消失败时上传状态为 `failed`，可在
工作区点击“重试标准化”，不要直接修改数据库状态。

默认 `AUDIO_TO_MIDI_PROVIDER_NAME=local_monophonic_wav_to_midi`，专用 Worker 使用确定性离线
基线，不需要模型服务。要启用真实 Basic Pitch，在 `.env` 中设置：

```dotenv
AUDIO_TO_MIDI_PROVIDER_NAME=spotify_basic_pitch
BASIC_PITCH_SERVICE_URL=http://basic-pitch:8080
BASIC_PITCH_TIMEOUT_SECONDS=90
TASK_TIMEOUT_SECONDS=120
```

然后启动隔离 profile，并检查服务和日志：

```bash
docker compose --profile basic-pitch up -d --build basic-pitch audio-midi-worker api
curl http://localhost:8010/health/ready
docker compose ps basic-pitch audio-midi-worker api
docker compose logs -f basic-pitch audio-midi-worker
```

Basic Pitch 镜像使用独立 Python 3.11 环境，并把 Numba cache 放在非 root 用户可写的 `/tmp`；
不要把它的模型依赖安装进 API 的 Python 3.12 环境。切回本地 Provider 时修改 `.env` 并重建/重启 `api` 与 `audio-midi-worker`。已经排队的
run 按数据库中记录的 Provider 重建，不会因当前配置变化而静默换 Provider。

确认 Redis 可用：

```bash
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli --scan --pattern "arq:*"
```

任务状态以 PostgreSQL 中的 `generation_runs` 为准。API 和 Worker 重启后，已完成资产仍可读取；异常中断的任务应通过 UI/API 重试，不要直接修改数据库状态。

`TASK_TIMEOUT_SECONDS` 控制 Demo、audio-to-MIDI 和音频派生任务的执行上限。超时任务会记录为 `failed` 并保留可查询错误。
`FFMPEG_BINARY` 和 `FFMPEG_TIMEOUT_SECONDS` 控制独立 ffmpeg Worker 的可执行文件和转换超时。
选择 Basic Pitch 时，`TASK_TIMEOUT_SECONDS` 必须至少比 `BASIC_PITCH_TIMEOUT_SECONDS` 大 15 秒。

### Basic Pitch 容器故障矩阵

下面的脚本会临时重建 `api` 和 `audio-midi-worker`、停止/暂停 Basic Pitch，并重启 MIDI Worker；
只应在本地或隔离测试环境运行。脚本创建独立项目并在退出时归档，随后恢复原 Provider、超时设置
和 Basic Pitch 初始启停状态：

```bash
uv run python support/validate_basic_pitch_faults.py
```

成功结果必须覆盖：

- sidecar 断连：`failed / audio_to_midi_provider_unavailable`，无 MIDI 资产；
- sidecar 恢复：重新排队后 `succeeded`；
- sidecar 响应超时：`failed / audio_to_midi_provider_timeout`，无 MIDI 资产；
- 推理过程中取消：`cancelled / task_cancelled`，Provider 返回后仍不写资产；
- 推理过程中重启 Worker：`failed / task_interrupted`，重投旧消息不再次执行。

若脚本异常退出，先执行 `docker compose unpause basic-pitch`，再根据 `.env` 重建 `api` 与
`audio-midi-worker`。任务终态仍以 PostgreSQL 为准，不要直接修改 Redis job key。

### Audio-to-MIDI 质量与容量基准

数据集格式、指标定义、阈值规则和正式放行流程见
`docs/audio-to-midi-benchmark.md`。合成管线自检：

```bash
uv run python support/create_audio_to_midi_smoke_dataset.py path/to/temp-dataset
uv run python support/benchmark_audio_to_midi.py \
  path/to/temp-dataset/manifest.json \
  --output path/to/temp-dataset/report.json
```

可复现的 NSynth acoustic 单音观察基线：

```bash
uv run python support/fetch_nsynth_benchmark_subset.py path/to/nsynth-subset
uv run python support/benchmark_audio_to_midi.py \
  path/to/nsynth-subset/manifest.json \
  --output path/to/nsynth-subset/report.json
```

采集器流式读取并验证官方 archive ETag，不在仓库或输出目录保存完整压缩包；默认保存 14 个小样本。
输出目录必须为空，避免覆盖已有评测结果。该数据只覆盖 isolated held notes，不能代替乐句或复调验收。

GuitarSet 真实 solo/comp 乐句观察基线：

```bash
uv run python support/fetch_guitarset_benchmark_subset.py path/to/guitarset-subset
uv run python support/benchmark_audio_to_midi.py \
  path/to/guitarset-subset/manifest.json \
  --output path/to/guitarset-subset/report.json
```

GuitarSet 采集器校验 Zenodo 1.1.0 record、CC BY 4.0、两份 ZIP 的大小/MD5，通过 Range 请求只取
目标 member，并拒绝官方已记录的错误标注 stem。不要把临时下载的真实音频提交进仓库。

Vocadito 完整真实演唱基线与双标注者一致性：

```bash
uv run python support/fetch_vocadito_benchmark_dataset.py path/to/vocadito
uv run python support/evaluate_audio_to_midi_reference_agreement.py \
  path/to/vocadito/manifest.json \
  --output path/to/vocadito/reference-agreement.json
uv run python support/benchmark_audio_to_midi.py \
  path/to/vocadito/manifest.json \
  --output path/to/vocadito/report.json
```

采集器会读取全部 40 条音频，完整校验官方 ZIP MD5，并为 A1/A2 分别生成参考 MIDI。benchmark
按 manifest 的 `best_onset_pitch_offset_f1` 策略逐曲选择更匹配的有效人工标注；不要手工删除低分
标注或只保留对当前模型有利的一位标注者。

Vocadito 歌手隔离参数扫描：

```bash
uv run python -m support.sweep_basic_pitch_parameters \
  path/to/vocadito/manifest.json \
  --definition support/basic_pitch_vocadito_sweep.json \
  --output path/to/vocadito/basic-pitch-sweep-v1.json

uv run python -m support.sweep_basic_pitch_parameters \
  path/to/vocadito/manifest.json \
  --definition support/basic_pitch_vocadito_refinement.json \
  --output path/to/vocadito/basic-pitch-sweep-refinement.json
```

扫描默认按 `singer_id` 做 development/holdout 分组并关闭 Docker 资源采样，以便多个候选使用一致
样本。先用 development 排名，再对 baseline 与入选候选运行 holdout；不要根据 holdout 反复人工
修改搜索空间。需要续跑时可传 `--reuse-existing`，必要时用 `--reports-directory` 指向已有候选报告
目录。选定最终候选后，仍须用普通 benchmark 命令对完整数据集开启容器资源采样。

报告退出码 `2` 表示推理完成但阈值未通过；不要把它当成基础设施失败重试。资源采样使用
`docker stats --no-stream` 轮询；CPU 为 `null` 表示没有有效采样，不等于 CPU 峰值为零。
合成结果不能作为真实人声或复调质量证明。

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
