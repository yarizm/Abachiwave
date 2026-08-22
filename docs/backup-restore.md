# PostgreSQL 与 MinIO 备份恢复

本文描述 Docker Compose 本地环境的成对备份。数据库元数据和 MinIO 对象必须来自同一静止时间点，否则可能出现元数据存在但对象缺失，或对象没有数据库记录。

## 1. 准备

确认服务和目标目录：

```bash
docker compose ps
mkdir -p backups/minio-data
```

PowerShell：

```powershell
New-Item -ItemType Directory -Force backups/minio-data | Out-Null
```

记录当前迁移：

```bash
docker compose exec api alembic current
```

## 2. 创建一致备份

先停止会写入数据的服务：

```bash
docker compose stop web api worker
```

PostgreSQL 自定义格式 dump：

```bash
docker compose exec -T postgres pg_dump \
  -U abachiwave -d abachiwave -Fc \
  -f /tmp/abachiwave.dump
docker compose cp postgres:/tmp/abachiwave.dump backups/abachiwave.dump
docker compose exec -T postgres rm /tmp/abachiwave.dump
```

复制 MinIO 数据目录：

```bash
docker compose cp minio:/data/. backups/minio-data/
```

记录校验值：

PowerShell：

```powershell
Get-FileHash backups/abachiwave.dump -Algorithm SHA256
Get-ChildItem backups/minio-data -Recurse -File | Get-FileHash -Algorithm SHA256 |
  Export-Csv backups/minio-checksums.csv -NoTypeInformation
```

Linux/macOS：

```bash
sha256sum backups/abachiwave.dump > backups/checksums.sha256
find backups/minio-data -type f -print0 | sort -z | xargs -0 sha256sum >> backups/checksums.sha256
```

恢复正常服务：

```bash
docker compose start api worker web
curl http://localhost:8000/health/ready
```

备份目录应至少包含：

```text
backups/
  abachiwave.dump
  minio-data/
```

## 3. 恢复前保护

恢复会覆盖当前本地数据。先为现状再做一次备份，并确认目标 dump 的 SHA256。

停止写入服务和 MinIO：

```bash
docker compose stop web api worker minio
```

## 4. 恢复 PostgreSQL

复制 dump 到容器并重建 public schema：

```bash
docker compose cp backups/abachiwave.dump postgres:/tmp/abachiwave.dump
docker compose exec -T postgres psql -U abachiwave -d abachiwave \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -T postgres pg_restore \
  -U abachiwave -d abachiwave --no-owner --no-privileges \
  /tmp/abachiwave.dump
docker compose exec -T postgres rm /tmp/abachiwave.dump
```

不要在 `pg_restore` 后使用 `Base.metadata.create_all`。后续结构升级只通过 Alembic。

## 5. 恢复 MinIO

清空并恢复 MinIO volume 前，核对实际目标只位于 Compose 的 `minio_data` 数据目录。更稳妥的本地流程是重建 MinIO volume，然后复制快照：

```bash
docker compose rm -f minio minio-init
docker volume rm abachiwave_minio_data
docker compose create minio
docker compose cp backups/minio-data/. minio:/data/
docker compose start minio
docker compose up minio-init
```

如果 Compose project name 不是 `abachiwave`，先用以下命令确认实际 volume 名称，不要猜测：

```bash
docker volume ls
docker compose config --volumes
```

也可以保留现有 volume 并手工覆盖，但必须先确认目录中没有需要保留的新对象。不要对未确认路径执行递归删除。

## 6. 启动与迁移

```bash
docker compose start api worker web
docker compose exec api alembic upgrade head
curl http://localhost:8000/health/ready
```

API 启动命令也会执行 `alembic upgrade head`，显式执行便于在恢复日志中确认结果。

## 7. 恢复验证

检查表和迁移：

```bash
docker compose exec -T postgres psql -U abachiwave -d abachiwave \
  -c "SELECT count(*) AS projects FROM projects;"
docker compose exec api alembic current
```

检查 bucket：

```bash
uv run python scripts/ensure_bucket.py
```

最后执行只读页面检查，并从一个已知项目下载 WAV、MIDI 和 ZIP。完整验收可运行：

```bash
uv run python scripts/smoke_mvp.py
cd web
npm run test:e2e
```

`smoke_mvp.py` 会创建新的验证项目，不会证明所有旧对象都存在。因此至少额外抽查一个备份前已存在的 Demo、MIDI 和导出包。

## 8. 回滚恢复操作

如果恢复验证失败：

1. 保持 API、Worker 和 Web 停止。
2. 保存 PostgreSQL、MinIO 和恢复命令日志。
3. 使用恢复前创建的保护备份重复第 4 至第 6 节。
4. 不要混用两次备份的 PostgreSQL dump 和 MinIO 目录。

默认凭据和本地快照可能包含创作内容，不应提交到 Git。`backups/` 建议保存在仓库外或受访问控制的位置。

## 9. 验证记录

2026-07-11 在 Docker Desktop 本地环境完成一次非破坏性演练：

- PostgreSQL 自定义格式 dump 恢复到临时数据库，源库和恢复库项目计数一致。
- `minio:/data` 快照挂载到独立临时 MinIO 实例，bucket 和对象可正常列出。
- 临时数据库和临时 MinIO 容器在验证后删除，现有 Compose 数据未被覆盖。
