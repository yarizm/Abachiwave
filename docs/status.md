# Abachiwave 当前状态

> 快照日期：2026-08-16
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

已完成按 `singer_id` 隔离的 30 条开发集 / 10 条留出集参数扫描：

- `onset_threshold=0.60`：开发集 offset F1 比默认值提高 0.053，留出集提高 0.047，留出集达到 0.410。
- `onset_threshold=0.75`：开发集提高 0.083，留出集提高 0.045，留出集为 0.408。
- `0.75` 的开发集优势没有在留出歌者上扩大，当前不能只按开发集最高分固化它。
- `0.80～0.95` 扩展候选已写入定义但尚未运行；即使现有调参收益成立，距离 0.50 offset 观察目标仍有差距。

这些结果是模型选择证据，不是正式 release gate。详细口径见
[`audio-to-midi-benchmark.md`](audio-to-midi-benchmark.md)。

## 5. 当前验证证据

2026-08-16 当前工作树验证：

```text
uv run ruff check .    passed
uv run mypy            148 source files, no issues
uv run pytest -q       233 passed
uv run alembic heads   202608100001 (head)
```

最近一次完整前端与真实 Compose 验证为 2026-08-09：

```text
npm run lint            passed
npm run typecheck       passed
npm test                84 passed
npm run build           passed
npm run test:e2e        25 passed, 1 desktop-only skip
Basic Pitch faults      5 scenarios passed
```

当时 PostgreSQL、Redis、MinIO、API、Web、通用 Worker、ffmpeg Worker 和 audio MIDI Worker 均通过
健康检查，真实 MP3 标准化与应用级 Basic Pitch 转录成功。当前 Docker Desktop 未启动，因此这些是
最近的实机证据，不表示服务此刻在线。

## 6. 当前工作树与风险

- 分支为 `main`，领先 `origin/main` 36 个提交。
- 音频链路、Provider、评测、前后端和文档形成一批较大的未提交修改；不得通过 reset、checkout
  或清理命令覆盖。
- 当前 migration 只有一个 head：`202608100001`。
- 大多数新功能已有单元/API/浏览器覆盖，但参数扫描扩展、文档重组和最终完整矩阵尚未形成一个
  可审查的提交边界。
- Compose 使用默认开发凭据、开发服务器和绑定挂载，不是生产部署方案。

## 7. 当前未完成项

- 跑完 Basic Pitch 尾部参数曲线，决定稳健参数并执行最终全量/资源复测。
- 若无法达到观察目标，完成替换或组合 Audio-to-MIDI Provider 的同口径比较。
- 扩大 GuitarSet 演奏者、风格、乐器和不同长度音频覆盖，建立容量建议。
- 为参考分析接入真实 Provider，并建立 BPM、key、结构和和弦的容差评测。
- 增加长音频波形缩放和基于真实 Provider 能力的警告/置信度交互。
- 区分日常 regression gate 与 product release gate，不把空阈值报告解释为质量通过。
