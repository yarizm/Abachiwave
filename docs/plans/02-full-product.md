# Abachiwave 完整功能产品 v1 后续开发计划

> 文档状态：Product v1 长期目标与需求基线。本文不表示当前完成度，部分差距已经关闭。当前事实见
> [`../status.md`](../status.md)，近期执行顺序见 [`../roadmap.md`](../roadmap.md)。

## 1. 阶段定位

本文最初以本地优先 MVP 为起点定义 Product v1 需求。后续实现已经完成其中一部分专业编辑器、
多格式音频和来源追踪能力；下面的差距清单应作为需求背景阅读，不能据此判断当前实现。

后续目标不是建设生产基础设施，而是把 MVP 扩展为一个产品能力完整、可以持续完成真实歌曲前期创作的 `Product v1`。

本计划重点解决六类差距：

1. 当前 Agent 和 Provider 主要是确定性占位实现，创作质量不足。
2. 核心资产虽然可编辑，但缺少歌词、和弦和 MIDI 的专业可视化编辑体验。
3. 音频输入只支持 WAV 和基础单旋律估算，不能分析常见参考音频。
4. Demo 只是本地试听占位稿，没有真实音乐生成、Stem 和局部重渲染能力。
5. 缺少个人风格记忆、模板、参考素材库和项目复用。
6. 评论、交接和导出已有基础，但缺少完整协作流程与 DAW 友好交付。

## 2. Product v1 完成定义

Product v1 完成后，用户应能够：

```text
从灵感、模板、参考音频或哼唱开始
→ 使用真实 AI 生成多个可选创作方向
→ 在同一时间线内精编辑歌词、和弦、旋律与编曲
→ 分析参考音频并提取节拍、调式、结构和旋律草稿
→ 生成多个真实 Demo/Stem 版本并 A/B 对比
→ 用自然语言或可视化工具执行局部修改
→ 复用个人风格、模板和素材
→ 邀请协作者进行评审和评论
→ 导出可继续进入 DAW 的完整项目包
```

产品完成不等于生成可直接发行的母带。Abachiwave v1 的交付定位仍是高质量创作草稿、制作决策和可继续编辑的工程素材。

## 3. 本轮明确不做

- Kubernetes、多区域部署、自动扩缩容和 SLA。
- 生产级高可用数据库、Redis Cluster 或分布式 MinIO。
- 计费、订阅、发票、商业配额和运营后台。
- 企业 SSO、复杂组织架构、合规认证和公开互联网运营。
- 歌手音色克隆、特定艺人仿声或版权保证。
- 自动发行、版权登记、音乐分发和专业母带服务。
- Ableton、Logic 等私有格式的完整原生工程生成；优先提供标准交换格式。

本地账号、项目成员和评审权限属于产品功能，可以实现；其目标是验证完整协作体验，不代表已达到公网安全标准。

## 4. 总体阶段规划

| Milestone | 主题 | 建议周期 | 核心结果 |
|---|---|---:|---|
| 8 | 真实 AI 创作引擎 | 3～4 周 | LLM Provider、候选方案、Prompt 版本和质量评估 |
| 9 | 专业创作编辑器 | 4～5 周 | 歌词、和弦、钢琴卷帘、统一段落时间线 |
| 10 | 音频理解与参考分析 | 3～4 周 | 常见音频导入、Basic Pitch、节拍/调式/结构分析 |
| 11 | 真实 Demo、Stem 与局部重渲染 | 4～5 周 | 外部音乐 Provider、多版本 Demo、Stem、A/B 与局部反馈 |
| 12 | 风格记忆、模板与素材库 | 2～3 周 | 可复用创作偏好、模板、参考素材和项目复制 |
| 13 | 协作、DAW 交付与产品收口 | 4～5 周 | 本地多用户协作、分享评审、标准交付包、完整体验验收 |

单人顺序开发预计需要 `20～26 周`。建议一次只推进一个 Milestone，不并行维护多套半成品工作流。

## 5. 架构演进原则

### 5.1 保留现有边界

- 保留 FastAPI、SQLAlchemy、Alembic、Arq、PostgreSQL、Redis、MinIO 和 Next.js。
- 保留当前专用版本模型，不在功能扩展前强制重构为通用 `ArtifactVersion`。
- 所有 AI 输出先形成候选或草稿，用户选择后才进入正式资产版本。
- 所有编辑继续创建新版本；前端未保存草稿不直接污染历史。
- 外部模型必须通过 Provider 协议接入，服务层不得依赖单一厂商 SDK 类型。

