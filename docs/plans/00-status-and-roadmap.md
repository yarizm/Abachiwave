# Abachiwave 开发现状与路线图

> **历史快照：本文冻结于 2026-08-09，不再作为当前状态或优先级事实来源。**
>
> 当前实现见 [`../status.md`](../status.md)，后续顺序见 [`../roadmap.md`](../roadmap.md)，文档导航见
> [`../README.md`](../README.md)。保留本文仅用于追溯当时的阶段判断和实施记录。
>
> 状态快照：2026-08-09
>
> 以下内容按原样保留当时对系统、完成度和开发顺序的判断；后续不再更新其中的状态和验证数字。

## 1. 文档分工

| 文档 | 定位 | 是否描述当前实现 |
|---|---|---|
| `README.md` / `README.en.md` | 项目入口、启动和能力摘要 | 是，保持简洁 |
| `docs/architecture.md` | 已落地架构、数据流、版本模型和约束 | 是，架构事实来源 |
| `docs/api.md` | 当前 HTTP 契约和错误结构 | 是，接口事实来源 |
| `docs/runbook.md` | 本地运行、迁移、Worker、存储和排障 | 是，运维手册 |
| `docs/backup-restore.md` | PostgreSQL 与 MinIO 备份恢复 | 是，运维手册 |
| `docs/plans/01-product.md` | 首轮 MVP 原始规划 | 历史基线 |
| `docs/plans/03-milestone-7.md` | MVP 稳定化与封闭试用规划 | 历史里程碑 |
| `docs/plans/04-ux-improvement.md` | 错误契约、视觉、引导和易用性规划 | 大部分已实施 |
| `docs/plans/02-full-product.md` | Product v1 的 Milestone 8～13 长期路线 | 目标路线，不是完整现状 |
| `docs/superpowers/plans/2026-08-03-demo-audio-quality.md` | Demo 音质专项实施记录 | 专项计划，已完成核心实现 |

推荐阅读顺序：本文 → 架构 → API → 当前要开发的专项计划 → 测试与运行手册。

## 2. 当前产品定位

Abachiwave 已经不是单纯的 Agent Demo，而是一个本地优先、单用户的音乐创作工作台。用户可以从灵感创建结构化 SongSpec，继续生成和编辑歌词、和弦、MIDI、编曲与 Demo，并通过 Revision、评论、评审、handoff 和 ZIP 导出形成完整创作闭环。

当前产品仍然定位为高质量创作草稿和制作决策工具，不承诺发行级音频，也不适合直接暴露到公网。

## 3. 已落地架构

```text
Next.js Web
    │ REST + X-Request-ID
    ▼
FastAPI API ─────────────── PostgreSQL
    │                         项目、版本、任务、事件
    ├────────────── MinIO
    │               MIDI、WAV、上传和 ZIP
    └────────────── Redis / Arq
                       │
                       ▼
                    Worker
              文本候选、评测、Demo、audio-to-MIDI
```

核心约束：

- 所有正式创作资产使用专用版本表，编辑、Revision apply 和 restore 都新增版本，不覆盖历史。
- 同项目版本写入先锁定 `projects` 行，再分配版本号；唯一约束冲突只有限重试，最终返回稳定 `409`。
- SongSpec 的 `structure_sections` 提供稳定 `section_id`，歌词、和弦、MIDI 和编曲共享段落来源。
- 耗时任务统一进入 Arq；PostgreSQL 是任务终态和业务事实来源，Redis 只负责排队与通信。
- 二进制对象存 MinIO，数据库只存 storage key、checksum、size 和来源关系。
- 外部文本、音乐和音频能力通过 Provider 边界接入；离线测试保留 deterministic 实现。

## 4. 里程碑复盘

### Milestone 0～7：MVP 与稳定化

状态：已完成。

已覆盖项目管理、Idea Intake、SongSpec、歌词、和弦、MIDI、编曲、Demo、Revision、版本恢复、音频上传、评论、评审、handoff、导出、健康检查、结构化日志、并发版本保护、真实依赖 CI 设计和浏览器工作台拆分。

### Milestone 8：真实 AI 创作引擎

状态：工程能力基本完成，质量验收仍依赖真实 Provider 环境。

已完成：

- `TextGenerationProvider` 抽象和 OpenAI-compatible Provider。
- Provider profile、Prompt 版本、候选、选择后物化正式资产。
- SongSpec、歌词、编曲和 Revision 四类候选工作流。
- 32 条固定样例的 EvaluationRun、自动指标和匿名 A/B 人工评分。
- 无外部配置时的 deterministic fallback。

