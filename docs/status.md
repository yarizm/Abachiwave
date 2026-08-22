# Abachiwave 当前状态

> 快照日期：2026-08-22
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
- `local_monophonic_wav_to_midi` fallback 与可选 Basic Pitch 0.4.0 sidecar。
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

这些结果是模型选择证据，不是正式 release gate。详细口径见
[`audio-to-midi-benchmark.md`](audio-to-midi-benchmark.md)。

## 5. 当前验证证据

2026-08-22 对当前 HEAD 验证：

```text
uv run ruff check .     passed
uv run mypy             148 source files, no issues
uv run pytest -q        233 passed
uv run alembic heads    202608100001 (head)
npm run lint            passed
npm run typecheck       passed
npm test                84 passed
```

同日 `basic-pitch` sidecar 以 Basic Pitch 0.4.0 / TensorFlow runtime 就绪，完成 440 次真实推理的
Vocadito 参数扫描，中位 RTF 0.023、中位时延 0.44 s、空结果率 0。

`npm run build`、Playwright e2e 与完整 Compose 栈本轮**未**重跑；最近一次为 2026-08-09：

```text
npm run build           passed
npm run test:e2e        25 passed, 1 desktop-only skip
Basic Pitch faults      5 scenarios passed
```

当时 PostgreSQL、Redis、MinIO、API、Web、通用 Worker、ffmpeg Worker 和 audio MIDI Worker 均通过
健康检查，真实 MP3 标准化与应用级 Basic Pitch 转录成功。这是最近的全栈实机证据，不表示这些服务
此刻在线。

## 6. 当前工作树与风险

- 分支为 `main`，工作树干净，尚未推送 `origin/main`。
- 原先的大批未提交修改已按依赖序拆成 7 个提交：gitignore、数据层、Provider/Worker、API/编排、
  前端、评测框架、文档。每个提交是一个独立审查单元。
- 当前 migration 只有一个 head：`202608100001`。
- 大多数新功能已有单元/API/浏览器覆盖；`npm run build` 与浏览器 e2e 尚未在当前 HEAD 上重跑。
- Compose 使用默认开发凭据、开发服务器和绑定挂载，不是生产部署方案。

## 7. 当前未完成项

- 完成替换或组合 Audio-to-MIDI Provider 的同口径比较；Basic Pitch 调参已探完，不再是可行路径。
- 补齐 `onset 0.60` 在 GuitarSet 上的退化证据，再决定是否把它固化为默认参数。
- 扩大 GuitarSet 演奏者、风格、乐器和不同长度音频覆盖，建立容量建议。
- 为参考分析接入真实 Provider，并建立 BPM、key、结构和和弦的容差评测。
- 增加长音频波形缩放和基于真实 Provider 能力的警告/置信度交互。
- 区分日常 regression gate 与 product release gate，不把空阈值报告解释为质量通过。