### 5.2 新 Provider 边界

```python
class TextGenerationProvider(Protocol):
    async def generate_structured(self, request: StructuredPromptRequest) -> StructuredResult: ...

class MusicGenerationProvider(Protocol):
    async def generate_demo(self, request: DemoGenerationRequest) -> GeneratedAudioSet: ...

class AudioAnalysisProvider(Protocol):
    async def analyze(self, request: AudioAnalysisRequest) -> ReferenceAnalysisResult: ...

class AudioToMidiProvider(Protocol):
    async def transcribe(self, request: AudioToMidiRequest) -> StructuredMidiResult: ...

class StemSeparationProvider(Protocol):
    async def separate(self, request: StemSeparationRequest) -> GeneratedStemSet: ...
```

每种 Provider 至少包含：

- `provider_name` 和 `provider_version`。
- 输入参数 schema 和能力声明。
- 超时、错误类别和可重试性。
- 成本/用量元数据，即使当前不做计费。
- 可替换的本地 Fake/Deterministic 实现，保证测试不依赖外网。

### 5.3 新任务类型

- `text_generation`
- `reference_analysis`
- `audio_to_midi`
- `demo_generation`
- `stem_separation`
- `audio_render`
- `project_import`
- `project_export`

所有耗时 Provider 调用进入 Arq；短小的本地编辑转换继续同步执行。

## 6. Milestone 8：真实 AI 创作引擎

### 6.1 目标

把 Idea Intake、歌词、编曲和 Revision Planner 从规则占位实现升级为真实可用的结构化 AI 工作流，同时保留确定性 fallback。

### 6.2 关键功能

- 实现第一个真实 `TextGenerationProvider`。
- Provider 配置只从服务端环境读取，前端不接触密钥。
- 为 SongSpec、歌词、编曲和 Revision 分别建立版本化 Prompt 模板。
- 使用 Pydantic schema 校验结构化输出；解析失败时执行有限修复，不接受任意 JSON。
- 每次生成支持 `1～3` 个候选，用户可以预览、比较和选择。
- 未选择的候选保留来源、Prompt 版本和生成参数，但不进入正式资产时间线。
- 保留 deterministic Provider，可在离线和测试环境运行完整链路。
- 建立固定创作样例集，覆盖中文 Indie Rock、英文 Pop、纯音乐配乐和已有歌词续写。

### 6.3 数据模型

- `provider_profiles`
  - Provider 名称、能力、模型、默认参数、启用状态。
  - 不保存明文 API key。
- `prompt_template_versions`
  - workflow、版本号、模板正文、输出 schema 版本、变更说明。
- `generation_candidates`
  - project、run、asset type、候选内容、评分、选择状态、来源版本。
- `evaluation_runs`
  - 样例集、Provider、Prompt 版本、结构正确率和人工评分。

### 6.4 Public Interfaces

- `GET /api/v1/providers/capabilities`
- `POST /api/v1/projects/{project_id}/candidates/generate`
- `GET /api/v1/projects/{project_id}/candidates`
- `POST /api/v1/projects/{project_id}/candidates/{candidate_id}/select`
- 现有 SongSpec、lyrics、arrangement 和 revision generate 接口增加可选 `provider_profile_id`、`candidate_count`。
- `GenerationRun` 增加 `provider_usage` 和稳定的 `error_code`。

### 6.5 验收标准

- 四类工作流都能通过真实 Provider 返回 schema 合法的候选。
- 用户选择候选前不会创建正式资产版本。
- Provider 不可用时，UI 可以选择重试或使用本地 fallback。
- 固定样例集结构化成功率不低于 `98%`。
- 人工盲评中，真实 Provider 输出在主题一致性和可编辑性上明显优于确定性基线。

## 7. Milestone 9：专业创作编辑器

### 7.1 目标

让用户不依赖 JSON 文本框或外部软件，也能完成核心创作资产的精细修改。

### 7.2 统一段落时间线

- 以 SongSpec 的 song structure 为主时间线。
- 歌词、和弦、MIDI、编曲和 Demo marker 共享稳定 `section_id`。
- 支持段落新增、复制、删除、重排和重命名。
- 结构变化先显示影响范围，再批量创建受影响的新版本。
- 支持局部循环试听和当前播放位置同步。