仍需持续验证：真实 Provider 的稳定性、成本、schema 合法率和人工盲评优势。

### Milestone 9：专业创作编辑器

状态：已完成核心范围。

已完成：

- 稳定段落时间线和两阶段结构变更。
- schema v2 结构化歌词、逐行改写预览、本地 draft、undo/redo。
- schema v2 和弦事件、music21 理论校验、移调、罗马/Nashville 显示和 Tone.js 试听。
- schema v2 MIDI、Canvas 钢琴卷帘、三轨查看、音符编辑、变换、draft 和 Tone.js 试听。

### Milestone 10：音频理解与参考分析

状态：进行中，是当前主线。

已有基础：

- WAV、MP3、M4A、FLAC、OGG 上传、原文件下载、元数据编辑和 archive/restore。
- WAV 同步分析；压缩格式自动排队生成标准 PCM WAV，完成后统一提供波形与浏览器播放。
- 本地确定性 fallback 与可选 Basic Pitch 的单旋律 audio-to-MIDI 任务和可编辑 MIDI 结果。
- Audio Marker 后端模型、迁移、CRUD、项目隔离、时长边界校验和事件记录。
- Audio Marker 前端数据加载、创建、编辑、删除、错误反馈、波形选点、播放头和 Marker seek 已接入工作台。
- 波形 analysis region 拖选、数值编辑、清除与片段试听；audio-to-MIDI 可只分析指定时间段。
- 可选 Spotify Basic Pitch audio-to-MIDI Provider、独立 Python 3.11 推理服务和专用队列。
- MIDI 保存 source upload、reference analysis、Provider manifest、校验和与范围血缘。

尚未完成：

- 波形缩放。
- 参考分析与 Basic Pitch 的真实曲库准确率、性能和资源占用验收。
- 参考分析的真实 Provider，以及更细粒度的候选置信度校正。

### Milestone 11～13

状态：尚未进入主开发。

- Milestone 11：真实 Demo variant、同步 A/B、region feedback、Stem 和局部重渲染。
- Milestone 12：Style/Lyrics Profile、模板、参考素材库和项目复制。
- Milestone 13：本地账号与角色、评论 thread、Review Snapshot、DAW 交付和项目归档导入。

## 5. 当前工作树

当前分支为 `main`，领先 `origin/main` 36 个提交，并存在一批未提交改动。不要通过 reset、checkout 或清理命令覆盖这些内容。

未提交工作的四个主要主题：

1. Demo 音质专项：CC0 鼓采样渲染、`DEMO_PROVIDER_NAME` 配置、Provider 来源记录和未知 Provider 明确失败。
2. Audio Marker 垂直切片：迁移、模型、schema、服务、API、前端编辑器和工作区接线。
3. 音频基础链路：多格式标准化、范围选择与参考音频分析候选。
4. 真实 audio-to-MIDI：Basic Pitch sidecar、专用队列、MIDI 来源血缘和实机 smoke。

Audio Marker 后端、前端交互和 Playwright E2E 用例已完成；Phase B 已接入 WAV、MP3、M4A、FLAC、OGG 校验、自动标准化状态机、PCM WAV 派生下载、统一试听、region 选区和分析范围 manifest。Phase C 已接入可追溯的参考音频分析版本、候选展示和安全的逐字段 SongSpec draft 应用。Phase D 已完成 Basic Pitch Provider/隔离服务、专用 Worker 队列、MIDI 来源血缘、真实 Compose smoke 和容器故障注入。当前剩余主项是扩展真实曲库质量门禁与目标环境容量验收，不再是基础环境接线。

## 6. 2026-08-09 验证结果

已通过：

```text
uv run ruff check .                         passed
uv run mypy                                 146 source files, no issues
uv run pytest -q                            227 passed
npm run lint                                passed
npm run typecheck                           passed
npm test                                    84 passed
npm run build                               passed
npx playwright test                         25 passed, 1 desktop-only skip
docker compose --profile basic-pitch --profile ffmpeg config  passed
docker compose --profile basic-pitch --profile ffmpeg up      passed
uv run alembic heads                        202608100001 (head)
docker compose exec api alembic current     202608100001 (PostgreSQL head)
uv run python support/validate_basic_pitch_faults.py  5 scenarios passed
git diff --check                            passed
```

真实链路已验证：

