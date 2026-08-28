# Abachiwave 当前状态

> 快照日期：2026-08-25
>
> 本文只记录当前已证明的实现和风险；后续工作见 [`roadmap.md`](roadmap.md)。

## 1. 产品定位

Abachiwave 是本地优先、单用户的音乐创作工作台。它把灵感、歌词、哼唱和参考音频组织为可编辑、
可追溯、可导出的 SongSpec、歌词、和弦、MIDI、编曲、Demo、Revision 和交付资产。

当前适合作为高质量创作草稿与制作决策工具，不承诺发行级音频，也不具备可直接暴露公网的认证、
权限和生产部署配置。

## 2. 里程碑概览

| 范围 | 状态 | 当前结论 |
| --- | --- | --- |
| Milestone 0～7：MVP 与稳定化 | 已完成 | 本地完整创作闭环、版本化、任务、导出、评审和运维基础已落地 |
| Milestone 8：真实 AI 创作引擎 | 工程基本完成 | Provider、候选、评测和选择物化已完成；真实模型稳定性、成本和盲评优势待持续验证 |
| Milestone 9：专业创作编辑器 | 核心范围完成 | 统一结构时间线、结构化歌词/和弦/MIDI 编辑与试听已落地 |
| Milestone 10：音频理解与参考分析 | 进行中，当前主线 | 音频基础链路完成；真实 Provider 质量与容量门禁尚未关闭 |
| Milestone 11～13 | 尚未进入主开发 | Demo variant/Stem、Profile/素材库、账号协作/DAW 交付仍属后续阶段 |

## 3. 已落地能力

### 创作与版本

- Idea Intake、澄清问题、结构化 SongSpec、审批与版本历史。
- 歌词、和弦、三类 MIDI、编曲方案和 Demo 的生成、编辑、试听与下载。
- Revision 影响预览、局部应用、diff、恢复、项目事件和并发版本保护。
- 评论、项目评审、handoff 摘要、资产树和 ZIP 导出。
- 所有正式资产采用不可变版本；数据库保存业务状态，对象二进制进入 MinIO。

### 专业编辑器

- 稳定 `section_id` 驱动的统一段落时间线和两阶段结构变更。
- 结构化歌词逐行编辑、局部改写、本地 draft、undo/redo。
- 和弦拍点网格、移调、理论提示、罗马/Nashville 显示和 Tone.js 试听。
- Canvas 钢琴卷帘、三轨叠加、音符编辑、复制、量化、移调、scale snap 和试听。

### 音频理解

- WAV、MP3、M4A、FLAC、OGG 上传，原始文件下载、元数据编辑和 archive/restore。
- 压缩格式通过独立 ffmpeg Worker 生成 48 kHz、双声道、16-bit PCM WAV；原始文件不覆盖。
- 波形、播放头、Audio Marker CRUD/seek 和 analysis region 拖选、数值编辑、清除与片段试听。
- 可追溯的参考音频分析候选；应用 tempo、key、time signature 时创建新的 SongSpec draft。
- `local_monophonic_wav_to_midi` fallback 与可选 Basic Pitch 0.4.0 sidecar，默认 `onset_threshold=0.6`。
- 独立 `arq:audio-midi` 队列、MIDI 来源 checksum、分析范围、Provider manifest 和版本血缘。
- timeout、断连、非法响应、取消和 Worker 中断均有稳定任务错误码，并避免物化孤立资产。

## 4. Audio-to-MIDI 质量证据

当前评测框架覆盖版本化 manifest、许可证与来源、逐文件 checksum、tempo-aware MIDI 解析、
micro/macro F1、offset F1、误差、空结果率、时延、RTF、CPU/内存和多参考 A_max。

| 数据集 | 覆盖 | Basic Pitch 观察结果 |
| --- | --- | --- |
| NSynth | 7 个 acoustic 家族、14 个单音 | 音高均命中，但 14 个参考音产生 48 个预测音，offset F1 0.065 |
| GuitarSet | 2 条 solo、2 条 comp、785 个音符 | overall no-offset/offset F1 0.744/0.444；solo 明显优于 comp |
| Vocadito | 40 条演唱、29 位歌者、双人工标注 | 默认参数 macro no-offset/offset F1 0.519/0.347 |

Vocadito 两位人工标注者在同一 evaluator 下的 macro no-offset/offset F1 为 0.722/0.633，说明
转换与容差口径可信，当前主要瓶颈位于 Provider。

2026-08-22 已跑完按 `singer_id` 隔离的 14 候选完整扫描（30 条开发集 / 10 条留出集）。baseline、
`onset 0.60`、`onset 0.75` 的开发集与 baseline 留出集结果与 2026-08-09 完全一致，两轮可比：