### 7.3 歌词编辑器

- 段落化富文本编辑，但持久化为受控结构而非任意 HTML。
- Hook 候选、韵脚标记、行数、字数/音节数和重音提示。
- 逐行改写、扩写、压缩、换韵和语气调整。
- 原文/候选并排 diff，一次接受单行、单段或全部修改。
- 支持敏感词、禁用表达和个人词库提示。

### 7.4 和弦编辑器

- 小节网格、每拍和弦位置、转位、延伸音和借用和弦。
- 全曲或选定段落移调。
- 基于 Tone.js 的浏览器内和弦试听、节拍器和循环。
- 和弦合法性由音乐理论工具层校验，不由 UI 字符串解析决定。
- 支持 Nashville Number 和罗马数字显示模式。

实施状态（2026-07-14）：已完成。和弦资产升级为 schema v2 的小节/拍点事件；完成稳定
event ID、music21 理论校验、转位/延伸音/借用和弦分析、全曲/段落移调、罗马与 Nashville
显示、Tone.js 动态试听、节拍器、循环、本地草稿、撤销/重做和不可变版本保存。

### 7.5 MIDI 钢琴卷帘

- 引入 `Tone.js`、`@tonejs/midi` 和稳定 Canvas 渲染层。
- note 新增、移动、缩放、删除、多选、复制和粘贴。
- quantize、transpose、velocity、legato、humanize 和 scale snap。
- melody/hook/chord track 切换与叠加查看。
- 浏览器播放只用于编辑试听；后端继续负责生成标准 MIDI 文件。
- `MidiAssetVersion` 增加结构化 `note_events`、tempo map 和 time signature map，二进制 MIDI 由结构化数据确定性重建。

实施状态（2026-08-01）：已完成。MIDI 资产升级为 schema v2，包含稳定 note ID、段落来源、
tempo/time-signature map 与父版本；完成 Canvas 钢琴卷帘、三轨切换/叠加、音符新增、移动、
缩放、多选、复制粘贴、删除、撤销/重做、本地草稿、Tone.js 试听，以及量化、移调、力度、
连奏、人性化和调式吸附的不可变服务端 transform。旧 schema v1 MIDI 保持可下载，不做不可证明的
结构化回填。

### 7.6 编辑状态

- 浏览器本地保存未提交 draft，刷新后可以恢复。
- Save 继续创建正式新版本。
- 支持 undo/redo，但 undo 不创建服务端版本。
- 离开存在未保存修改的页面前给出明确提示。

### 7.7 Public Interfaces

- `PATCH /api/v1/projects/{project_id}/structure`
- `PATCH /api/v1/projects/{project_id}/midi-assets/{midi_asset_id}`
- `POST /api/v1/projects/{project_id}/midi/transform`
- `POST /api/v1/projects/{project_id}/lyrics/{lyrics_id}/rewrite`
- `POST /api/v1/projects/{project_id}/chords/{chord_id}/transpose`

### 7.8 验收标准

- 用户可以只使用浏览器完成一首歌的结构、歌词、和弦和旋律修改。
- 钢琴卷帘保存后的 MIDI 可由 `mido`、Ableton 和 Logic 导入。
- 编辑过程无明显布局跳动，桌面和移动端不存在不可达控件。
- 结构变化不会产生悬空 section reference。
- undo/redo、本地 draft、版本保存和 restore 语义清晰且互不冲突。

## 8. Milestone 10：音频理解与参考分析

### 8.1 目标

支持用户以常见音频文件、参考曲和哼唱作为正式创作入口，并把分析结果转化为可确认的结构化约束。

### 8.2 音频导入

- 通过 ffmpeg 支持 WAV、MP3、M4A、FLAC 和 OGG。
- 原文件保留，分析前创建标准 PCM WAV 派生文件。
- 波形支持缩放、选区、裁剪预览和 marker。
- 用户可以标记“只分析 00:20～01:00”，降低处理时间。

### 8.3 分析能力

- tempo、beat grid、time signature 候选。
- key/mode、音高范围和响度曲线。
- intro/verse/chorus/bridge 等结构候选。
- chord progression 候选和置信度。
- 乐器与密度标签、能量曲线和参考制作特征。
- 使用 Basic Pitch 或兼容 Provider 提取单旋律 MIDI。
- 哼唱 MIDI 支持休止、连音、力度估计、调内吸附和手工纠正。