- PostgreSQL、Redis、MinIO、API、通用 Worker、audio MIDI Worker、ffmpeg Worker 和 Web 均通过健康检查；PostgreSQL 已升级到唯一 head。
- 真实 MP3 自动标准化成功，原始 bytes 保持不变，派生物为 48 kHz、双声道、16-bit PCM WAV，重复创建返回 `409`。
- Basic Pitch 0.4.0 / TensorFlow sidecar 完成模型预载；440 Hz WAV 直接推理返回 MIDI 69，并通过应用专用队列生成带完整 Provider/source manifest 的 MIDI 资产。
- 首次实机推理发现并修复非 root Numba cache；镜像契约测试防止回归。
- 容器级故障矩阵验证 sidecar 断连、恢复、超时、运行中取消和 MIDI Worker 重启；五种场景均保留稳定任务终态且无孤立 MIDI 资产。
- audio-to-MIDI 基准框架支持版本化 WAV/MIDI 真值集、tempo-aware 秒级解析、两级 F1、onset/pitch/duration/velocity 误差、空结果率、时延、RTF 与容器资源阈值；3 个合成 smoke 样例已通过真实 Basic Pitch 自检，但不计为真实曲库质量结论。
- 新增 NSynth 流式采集器，固定官方 archive ETag、许可证/来源、原始/标准化 WAV 与参考 MIDI checksum；7 个 acoustic 家族共 14 个真实单音样本已完成 Basic Pitch 观察基线。
- NSynth 基线改用与产品一致的 48 kHz、双声道、16-bit PCM；命中 14/14 参考音高但输出 48 个音符：overall onset+pitch F1 0.452、offset F1 0.065、空结果率 0、中位热时延 201 ms、RTF 0.050、峰值 CPU 261.73%、内存 716.3 MiB。结果暴露持续音/泛音过分段，不作为正式发布通过结论。
- 新增 GuitarSet 1.1.0 Range 采集器，校验 Zenodo record、CC BY 4.0、官方 ZIP 大小/MD5，逐样本记录音频与 JAMS member/SHA-256，并排除官方 issues 4/5 的已知错误标注。
- GuitarSet 两条 solo、两条 comp 共 785 个参考音符已完成观察基线：overall F1 0.744、solo F1 0.866、comp F1 0.714；overall offset F1 0.444、中位热时延 662 ms、RTF 0.022、峰值 CPU 385.94%、内存 720.6 MiB。
- Docker 资源采样从可能被 Windows CLI 缓冲的无限流改为 `--no-stream` 轮询；最短的三样本合成 smoke 也取得 CPU 74.61%、内存 715.5 MiB。
- benchmark manifest 支持多参考 MIDI、逐参考 checksum/annotation lineage、样本 attributes 与 A_max 选择策略；报告同时输出 micro 和逐曲 macro F1，并记录实际选中的 reference ID。
- Vocadito 官方 58.5 MB ZIP 已完成全量 MD5 校验和 40 条/80 份人工标注转换；两位标注者在相同 evaluator 下 macro no-offset/offset F1 为 0.722/0.633，与论文人类一致性结论接近。
- Basic Pitch Vocadito A_max 基线为 micro F1 0.508/0.332、macro F1 0.519/0.347、空结果率 0、中位热时延 522 ms、RTF 0.026、CPU 442.44%、内存 738.9 MiB，明显低于论文既有算法约 0.64/0.50 的 macro A_max。
- 全量 Playwright 在真实 Compose 栈执行：25 条通过，完整 MVP 只在桌面项目运行，移动项目按设计跳过 1 条。
- 浏览器 smoke 同时发现并修复 Marker 表单无障碍标签、DELETE CORS preflight、统一校验被原生表单短路、音频行窄栏溢出和旧多格式上传定位器。

仍需质量验收：

- 根据 Vocadito/GuitarSet 失败样例做 Provider 参数扫描或模型替换，达到可解释的目标质量后再固化正式阈值；当前不能把“无阈值违规”写成质量通过。
- 扩大 GuitarSet 的演奏者/风格与其他乐器覆盖，防止阈值只适配四条吉他 excerpt。
- 用不同长度音频测量冷启动、热推理和高负载下的 CPU/内存峰值，形成部署容量建议。

## 7. 下一阶段开发顺序

### Phase A：完成 Audio Marker 垂直切片

已完成：

- `audioMarkersEndpoint`、`audioMarkerEndpoint`、`sortAudioMarkers` 和两个 validator 的前端单测。
- Marker 编辑区域的专用 CSS 和移动端布局。
- 波形 Marker、播放头、点击波形选点和点击 Marker seek。
- `web/e2e/audio-marker.spec.ts`：桌面/移动端创建、跳转、编辑、删除和越界校验。
- `web/e2e/audio-derivative.spec.ts`：桌面/移动端触发 PCM WAV 标准化任务。