- 开发集 offset F1 在 `onset 0.80` 见顶（0.428），`0.85` 起单调下降；4 个 `onset/frame` 组合全部跑输
  同 onset 的纯阈值候选。
- 开发集冠军 `onset 0.80` 的留出集 offset F1 只有 0.381，增益 +0.018，低于 0.02 阈值，也低于
  `onset 0.60` 的 +0.047。开发集排名在尾部与留出集泛化反相关。
- `onset 0.60` 仍是最稳健候选（留出集 0.410），但距 0.50 观察目标仍差 0.09。
- 沿曲线 precision 从 0.491 升到 0.694，recall 从 0.507 降到 0.443：剩余差距来自漏音，不是阈值位置。
- 结论是 onset threshold 的调参空间已探完，模型差距无法靠调参关闭。

同日在 GuitarSet 4 条 excerpt 上复现 baseline 并完成 `onset 0.60` 退化验证：overall offset F1
0.444→0.474、solo 0.708→0.728、comp 0.380→0.409，三个类别均无退化；时长 MAE 与 P95 时延同步
改善，资源占用持平。该参数在 Vocadito 上选出、GuitarSet 未参与选参，属跨数据集独立确认。

2026-08-23 补做止音误差分解，检验"加一层止音精修即可达标"这条线索。完美止音层的上限就是
no-offset F1：留出集补满 0.163 缺口即可从 0.410 到 0.572，确实能越过 0.50。但误差是无偏对称散布，
不是可移除的偏置——留出集有符号时长误差中位数 +0.1 ms、预测/参考时长比中位数 1.0005、越界样本
在偏长与偏短之间 50.6/49.4 开。时长缩放与平移的网格搜索最佳收益在开发集 +0.009、留出集 +0.002，
任何强到有意义的变换都使指标下降。结论：止音缺口真实，但收回它需要逐音符声学证据而非后处理，
这条线索关闭，替代 Provider 比较是唯一剩余路径。

2026-08-24 把剩余缺口分解到失败类型，并否掉第一个替代候选。约 42% 的参考音符没有对应起音，
其中近一半是被同音高长音符盖住的**欠切分**而非漏检（开发集 611 未匹配中 276 合并、262 未覆盖）。
起音召回 0.58–0.60 是当前约束条件。四族纯后处理全部无效（止音变换 +0.002、单声部消解 −0.006 至
−0.003、pYIN 重指派音高 +0.002、pYIN 引导切分 −0.000）。pYIN + 音符分割管线开发集调到头是
0.467/0.332，落后 Basic Pitch 0.090/0.062；但给定 oracle 边界时 pYIN 音高能到 0.814/0.811，说明
瓶颈是音符分割不是 f0——换 f0 估计器无用，需要学习到的切分模型。

2026-08-25 完成第一个可用替代 Provider 的同口径比较。YourMT3+（Apache-2.0，45.8M 参数，CPU 可跑）
单独使用**劣于** Basic Pitch（留出 offset F1 0.357 vs 0.410），但三部件组合
`YourMT3 边界 + pYIN 音高 + 时长 ×0.85` 在留出集达到 0.623 / 0.441，offset F1 增益 +0.031，
超过 0.02 阈值。三者各补一块短板：YourMT3 把起音召回从 0.581 拉到 0.783；pYIN 补音高
（起音对齐音高准确率 Basic Pitch 87.6–92.0%、YourMT3 仅 70.3–70.8%，且非八度错误、非整轨调音）；
时长缩放补止音——YourMT3 的时长误差是**有偏**的（中位 +29.2 ms、越界中 78% 偏长），因此第 10 节
在 Basic Pitch 上失效的方法在此处生效。

代价：中位 RTF 0.023 → 0.824（约 36 倍），进程峰值内存 770 MiB → 2205 MB，权重 536 MB 加 PyTorch。
留出 0.441 距 0.50 观察目标仍差 0.059。GuitarSet 的绝对分（0.902/0.790）**不可用**——YourMT3 训练混合
包含 `guitarset_pshift`，本子集演奏者很可能被训练过；器乐类别的绝对比较需要一个不在 MT3 训练混合
中的数据集（NSynth 已确认不在其中，尚未采集）。