分析结果只能作为用户可编辑候选，不自动覆盖 SongSpec 或当前资产。

### 8.4 数据模型

- `audio_derivatives`
  - source upload、类型、storage key、格式、采样率、声道和时长。
- `reference_analysis_versions`
  - tempo/key/structure/chords/energy/instrument tags、置信度、Provider 来源。
- `audio_markers`
  - upload、时间、label、section link、用户备注。
- `midi_asset_versions` 保留 `source_audio_upload_id`，增加 analysis version 来源。

### 8.5 Public Interfaces

- `POST /api/v1/projects/{project_id}/audio-uploads/{audio_id}/analyze`
- `GET /api/v1/projects/{project_id}/audio-uploads/{audio_id}/analyses`
- `POST /api/v1/projects/{project_id}/reference-analyses/{analysis_id}/apply`
- `POST /api/v1/projects/{project_id}/audio-uploads/{audio_id}/markers`
- `PATCH /api/v1/projects/{project_id}/audio-markers/{marker_id}`
- `GET /api/v1/projects/{project_id}/audio-uploads/{audio_id}/waveform?resolution=...`

### 8.6 验收标准

- 五种格式都可导入、试听、显示波形并进入分析任务。
- 测试音频的 BPM 和 key 在定义容差内稳定输出。
- Basic Pitch Provider 输出的 MIDI 可在钢琴卷帘继续编辑。
- 用户可选择性应用分析字段，不会一次覆盖整份 SongSpec。
- 原始音频、派生音频、分析和 MIDI 之间来源关系可追溯。

## 9. Milestone 11：真实 Demo、Stem 与局部重渲染

### 9.1 目标

把当前占位 WAV 升级为真实方向试听能力，并让 Demo 修改继续受结构化资产控制。

### 9.2 真实 Music Provider

- 接入第一个真实 `MusicGenerationProvider`，但保持厂商无关协议。
- 请求由 approved SongSpec、当前歌词、和弦、MIDI、编曲和参考分析共同构建。
- 记录 Provider request id、模型版本、seed、参数、Prompt 和来源 manifest。
- 支持 Provider 异步状态同步、失败重试和用户取消。
- 同一次请求支持多个 variant，用户选择后再设为当前 Demo。

### 9.3 Demo Studio

- A/B 双播放器升级为同步播放、统一 seek 和响度匹配。
- 波形 marker 与 song section 联动。
- 用户可对时间范围或段落提交反馈。
- Revision Planner 将反馈映射到歌词、旋律、和弦、编曲、mix 或重新渲染任务。
- 只影响局部资产的反馈优先创建局部新版本；Provider 不支持局部生成时明确提示将重渲染整曲。

### 9.4 Stem 与本地渲染

- Provider 原生返回 Stem 时保存 vocals、drums、bass、music/other。
- Provider 不返回 Stem 时可选调用 `StemSeparationProvider`。
- 支持 Stem mute/solo、基础音量和平衡试听。
- 使用 ffmpeg 生成预览混音，不在本阶段建设完整 DAW 混音器。

### 9.5 数据模型

- `demo_generation_variants`
- `stem_asset_versions`
- `demo_feedback_regions`
- `audio_render_versions`
- `audio_demo_versions` 增加 active variant、loudness 和 source render manifest。

### 9.6 Public Interfaces

- `POST /api/v1/projects/{project_id}/demo-requests`
- `GET /api/v1/projects/{project_id}/demo-requests/{request_id}`
- `POST /api/v1/projects/{project_id}/demo-variants/{variant_id}/select`
- `POST /api/v1/projects/{project_id}/demos/{demo_id}/feedback-regions`
- `POST /api/v1/projects/{project_id}/demos/{demo_id}/separate-stems`
- `GET /api/v1/projects/{project_id}/stems`
- `POST /api/v1/projects/{project_id}/audio-renders`

### 9.7 验收标准

- 真实 Provider 可以从当前资产链生成至少两个可试听 variant。
- 每个 Demo 可完整追溯到输入资产、Prompt、模型和参数。
- A/B 同步播放、seek 和响度匹配可正常工作。
- 时间范围反馈可以进入 Revision 预览并形成明确影响范围。
- Stem 可独立试听和导出，生成失败不会污染当前 Demo。