实机验证：PostgreSQL 迁移、桌面/移动 Marker 创建、seek、编辑、删除、越界校验和完整浏览器矩阵均已通过。

完成定义：Marker 不只存在于表单列表，还能与波形播放位置形成稳定交互锚点。

### Phase B：音频派生与格式统一

已完成：

- 新增 `audio_derivatives` 模型、`202608080001` migration、项目隔离列表 API 和 source checksum 幂等约束。
- 新增 `FfmpegAudioConverter` pipe 转换边界，统一输出 16-bit PCM WAV，并覆盖缺少 ffmpeg、超时、解码失败和非法输出。
- 新增 `audio_derivative` GenerationRun、`arq:audio-ffmpeg` 专用队列、`FFmpegWorkerSettings` 和 Compose `ffmpeg` profile。
- 工作区显示 derivative 状态，并可从音频上传行排队生成标准 PCM WAV。
- WAV、MP3、M4A、FLAC、OGG 使用扩展名、MIME 和魔数联合校验；压缩格式上传后自动排队。
- 上传状态覆盖 `processing / available / failed / archived`，解码失败、入队失败和取消均可重试且不会覆盖原文件。
- 派生下载接口与工作区统一试听已接入；压缩源 audio-to-MIDI 使用 ready PCM WAV。
- 新增 `202608080002` migration，为上传记录保存源格式，并允许标准化前的分析元数据为空。
- 波形支持 analysis region 拖选、起止时间编辑、清除和片段试听；提取请求可提交可选范围。
- 每个新 audio-to-MIDI run 都保存显式 full/selection manifest；Worker 按帧裁剪 WAV 后再调用 Provider，并记录原始与实际分析字节数。
- 新增后端范围校验/裁剪集成测试和 `web/e2e/audio-region.spec.ts` 桌面/移动端浏览器用例。

实机验证：MP3 → 标准 PCM WAV、原文件保留、派生下载、幂等冲突和桌面/移动浏览器 smoke 均已通过。

### Phase C：参考音频分析

已完成基础垂直切片：

- 定义 `AudioAnalysisProvider` contract 和 `local_deterministic_reference_analysis` fixture Provider。
- 新增 `reference_analysis_versions`、`reference_analysis` 任务类型、API、Worker 和来源追踪。
- 实现 tempo/beat、拍号、key/mode、音域、响度/能量、结构、和弦、乐器与制作特征候选。
- 工作区展示分析范围、Provider 版本和逐字段置信度，完成任务不会自动覆盖正式资产。
- 支持对 tempo、key、time signature 做影响预览；确认后创建新的 SongSpec draft，approved 来源和关联资产保持不变。
- 新增 Provider、API/Worker/迁移测试和桌面/移动 Playwright E2E 用例。

后续增强：

1. 用真实曲库评测或替换 deterministic 基线 Provider，建立 BPM、key、结构与和弦的容差指标。
2. 结构和和弦候选需通过各自的版本化编辑/资产工作流应用，不直接扩张当前 SongSpec 字段写入。
3. 增加长音频波形缩放和更细粒度的候选校正交互。

### Phase D：真实 audio-to-MIDI

已完成工程基础与实机 smoke：

