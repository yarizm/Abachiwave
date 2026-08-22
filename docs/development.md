# Abachiwave 开发指南

本文定义从接手任务到交付验证的日常工程流程。启动与排障命令见 [`runbook.md`](runbook.md)，
系统不变量见 [`architecture.md`](architecture.md)。

## 1. 开始任务前

1. 阅读 [`status.md`](status.md)，确认当前完成度和已知风险。
2. 阅读 [`roadmap.md`](roadmap.md)，确认任务所属阶段和退出条件。
3. 执行 `git status --short --branch`；当前仓库可能存在用户未提交修改，禁止用 reset、checkout 或
   clean 覆盖不属于本任务的内容。
4. 搜索最近的 migration head、Provider contract、API schema 和对应测试，不从历史计划猜实现。
5. 对多步骤任务写简短计划；每一步必须对应可检查的代码、测试、报告或运行状态。

## 2. 本地环境

```bash
uv sync --all-groups --frozen
cd web && npm ci && cd ..
docker compose up -d --build
docker compose ps
```

可选服务：

```bash
# 压缩音频标准化
docker compose --profile ffmpeg up -d --build

# Basic Pitch 模型服务
docker compose --profile basic-pitch up -d --build
```

Basic Pitch 使用独立 Python 3.11 镜像；不要把其 TensorFlow/Numba 依赖安装进主 Python 3.12
环境。完整环境变量和 timeout 约束见 `.env.example` 与 runbook。

## 3. 代码边界

### API 与服务

- Router 负责 HTTP 合同、依赖注入和响应状态，不承载音频解码或模型推理。
- Service 负责项目隔离、状态转换、版本分配、来源校验和事务边界。
- Schema 是公开合同；数据库 storage key、内部队列细节和敏感配置不得泄漏到响应。
- 所有项目子资源读取和写入都必须同时检查 `project_id`。

### 资产与版本

- 正式创作资产只新增版本，不原地覆盖。
- Revision apply、restore、编辑和模型输出必须继承来源字段。
- 原始上传不可覆盖；转码、分析和模型输出保存为派生物或独立版本。
- 新版本号在锁定项目行后分配；并发冲突只做有限重试并返回稳定错误。

### 异步任务

- API 创建 `generation_runs` 并排队，Worker 执行耗时操作。
- PostgreSQL 是终态事实来源；不得依赖 Redis job 状态替代业务状态。
- Provider 调用前、对象写入前和数据库提交前检查取消/终态。
- 失败、取消或提交异常必须尽力清理未引用对象。
- ffmpeg 和 audio-to-MIDI 使用专用队列与 Worker，不进入 API 或通用 Worker。

### Provider

- Provider 名称、版本、参数、输入 checksum 和范围在创建 run 时固定。
- Worker 必须按记录重建 Provider；不可用时明确失败，不静默切换 fallback。
- 未知参数必须拒绝，不能保留在 lineage 中却不影响实际推理。
- 新模型先进入离线评测，再进入应用默认配置。

### Web

- API URL、排序、校验和状态判断放在 `web/src/lib`。
- 数据加载、副作用和展示组件分离；长任务只轮询 active run，终态后再刷新工作区。
- 编辑器先维护本地 draft，保存时创建不可变版本。
- 新交互必须覆盖键盘/标签、错误恢复、窄屏和桌面/移动布局。

## 4. 数据库变更

1. 新建 migration，`down_revision` 指向当前唯一 head。
2. 模型、schema、服务和 API 同步修改，避免只改 ORM。
3. 对旧行和升级前排队任务定义兼容策略；显式来源不匹配不得容错回退。
4. 至少验证：

```bash
uv run alembic heads
uv run alembic upgrade head
uv run pytest -q tests/test_migrations.py
```

5. 高风险迁移在 PostgreSQL Compose 环境验证；SQLite 单测不能证明 PostgreSQL DDL 完全正确。

## 5. 验证矩阵

### 快速反馈

```bash
uv run ruff check .
uv run mypy
uv run pytest -q path/to/affected_tests.py

cd web
npm run typecheck
npm test -- --run
```

### 合并前完整验证

```bash
uv run ruff check .
uv run mypy
uv run pytest -q
uv run alembic heads
git diff --check

cd web
npm run lint
npm run typecheck
npm test -- --run
npm run build
npx playwright test --list
```

### 真实依赖与浏览器

```bash
docker compose --profile ffmpeg --profile basic-pitch up -d --build
uv run alembic upgrade head
uv run python scripts/smoke_mvp.py
cd web && npm run test:e2e
```

模型、ffmpeg、对象存储或 Worker 改动不能只靠 mock 测试完成；必须保留一条真实 Compose 证据。

## 6. Audio-to-MIDI 与模型变更

1. 固定数据集版本、来源、许可证和 checksum。
2. 参数选择使用开发集；歌手、演奏者或曲目组不能跨开发/留出分区。
3. 留出集只验证开发集选出的候选，不用来反复人工挑参。
4. 比较同一容差下的类别质量、时延、RTF、CPU、内存和失败样例。
5. 将报告写到临时/外部 artifact 目录，不提交第三方音频。
6. regression gate 与 product release gate 分开；空阈值报告不等于质量通过。

完整命令和指标见 [`audio-to-midi-benchmark.md`](audio-to-midi-benchmark.md)。

## 7. 文档更新矩阵

| 变更 | 必须同步 |
| --- | --- |
| API 路径、请求、响应、错误码 | `api.md`、相关客户端与合同测试 |
| 组件、队列、数据流、不变量 | `architecture.md` |
| 启动命令、服务名、环境变量、排障 | `runbook.md`、`.env.example` |
| 当前完成度或验证结论 | `status.md` |
| 优先级、阶段或退出条件 | `roadmap.md` |
| 数据集、指标、模型或参数结论 | `audio-to-midi-benchmark.md` |
| 新的 canonical 文档 | `docs/README.md` 与根 `README.md` |

历史计划不回填为当前事实；必要时添加“已归档/被替代”提示并链接 canonical 文档。

## 8. 完成定义

一个开发项只有同时满足以下条件才算完成：

- 用户可见行为和失败行为均已实现。
- schema、迁移、来源、不变量和并发语义明确。
- 受影响单元/API/浏览器测试通过；高风险外部依赖有真实运行证据。
- 没有覆盖用户已有修改、提交第三方数据或遗留孤立对象。
- architecture/API/runbook/status/roadmap 中受影响的事实已经同步。
- 剩余限制被明确记录，没有用“任务成功”替代质量结论。