## 10. Milestone 12：风格记忆、模板与素材库

### 10.1 目标

让用户不必在每个项目重复输入创作偏好，并能够复用成功项目的结构和制作决策。

### 10.2 功能范围

- Style Profile：常用流派、语言、BPM、调式、情绪、乐器和制作偏好。
- Lyrics Profile：常用意象、词汇、叙事视角、禁用表达和押韵偏好。
- Instrument Preset：段落乐器层、能量和 mix notes 模板。
- Song Template：SongSpec、结构、默认生成步骤和导出设置。
- Reference Library：上传素材、分析摘要、标签、收藏和项目引用。
- Project duplicate：复制结构和设置，可选择是否复制资产。
- 从已批准资产显式“保存为模板/风格”，不静默学习全部项目内容。
- 项目列表支持 tag、favorite、最近编辑和全文搜索。

### 10.3 数据模型

- `style_profiles`
- `lyric_profiles`
- `instrument_presets`
- `song_templates`
- `reference_library_items`
- `project_tags`
- `project_template_links`

### 10.4 Public Interfaces

- `/api/v1/style-profiles`
- `/api/v1/lyric-profiles`
- `/api/v1/instrument-presets`
- `/api/v1/song-templates`
- `/api/v1/reference-library`
- `POST /api/v1/projects/{project_id}/duplicate`
- `POST /api/v1/projects/{project_id}/save-as-template`

### 10.5 验收标准

- 用户可以基于模板在一分钟内建立结构完整的新项目。
- Style/Lyrics Profile 可以应用、覆盖和移除，并记录到 SongSpec 来源。
- 相同 profile 在不同项目中保持稳定约束，但不会覆盖项目明确输入。
- 参考素材只存一份，可被多个项目引用且来源清晰。
- 搜索和标签可以在项目和参考素材数量增长后保持可用。

## 11. Milestone 13：协作、DAW 交付与产品收口

### 11.1 本地账号与项目协作

- 本地注册、登录、退出和密码修改。
- Project owner、editor、reviewer 三种角色。
- 项目邀请、成员列表和移除成员。
- 评论支持 thread、回复、mention、resolve/reopen 和 asset/section/time range target。
- Activity 显示操作者，关键变更可从事件进入对应版本。
- 只读 Review Snapshot 固定资产版本，后续编辑不改变已分享快照。
- 不实现企业 SSO、公开注册风控或公网安全承诺。

### 11.2 DAW 友好交付

导出包至少包含：

```text
project.zip
├── manifest.json
├── project-snapshot.json
├── song-spec.json
├── lyrics.md / lyrics.txt / lyrics.json
├── chord-sheet.md
├── lead-sheet.musicxml
├── midi/
│   ├── full-song-type-1.mid
│   ├── melody.mid
│   ├── hook.mid
│   ├── chords.mid
│   └── tempo-map.mid
├── audio/
│   ├── selected-demo.wav
│   ├── reference-preview.wav
│   └── stems/*.wav
├── markers.csv
├── arrangement.md / arrangement.json
├── comments.md
└── revision-history.json
```

- MIDI Type 1 包含 tempo、time signature、track name、section marker 和 key metadata。
- MusicXML 提供旋律、和弦和歌词的 lead sheet 交换格式。
- markers.csv 可用于常见 DAW 手工或脚本导入。
- 支持完整项目 archive 导出与重新导入，保留版本和来源关系。
- 导出前执行 preflight，列出缺失项、格式警告和预计大小。

### 11.3 产品体验收口

- 首次使用 onboarding：新建、从模板开始、导入音频三条入口。
- 工作台统一导航和当前 section/playhead 状态。
- 全局命令面板、键盘操作、tooltip 和可访问焦点。
- 项目 trash、恢复和永久删除。
- 未保存草稿恢复、任务历史、错误恢复入口和离线 fallback 提示。
- 桌面优先，同时保证移动端可完成查看、评论、试听和审批。
- English/中文覆盖所有新增界面和系统生成状态。

### 11.4 Public Interfaces