- 定义 `AudioToMidiProvider` contract，保留 `local_monophonic_wav_to_midi` 作为测试基线和离线 fallback。
- 新增 `spotify_basic_pitch` HTTP Provider；Basic Pitch 0.4.0 在隔离的 Python 3.11 sidecar 中运行，不把模型依赖装入主 Python 3.12 API/Worker。
- 新增 `arq:audio-midi` 专用队列和 `audio-midi-worker`；API、通用 Worker 与 ffmpeg Worker 均不消费该队列。
- run 固定 upload、PCM derivative、reference analysis、两级 checksum、分析范围和 Provider identity；Worker 对来源不匹配明确失败。
- `midi_asset_versions` 保存 `source_reference_analysis_id` 和 `source_provider_manifest`；编辑、变换、Revision 与 restore 继承来源。
- 工作区在提取前展示匹配的 analysis version，提取后展示分析/Provider 来源；钢琴卷帘继续支持休止、连音、力度、scale snap 和人工音符修正。
- 兼容升级前已排队、尚无 checksum/range 扩展字段的 run；只补解析缺失值，不容忍显式不匹配。
- 构建并运行 Basic Pitch 0.4.0 / TensorFlow 镜像；修复非 root Numba cache 后，直接推理与应用级 WAV → MIDI 均成功。
- 真实应用 run 由 `audio-midi-worker` 消费并生成 1 个 A4 音符，Provider usage、checksum、范围和 MIDI 下载均已校验。
- 新增 `support/validate_basic_pitch_faults.py`，自动恢复原配置并验证断连、恢复、超时、取消和 Worker 重启；任务分别落入可诊断终态且无对象残留。
- Provider 区分 timeout、unavailable 和 invalid response；Worker 优雅中断写入 `task_interrupted`，执行器拒绝再次处理终态 run。
- 新增 `support/benchmark_audio_to_midi.py`、合成数据生成器和 manifest/指标文档；Basic Pitch 合成自检为 7/7 音符命中，轮询采样后热推理中位数约 0.14 秒、RTF 约 0.07、CPU 74.61%、内存 715.5 MiB。
- manifest 对真实数据集强制要求许可证/来源 URL，并校验标准化 WAV、参考 MIDI SHA-256；转换型样本记录 archive member 和原始音频 SHA-256。
- 新增 `support/fetch_nsynth_benchmark_subset.py`，通过 HTTPS/固定 ETag 流式抽取 7 个 acoustic 家族各 2 个独立音高，不落盘完整 archive。
- NSynth 14 样本观察基线已完成：所有参考音高均命中，但 48 个预测音暴露明显过分段；overall onset+pitch F1 0.452、offset F1 0.065、空结果率 0、中位热时延 201 ms、RTF 0.050、峰值 CPU 261.73%、内存 716.3 MiB。
- 新增远程 seekable ZIP reader 和 `support/fetch_guitarset_benchmark_subset.py`；通过 Range 请求抽取两条 solo/两条 comp，并把 JAMS `note_midi` 转成 tempo-aware 参考 MIDI。
- GuitarSet 785 音符基线：solo onset+pitch/offset F1 为 0.866/0.708，comp 为 0.714/0.380；总体中位热时延 662 ms、RTF 0.022、CPU 385.94%、内存 720.6 MiB。
- 新增 `support/fetch_vocadito_benchmark_dataset.py` 和参考一致性工具；40 条真实演唱完整保留 A1/A2，A_max 选择 A2 26 条、A1 14 条。
- Vocadito 人类 macro F1 为 0.722/0.633，Basic Pitch 仅 0.519/0.347；转换口径已由人类一致性复现验证，当前瓶颈落在 Provider 质量。

待完成：

1. 针对 Vocadito 低分样本运行 Basic Pitch 参数扫描，确认默认阈值能否显著改善；若无法接近公开 Vocano 基线，评估替换/组合 Provider。
2. 扩大 GuitarSet 乐句覆盖，并在目标硬件上确定质量回归阈值与容量上限；正式阈值必须区分 regression gate 和 product release gate。
3. 根据质量结果补充置信度/警告显示；若 Provider 不提供可靠的逐音符置信度，不伪造该字段。

### Phase E：进入 Milestone 11

只有在 Reference Analysis 和结构化 MIDI 来源链稳定后，再开发真实 Demo variant、同步 A/B、region feedback、Stem 和局部重渲染。这样可以避免 Demo 层先于输入约束成熟，形成第二套不可追溯状态。

## 8. 优先级与风险

当前最高优先级不是继续增加更多模型，而是完成“音频输入 → 可定位 → 可分析 → 可确认应用”的一条完整链路。

主要风险：

- Audio Marker 只停留在表单层，会失去作为波形选区和局部反馈锚点的价值。
- 先做真实 Demo/Stem、后补 Reference Analysis，会让 Provider 输入来源不稳定。
- 音频分析结果若直接写入 SongSpec，会破坏候选确认和不可变版本语义。
- ffmpeg、Basic Pitch、librosa 等大型依赖若进入普通 API 进程，会放大启动时间和部署复杂度。
- 计划文档若继续同时承担历史记录、当前状态和未来目标，容易再次产生完成度漂移。

## 9. 文档维护规则

- `docs/architecture.md` 只写已经落地的架构事实，不写尚未实现的目标。
- `docs/api.md` 与代码接口同批更新，未实现接口只保留在计划文档。
- 本文在每个完整垂直切片完成后更新一次状态和验证结果。
- `docs/plans/02-full-product.md` 保持 Product v1 目标和依赖顺序，不承担每日进度记录。
- 专项计划完成后保留为实施记录，不再作为当前入口。
- 每个里程碑用“已完成 / 进行中 / 未开始 / 受阻”四种状态，避免只依赖过时 checkbox。
