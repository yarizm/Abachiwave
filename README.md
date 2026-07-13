# Abachiwave

[![CI](https://github.com/yarizm/Abachiwave/actions/workflows/ci.yml/badge.svg)](https://github.com/yarizm/Abachiwave/actions/workflows/ci.yml)

Abachiwave 是一个面向音乐创作者的本地优先 AI 协作工作台，用于把灵感、歌词、哼唱旋律和参考方向转化为可编辑、可追溯、可导出的歌曲资产。

## 已实现能力

- 项目、Idea Intake、需求澄清和版本化 SongSpec。
- 歌词、和弦、chord/melody/hook MIDI 与编曲方案生成和编辑。
- 基于 Arq 的异步 WAV Demo 生成、重试、取消和浏览器试听。
- Revision Planner、版本差异、恢复和项目事件记录。
- WAV 上传、波形展示和单旋律转 MIDI。
- 项目评审、评论、handoff 摘要和 ZIP 导出。
- 可持久化的 English/中文 UI 语言设置。

生成器目前采用本地确定性实现，不需要外部 LLM、音乐模型、GPU 或 ffmpeg。

## 环境要求

- Python `>=3.12`
- `uv`
- Node.js `22+`
- Docker Desktop

## 本地启动

```bash
uv sync --all-groups --frozen
cd web && npm ci && cd ..
docker compose up -d --build
docker compose ps
```

本地服务：

- Web: <http://localhost:3000>
- API: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs>
- MinIO Console: <http://localhost:9001>

依赖就绪检查：

```bash
curl http://localhost:8000/health/ready
```

## 验证

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

完整 Docker 服务启动后可执行：

```bash
uv run python scripts/smoke_mvp.py
cd web && npm run test:e2e
```

对象存储一致性审计默认只读：

```bash
uv run python scripts/audit_storage.py
```

## 文档

- [API 接口](docs/api.md)
- [系统架构](docs/architecture.md)

## 当前限制

- 当前为匿名单用户模式，不适合直接暴露到公网。
- 音频分析仅支持 WAV，单文件上限默认 25 MB。
- 本地生成结果定位为可验证草稿，不代表商业制作质量。
- Compose 默认凭据仅用于本地开发环境。

## License

[MIT](LICENSE)