- `/api/v1/auth/register|login|logout|me`
- `/api/v1/projects/{project_id}/members`
- `/api/v1/projects/{project_id}/invitations`
- `/api/v1/projects/{project_id}/comment-threads`
- `/api/v1/projects/{project_id}/review-snapshots`
- `POST /api/v1/projects/{project_id}/exports/preflight`
- `POST /api/v1/projects/{project_id}/archives`
- `POST /api/v1/project-imports`
- `DELETE /api/v1/projects/{project_id}` 与 trash/restore 语义。

### 11.5 验收标准

- owner、editor、reviewer 在本地多用户场景中权限行为正确。
- Review Snapshot 在原项目继续修改后仍保持内容不变。
- 导出包可在至少两种 DAW 中导入 MIDI、Stem 和 marker 信息。
- 项目 archive 在空数据库中重新导入后，版本树和主要文件一致。
- 新用户不阅读开发文档也能完成“创建 → 生成 → 编辑 → Demo → 导出”。
- 桌面、平板和移动端的目标流程没有文本溢出或关键控件不可达。

## 12. 数据迁移与兼容策略

- 所有迁移 additive，现有 Milestone 0～7 数据无需清空。
- 新增结构化 MIDI 字段时，为旧 MIDI 提供一次性解析回填任务；解析失败保留二进制资产并标记只读。
- Audio derivative 和 analysis 不改变原始 `audio_uploads` 对象。
- 真实 Provider 生成的新 Demo 与现有 local deterministic Demo 共用版本列表，通过 provider 字段区分。
- 引入用户后，为现有项目创建默认 local owner，并保持现有 URL 可访问。
- 每个新 schema 增加 `schema_version`，导入旧 archive 时执行显式升级。

## 13. 测试与质量计划

### 13.1 Provider Contract Tests

- 每个真实和 Fake Provider 运行同一套 contract tests。
- 覆盖 timeout、rate limit、invalid response、partial result、cancel 和 retry。
- 测试日志不得包含密钥、完整 Prompt 或上传音频内容。

### 13.2 Agent Evaluation

- 固定至少 30 个创作样例，包含中英文、不同流派、纯音乐和输入不完整场景。
- 指标包括 schema 合法率、约束遵循率、段落完整率、重复度和人工可编辑性评分。
- Prompt 或模型升级必须与当前基线对比，不能只验证“接口成功”。

### 13.3 音乐与编辑器测试

- MIDI transform 使用属性测试验证音高、时值、范围和 round-trip。
- MusicXML、MIDI 和 ZIP 使用真实解析器重新读取。
- 音频 fixture 覆盖格式转换、tempo/key、marker、Basic Pitch 和 Stem。
- 编辑器覆盖选区、拖拽、undo/redo、draft restore、save version 和冲突恢复。
- 浏览器音频测试覆盖 AudioContext suspend/resume 和设备不支持场景。

### 13.4 集成与 E2E

- 保留当前 deterministic 完整链路作为每次 CI 的稳定基线。
- 真实 Provider smoke 通过显式环境开关运行，不作为离线测试前提。
- 每个 Milestone 至少增加一条桌面 E2E 和一条移动端查看/审批路径。
- Product v1 最终 E2E 覆盖四种入口：idea、template、reference audio、humming。
- 最终验收使用三个完整项目场景：中文 Indie Rock、英文 Pop、无歌词游戏配乐。

## 14. 推荐技术增量

### 后端与音频

- `ffmpeg`：统一音频解码、预览转码和 Stem 混合。
- `basic-pitch`：真实单旋律转 MIDI Provider。
- `librosa`：tempo、beat、key 特征与基础结构分析。
- `music21`：和弦、调式、MusicXML 和理论校验。
- `pretty_midi`：结构化 MIDI 与标准文件转换。

这些依赖应隔离在音频/音乐 Worker profile，避免普通 API 启动必须加载大型模型。

### 前端

- `Tone.js`：浏览器试听、节拍器、loop 和 transport。
- `@tonejs/midi`：MIDI 解析与浏览器播放数据。
- `wavesurfer.js`：缩放波形、region 和 marker。
- Canvas/WebGL 渲染层：钢琴卷帘和长时间线；避免为每个 note 创建大量 DOM 节点。

引入前必须用最小原型验证 Next.js、移动端和浏览器 AudioContext 兼容性。

## 15. 实施顺序与依赖