但同一音频上的系统内对比不受泄漏影响，并给出一个确定结论：该组合是**人声专用**的。pYIN 同一时刻
只能给一个音高，复调 offset F1 从 0.769 塌到 0.077。因此不存在统一替换默认 Provider 的选项，必须
按素材类型显式路由；而路由判据不能用输出 MIDI program（人声 program 100/101 在 40 条中出现 0 次）。
第四部件（Basic Pitch 音高回退）已否：开发集 −0.015、留出集 +0.014，方向相反且低于阈值。

这些结果是模型选择证据，不是正式 release gate。详细口径见
[`audio-to-midi-benchmark.md`](audio-to-midi-benchmark.md)。

## 5. 当前验证证据

2026-08-22 完成完整验证矩阵；2026-08-23 与 2026-08-24 的评测分析只改动 Python 与文档，因此重跑了
后端三项（ruff / mypy / pytest），前端与 Compose/e2e 行沿用 2026-08-22 的结果：

```text
uv run ruff check .              passed
uv run mypy                      148 source files, no issues
uv run pytest -q                 239 passed
uv run alembic heads             202608100001 (head)
npm run lint                     passed
npm run typecheck                passed
npm test                         84 passed
npm run build                    passed
docker compose up -d --build     8 services healthy
scripts/smoke_mvp.py             ok
npm run test:e2e                 25 passed, 1 desktop-only skip
Basic Pitch faults               5 scenarios passed
compressed decode (ffmpeg)       mp3/m4a/flac/ogg all passed
GitHub Actions CI                5 jobs green
```

PostgreSQL、Redis、MinIO、API、Web、通用 Worker、audio MIDI Worker 和 `basic-pitch` sidecar 均通过
健康检查，`/health/ready` 三个依赖全部 ok。smoke 覆盖完整创作链，含音频上传与 MIDI 抽取。

故障矩阵 5 个场景的终态与 runbook 规定一致：`sidecar_disconnect` →
`audio_to_midi_provider_unavailable`、`sidecar_recovery` → `succeeded`、`sidecar_timeout` →
`audio_to_midi_provider_timeout`、`running_cancel` → `task_cancelled`、`worker_restart` →
`task_interrupted`。注入结束后各容器与 Provider 设置均已恢复。

同日 `basic-pitch` sidecar 完成 440 次真实推理的 Vocadito 参数扫描，中位 RTF 0.023、中位时延
0.44 s、空结果率 0。

2026-08-23 `support/analyze_audio_to_midi_offsets.py` 在同一 sidecar 上对 40 条 Vocadito 重新推理，
`identity` 在开发集与留出集分别复现出 0.557/0.394 与 0.572/0.410，与第 4 节记录一致。

`ffmpeg` profile 下对 MP3、M4A、FLAC、OGG 各上传一份真实压缩音频：格式识别正确，派生统一为
48 kHz、双声道、16-bit PCM WAV，派生 `source_checksum` 指回源文件，原始文件下载后与上传字节
完全一致，确认标准化不覆盖原件。

本批工作首次进入 GitHub Actions 时暴露两个本地环境测不出的问题，均已修复并在 CI 复验：

- `extract_midi_from_audio_job` 迁到 `arq:audio-midi` 专用队列后，integration job 仍只启动默认队列
  worker，smoke 的转录任务一直停在 `queued` 直到超时。本地 Compose 恰好有 `audio-midi-worker`
  服务，因此掩盖了这个缺口。
- `npm audit --audit-level=high` 报出 postcss 与 sharp 通告。两者均通过 `overrides` 收敛，未升级
  Next 大版本。

## 6. 当前工作树与风险

- 分支为 `main`，工作树干净，已推送 `origin/main`；CI 五个 job 全绿。
- 原先的大批未提交修改已按依赖序拆成 7 个提交：gitignore、数据层、Provider/Worker、API/编排、
  前端、评测框架、文档。每个提交是一个独立审查单元。
- 当前 migration 只有一个 head：`202608100001`。
- 新功能已有单元、API、浏览器、故障注入和真实压缩格式解码覆盖。
- Compose 使用默认开发凭据、开发服务器和绑定挂载，不是生产部署方案。

## 7. 当前未完成项

- 完成替换或组合 Audio-to-MIDI Provider 的同口径比较；Basic Pitch 调参已探完，不再是可行路径。
- 补齐 `onset 0.60` 在 GuitarSet 上的退化证据，再决定是否把它固化为默认参数。
- 扩大 GuitarSet 演奏者、风格、乐器和不同长度音频覆盖，建立容量建议。
- 为参考分析接入真实 Provider，并建立 BPM、key、结构和和弦的容差评测。
- 增加长音频波形缩放和基于真实 Provider 能力的警告/置信度交互。
- 区分日常 regression gate 与 product release gate，不把空阈值报告解释为质量通过。