```text
Milestone 8 真实 AI
       │
       ├──────────────┐
       ▼              ▼
Milestone 9 编辑器   Milestone 10 音频理解
       │              │
       └──────┬───────┘
              ▼
      Milestone 11 真实 Demo/Stem
              │
              ▼
      Milestone 12 风格与模板
              │
              ▼
      Milestone 13 协作与交付
```

- Milestone 9 必须先建立结构化 MIDI，Milestone 11 才能可靠执行旋律局部修改。
- Milestone 10 的 reference analysis 是 Milestone 11 Demo prompt 和风格约束的重要输入。
- Milestone 12 应基于已验证的真实 AI 与编辑器数据设计，避免提前固化错误偏好模型。
- 账号与成员可以在 Milestone 13 集中实现，前面继续使用默认 local user。

## 16. 主要风险与控制

| 风险 | 影响 | 控制方式 |
|---|---|---|
| 真实模型输出不稳定 | 产品体验不可预测 | 候选机制、schema 校验、evaluation、deterministic fallback |
| Provider 成本或条款变化 | 功能不可持续 | 厂商无关协议、用量记录、至少一个替代 Provider |
| 编辑器范围过大 | 长期停留在半成品 | 先完成统一时间线和 melody 单轨，再扩展高级操作 |
| Basic Pitch/分析误差 | 用户错误信任结果 | 显示置信度、候选确认、保留原音频与手工修正 |
| Stem 质量不足 | 无法作为 DAW 素材 | 明确原生 Stem 与分离 Stem 来源，导出时标记质量 |
| 参考曲造成模仿风险 | 版权和产品定位问题 | 只提取结构化特征，不生成“仿某艺人”指令 |
| 版本数量快速增长 | 工作台难以理解 | 版本命名、标签、分支来源、当前版本和 archive 策略 |
| 多用户引入权限回归 | 项目数据误操作 | 服务层统一 ownership/role 检查，跨项目测试矩阵 |

## 17. Product v1 最终验收清单

### 创作入口

- [ ] 用户可以从灵感、模板、参考音频和哼唱开始项目。
- [ ] 真实 AI 可以生成并比较多个 SongSpec、歌词或编曲候选。
- [ ] 用户可以显式选择 Provider 或使用本地 fallback。

### 编辑能力

- [x] 歌词支持逐行/逐段编辑和 AI 候选接受。
- [x] 和弦支持小节网格、试听、转位和移调。
- [x] MIDI 支持钢琴卷帘编辑、量化、移调、力度和循环播放。
- [x] song structure 修改可以安全传播到关联资产。

### 音频与 Demo

- [ ] WAV、MP3、M4A、FLAC、OGG 可导入和分析。
- [ ] 参考分析结果可选择性应用到 SongSpec。
- [ ] 哼唱可通过真实 Provider 提取并修正 melody MIDI。
- [ ] 真实音乐 Provider 可生成多个 Demo variant。
- [ ] Demo 支持同步 A/B、region feedback、Stem 和重新渲染。

### 复用与协作

- [ ] Style Profile、歌词偏好、模板和参考库可跨项目复用。
- [ ] 本地 owner/editor/reviewer 权限和评论 thread 完整可用。
- [ ] 固定 Review Snapshot 可分享评审且不会随项目修改漂移。

### 交付

- [ ] 导出包含标准 MIDI、MusicXML、Stem、marker、歌词和完整 manifest。
- [ ] 项目 archive 可以导出后重新导入并保留版本关系。
- [ ] 至少两种 DAW 验证 MIDI、Stem 和 marker 可继续使用。

### 体验与质量

- [ ] English/中文覆盖全部新增产品界面。
- [ ] 三个最终样例项目从入口到导出无阻断完成。
- [ ] deterministic CI、Provider contract、音频 fixture 和浏览器 E2E 全部通过。
- [ ] 新用户可以在不阅读开发文档的情况下完成第一首项目。

## 18. 完成后的产品边界

完成 Milestone 8～13 后，Abachiwave 应成为一个功能完整的本地优先音乐创作产品：它能够理解用户输入、提供真实 AI 候选、支持专业级草稿编辑、分析音频、生成和比较 Demo、复用个人风格、完成协作评审，并输出可进入 DAW 的标准素材。

此时再单独评估生产化工作，包括公网认证强化、部署、高可用、监控、成本、计费和合规；这些工作不应反向阻塞 Product v1 的功能开发。
