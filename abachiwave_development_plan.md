# Abachiwave 首轮开发计划大纲

> **项目定位**：面向音乐创作者的 AI 协作创作工作台。系统通过 Agent 将用户的灵感、歌词、哼唱、参考方向等输入，逐步转化为可编辑的歌曲创作资产：创作简报、歌词、和弦、旋律 MIDI、编曲方案、Demo、版本记录与导出包。
>
> **首轮目标**：跑通“灵感 → 创作简报 → 歌词 → 和弦/旋律 MIDI → 编曲建议 → Demo → 修改 → 导出”的最小闭环，而不是追求一次性生成可发行成品。

---

## 1. 产品目标与边界

### 1.1 首轮要解决的问题

- 用户有模糊灵感，但难以快速拆解为可制作的歌曲方案。
- 用户可以写歌词或哼旋律，但缺少和弦、段落、编曲与制作方向。
- 现有 AI 音乐生成工具多为黑盒输出，用户难以局部修改、保留版本或进入 DAW 继续制作。
- 创作过程需要反复迭代，单轮聊天记录无法稳定保存创作决策与资产关系。

### 1.2 首轮目标用户

- 独立音乐人、唱作人、编曲初学者。
- 面向短视频、独立游戏、播客、影视内容制作配乐的人群。
- 有创作想法、但需要歌词、和弦、旋律草稿或编曲方向辅助的用户。

### 1.3 MVP 成功标准

用户能够在一个项目内完成：

```text
灵感输入
→ 生成并确认创作简报
→ 生成/编辑歌词
→ 生成和弦与旋律 MIDI 草稿
→ 获得段落化编曲建议
→ 生成可试听 Demo
→ 用自然语言提出局部修改
→ 导出 MIDI、歌词、方案与音频资产
```

### 1.4 首轮明确不做

- 歌手音色克隆或模仿特定艺人。
- 自动完成专业混音、母带和可直接发行成品。
- 复杂 DAW 原生工程文件生成。
- 自动版权判定、侵权保证或发行分发。
- 低延迟实时伴奏、实时声线转换。
- 直接依赖单一第三方音乐生成模型的业务实现。

---

## 2. 核心用户流程

### 2.1 新建歌曲项目

用户输入自然语言创作需求，例如：

```text
我想写一首关于深夜骑车回家的歌。
情绪是孤独但不绝望，偏日系 Indie Rock。
副歌要有明显上扬感，主歌克制一些。
```

系统创建 `Project`，并进入需求澄清流程。

### 2.2 创作需求澄清

Agent 通过结构化提问补齐创作信息：

- 主题、叙事视角、情绪变化。
- 语言与歌词风格。
- 流派、参考氛围、乐器偏好。
- BPM、调式、拍号、目标时长。
- 段落结构与副歌爆发程度。
- 是否已有歌词、哼唱、MIDI、参考曲或音频草稿。

确认后生成 `SongSpec`。

### 2.3 创作资产生成

基于 `SongSpec`，按步骤生成：

1. 创作简报与歌曲结构。
2. 歌词草稿与 Hook 候选。
3. 和弦进行。
4. 主旋律、Hook、根音等 MIDI 草稿。
5. 编曲与能量曲线建议。
6. Demo 生成请求与试听音频。

### 2.4 反馈与局部修改

用户以自然语言反馈，例如：

```text
副歌太平，旋律再抬高一点；
前奏更空一些，桥段把鼓抽掉；
人声不要那么靠前。
```

系统识别：

- 修改目标段落。
- 修改类型。
- 受影响资产。
- 是否需要重新生成 Demo。

系统只更新相关资产，并保留历史版本。

### 2.5 导出

导出一个歌曲项目包：

```text
project.zip
├── song_spec.json
├── creative_brief.md
├── lyrics.md
├── chords.mid
├── melody.mid
├── hook.mid
├── arrangement_plan.md
├── demo.wav / demo.mp3
└── revision_history.json
```

---

## 3. 首轮功能范围

### 3.1 P0：必须完成

| 模块 | 功能 | 说明 |
|---|---|---|
| 项目管理 | 新建、查看、重命名、归档项目 | 一个项目对应一首歌曲或一个创作方向 |
| 创作需求 Agent | 灵感解析、追问、生成 SongSpec | 作为所有后续流程的结构化输入 |
| 创作简报 | 主题、风格、情绪曲线、段落结构 | 用户确认后锁定版本 |
| 歌词 Agent | 生成、改写、段落重写、Hook 候选 | 以结构化段落方式保存 |
| 和弦生成 | 段落级和弦进行 | 支持调式、BPM、风格约束 |
| MIDI 生成 | 主旋律/Hook/根音 MIDI 草稿 | 必须可下载、可继续编辑 |
| 编曲规划 | 乐器层、能量曲线、段落制作建议 | 生成可读的制作说明 |
| 版本管理 | 每次资产变更生成版本 | 支持回看与恢复 |
| 导出 | 打包歌词、MIDI、方案、元数据 | 首轮重点交付能力 |

### 3.2 P1：首轮后半段完成

| 模块 | 功能 | 说明 |
|---|---|---|
| Demo 生成 | 接入可替换的音频生成 Provider | 目标是方向试听，不承诺发行品质 |
| 修改 Agent | 从自然语言提取局部修改任务 | 只更新受影响资产 |
| 音频上传 | 上传哼唱、旋律草稿、参考片段 | 为后续音频分析预留 |
| 音频转 MIDI | 单旋律/单乐器转 MIDI | 作为草稿提取能力，不定位为精确扒谱 |
| 音频播放 | Demo 试听、版本切换、波形显示 | 支持项目内比对 |

### 3.3 P2：后续扩展

- 多人协作与评论。
- 用户个人创作风格记忆。
- 自动参考曲结构分析。
- 多轨分离、音色与编配建议。
- DAW 插件或 Ableton/Logic 工作流集成。
- 可配置的专业制作模板。
- 创作评审与质量评价体系。

---

## 4. 系统架构

### 4.1 架构原则

1. **Agent 负责创作决策，工具负责确定性执行。**
2. **所有创作信息结构化保存，不依赖纯聊天上下文。**
3. **音频生成模型必须通过 Provider Adapter 隔离。**
4. **耗时任务异步执行，前端可查看任务状态和中间结果。**
5. **每个资产天然版本化，任何修改可追溯。**

### 4.2 技术栈建议

```text
Backend
- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- PostgreSQL

Agent Orchestration
- LangGraph
- LangSmith 或自建 Trace / Evaluation

Async Jobs
- Redis
- Celery / Dramatiq / Arq（三选一）
- 独立 GPU Worker

Storage
- S3 / MinIO
- PostgreSQL 存业务元数据与版本关系
- 对象存储保存 MIDI、WAV、MP3、导出包

Music Processing
- pretty_midi
- mido
- music21
- librosa
- ffmpeg
- Basic Pitch（音频转 MIDI 适配器）

Frontend
- Next.js / React
- TypeScript
- 音频播放器与波形组件
- MIDI / Piano Roll 预览组件
```

### 4.3 服务拆分

```text
Frontend Web App
        │
        ▼
FastAPI API Gateway
        │
        ├── Project Service
        ├── Asset & Version Service
        ├── Agent Orchestrator (LangGraph)
        ├── Export Service
        └── Task Dispatcher
                │
                ▼
        Queue / Redis
                │
                ├── CPU Worker: MIDI、文档、打包、音频处理
                └── GPU Worker: 音乐生成、音频分析

PostgreSQL  ←→  Object Storage (S3 / MinIO)
```

---

## 5. Agent 工作流设计

### 5.1 核心状态对象

`SongState` 应包含而不限于：

```python
class SongState(TypedDict):
    project_id: str
    active_song_spec_id: str | None
    active_lyrics_version_id: str | None
    active_chord_version_id: str | None
    active_melody_version_id: str | None
    active_arrangement_version_id: str | None
    active_demo_version_id: str | None
    user_feedback: list[str]
    pending_tasks: list[str]
    approval_status: str
    revision_plan: dict | None
```

### 5.2 主流程图

```text
START
  ↓
Idea Intake
  ↓
Requirement Clarifier
  ↓
SongSpec Builder
  ↓
Human Approval
  ├── revise brief ──────────────┐
  └── approve                    │
          ↓                      │
      Lyrics Generator           │
          ↓                      │
      Harmony Generator          │
          ↓                      │
      Melody/MIDI Generator      │
          ↓                      │
      Arrangement Planner        │
          ↓                      │
      Demo Generation            │
          ↓                      │
      Critic / Revision Planner ─┘
          ↓
      Export Project
          ↓
END
```

### 5.3 主要 Agent 职责

| Agent | 输入 | 输出 | 是否需要人工确认 |
|---|---|---|---|
| Requirement Clarifier | 用户灵感与补充信息 | 澄清问题、创作方向 | 是 |
| SongSpec Builder | 对话与确认内容 | 结构化 SongSpec | 是 |
| Lyrics Agent | SongSpec、歌词反馈 | 歌词版本、Hook 候选 | 建议 |
| Harmony Agent | SongSpec、歌词节奏信息 | 和弦进行、段落调性信息 | 建议 |
| Melody Agent | SongSpec、歌词、和弦 | 旋律/Hook MIDI | 建议 |
| Arrangement Agent | 前述全部资产 | 编曲计划、能量曲线 | 否 |
| Demo Prompt Agent | SongSpec、编曲方案、歌词 | 音乐生成模型 Prompt | 否 |
| Revision Planner | 用户反馈、当前资产 | 局部修改任务列表 | 是 |
| Quality Critic | 成品资产与规则 | 质量问题与修改建议 | 否 |

---

## 6. 数据模型设计

### 6.1 核心实体

```text
User
Project
SongSpec
CreativeBrief
LyricsVersion
ChordProgressionVersion
MidiAssetVersion
ArrangementPlanVersion
AudioDemoVersion
RevisionRequest
GenerationRun
ArtifactVersion
ExportBundle
```

### 6.2 项目关系

```text
Project
├── SongSpec v1..n
├── Lyrics v1..n
├── Chords v1..n
├── Melody MIDI v1..n
├── Arrangement v1..n
├── Demo v1..n
├── Revision Request v1..n
└── Export Bundle v1..n
```

### 6.3 关键字段建议

#### SongSpec

```json
{
  "theme": "深夜骑车回家的孤独感",
  "genre": ["indie rock", "j-pop influenced"],
  "language": "zh-CN",
  "tempo_bpm": 128,
  "key": "E major",
  "time_signature": "4/4",
  "target_duration_seconds": 210,
  "mood_curve": {
    "verse": "restrained and lonely",
    "chorus": "lifting and hopeful"
  },
  "song_structure": [
    "intro",
    "verse_1",
    "pre_chorus",
    "chorus",
    "verse_2",
    "chorus",
    "bridge",
    "final_chorus",
    "outro"
  ]
}
```

#### ArtifactVersion

```json
{
  "id": "uuid",
  "project_id": "uuid",
  "artifact_type": "lyrics | chords | midi | arrangement | demo",
  "version_number": 3,
  "parent_version_id": "uuid | null",
  "source_revision_request_id": "uuid | null",
  "storage_uri": "s3://...",
  "metadata": {},
  "created_at": "ISO-8601"
}
```

---

## 7. API 设计大纲

### 7.1 项目接口

```text
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

### 7.2 创作流程接口

```text
POST /api/v1/projects/{project_id}/intake
POST /api/v1/projects/{project_id}/song-spec/generate
POST /api/v1/projects/{project_id}/song-spec/approve
POST /api/v1/projects/{project_id}/lyrics/generate
POST /api/v1/projects/{project_id}/chords/generate
POST /api/v1/projects/{project_id}/melody/generate
POST /api/v1/projects/{project_id}/arrangement/generate
POST /api/v1/projects/{project_id}/demo/generate
POST /api/v1/projects/{project_id}/revisions
```

### 7.3 资产与导出接口

```text
GET  /api/v1/projects/{project_id}/assets
GET  /api/v1/projects/{project_id}/assets/{asset_id}
POST /api/v1/projects/{project_id}/assets/{asset_id}/restore
POST /api/v1/projects/{project_id}/exports
GET  /api/v1/exports/{export_id}
```

### 7.4 异步任务接口

```text
GET /api/v1/tasks/{task_id}
GET /api/v1/projects/{project_id}/runs
```

---

## 8. 核心工具层设计

### 8.1 MIDI 工具

应提供以下确定性能力：

- 创建 MIDI 文件。
- 写入 tempo、key、time signature。
- 写入旋律、和弦、bass root、drum pattern。
- 量化、移调、裁剪、拼接。
- 导出标准 `.mid` 文件。

建议接口：

```python
class MidiService:
    def build_chord_midi(self, progression: ChordProgression) -> MidiArtifact: ...
    def build_melody_midi(self, notes: list[MelodyNote]) -> MidiArtifact: ...
    def transpose(self, midi_uri: str, semitones: int) -> MidiArtifact: ...
    def quantize(self, midi_uri: str, grid: str) -> MidiArtifact: ...
```

### 8.2 音频工具

- 音频格式转换。
- 时长裁剪与拼接。
- 波形与响度基础分析。
- 文件元数据读取。
- 音频转 MIDI 适配器。
- Demo 生成模型适配器。

建议接口：

```python
class MusicGenerationProvider(Protocol):
    def generate_demo(self, request: DemoGenerationRequest) -> GeneratedAudio: ...
    def continue_song(self, request: ContinueSongRequest) -> GeneratedAudio: ...
    def repaint_section(self, request: RepaintRequest) -> GeneratedAudio: ...
```

---

## 9. 前端页面规划

### 9.1 页面清单

| 页面 | 核心内容 |
|---|---|
| 项目列表页 | 最近项目、状态、最近版本、创建项目 |
| 新建项目页 | 灵感输入、参考信息、上传草稿 |
| 项目工作台 | 歌曲结构、聊天/反馈区、资产面板、生成进度 |
| SongSpec 编辑页 | 主题、风格、BPM、调式、段落结构、确认按钮 |
| 歌词编辑页 | 段落编辑、版本切换、重写指令、Hook 候选 |
| MIDI 页面 | Piano Roll 预览、下载、版本对比 |
| 编曲页面 | 段落乐器层、能量曲线、生成建议 |
| Demo 页面 | 音频播放器、波形、版本试听、局部反馈 |
| 导出页面 | 选择资产、生成 ZIP、下载记录 |

### 9.2 项目工作台布局建议

```text
┌───────────────────────────────────────────────────────┐
│ 项目名称 / 当前版本 / 导出 / 设置                      │
├───────────────┬──────────────────────┬────────────────┤
│ 项目资产树    │ 中央创作编辑区        │ Agent 对话区   │
│ - SongSpec    │ - 歌词 / MIDI / Demo  │ - 澄清问题     │
│ - Lyrics      │ - 段落结构            │ - 修改反馈     │
│ - Chords      │ - 波形 / Piano Roll   │ - 任务进度     │
│ - Melody      │                      │                │
│ - Arrangement │                      │                │
│ - Demo        │                      │                │
└───────────────┴──────────────────────┴────────────────┘
```

---

## 10. 开发里程碑

> 以下以 1 名主开发者、可复用现有 Agent 工程能力为假设。实际工期会受到前端复杂度、模型部署条件、GPU 资源和测试深度影响。

### Milestone 0：项目基础设施（第 1 周）

**目标**：建立可开发、可测试、可部署的工程底座。

- 初始化 FastAPI、PostgreSQL、Redis、对象存储。
- 配置 Docker Compose 本地开发环境。
- 建立数据库迁移、配置管理、日志与错误规范。
- 初始化 LangGraph 工作流框架。
- 建立基础 CI：lint、type check、unit test。
- 建立前端项目和基础登录/项目列表骨架。

**验收标准**：

- 本地一键启动 API、数据库、队列和对象存储。
- 能创建项目并持久化到数据库。
- CI 在 Pull Request 中自动运行。

### Milestone 1：创作简报与 SongSpec（第 2 周）

**目标**：让系统稳定理解用户创作需求。

- 实现 Idea Intake API 与 Agent。
- 实现澄清问题与回答存储。
- 生成结构化 SongSpec。
- 实现 SongSpec 编辑与确认。
- 加入基础 Prompt 模板与 JSON Schema 校验。

**验收标准**：

- 用户可从自由文本创建 SongSpec。
- 生成结果可人工编辑、保存和版本化。
- 不完整需求会触发澄清，而不是随机补全关键参数。

### Milestone 2：歌词、和弦与 MIDI（第 3～4 周）

**目标**：跑通首个可编辑音乐资产链。

- 歌词 Agent：生成、段落重写、Hook 候选。
- 和弦 Agent：生成段落级和弦进行。
- MIDI Service：生成和弦 MIDI、旋律 MIDI、Hook MIDI。
- MIDI 文件上传、下载与版本保存。
- 前端歌词编辑与 MIDI 文件资产展示。

**验收标准**：

- 每个项目至少可生成 1 个歌词版本、1 个和弦版本、1 个旋律 MIDI 版本。
- 生成的 MIDI 可被常见 DAW 导入。
- 用户修改歌词或和弦后，不会覆盖旧版本。

### Milestone 3：编曲方案与导出包（第 5 周）

**目标**：把创作资产组织成可交付项目包。

- 编曲 Agent：按段落生成乐器层与能量曲线建议。
- 导出服务：生成 Markdown、JSON、MIDI、ZIP。
- 项目资产树、版本时间线。
- 基础项目分享/下载权限控制。

**验收标准**：

- 用户可导出完整项目 ZIP。
- 导出包包含所有当前激活版本资产与版本信息。
- 生成过程可重试，不产生脏数据。

### Milestone 4：Demo 生成与任务队列（第 6～7 周）

**目标**：形成可试听闭环。

- 实现 `MusicGenerationProvider` 抽象。
- 接入第一个 Demo 生成适配器。
- 配置 GPU Worker 与长任务状态追踪。
- 前端 Demo 播放、任务进度、失败重试。
- 保存生成参数与模型版本。

**验收标准**：

- 用户可从当前 SongSpec 生成 Demo。
- 生成任务失败可明确定位并支持重试。
- Demo 与生成它的歌词、编曲、Prompt、模型参数可追溯。

### Milestone 5：修改闭环与可用性打磨（第 8 周）

**目标**：让系统真正具备“协作创作”体验。

- Revision Planner：解析自然语言修改要求。
- 局部资产更新与影响范围识别。
- 版本对比、恢复和 Demo 对比试听。
- 错误提示、空状态、任务取消与基础埋点。
- 完成 MVP 试用测试与问题修复。

**验收标准**：

- 用户可提出至少三类局部修改：歌词、旋律、编曲。
- 系统能够解释将修改哪些资产，并在执行前允许确认。
- 可回退到任意已保存资产版本。

---

## 11. 质量与测试策略

### 11.1 单元测试

重点覆盖：

- SongSpec Schema 校验。
- Prompt 输入/输出解析。
- MIDI 文件生成、量化、移调。
- 版本关系和恢复逻辑。
- 导出 ZIP 文件完整性。
- 任务状态机转换。

### 11.2 集成测试

- 从项目创建到导出的完整流程。
- Agent 节点失败、超时、重试后的状态一致性。
- 对象存储失败、队列失败、模型 Provider 失败。
- 资产版本与数据库记录的一致性。

### 11.3 Agent Evaluation

建立一组固定创作需求样本，检查：

- 是否正确提问而非擅自假设。
- SongSpec 是否完整且满足 JSON Schema。
- 歌词是否匹配主题、语言、段落结构。
- 和弦与旋律是否符合指定调式/BPM/拍号。
- 修改请求是否准确映射到受影响资产。

### 11.4 人工体验测试

至少测试以下典型路径：

1. 从一句灵感开始创作。
2. 先上传歌词，再补全旋律与编曲。
3. 先上传哼唱，再转 MIDI。
4. 多轮反复修改副歌。
5. 导出后导入任意 DAW 验证 MIDI 可用性。

---

## 12. 风险与应对

| 风险 | 影响 | 应对策略 |
|---|---|---|
| 底层音乐生成模型质量不稳定 | Demo 不可用或体验波动 | Provider 抽象、保留无 Demo 的创作资产闭环 |
| GPU 生成耗时过长 | 用户等待和成本上升 | 异步任务、队列、优先级、取消、缓存与限流 |
| 语言模型输出结构不稳定 | SongSpec 或资产数据损坏 | Pydantic Schema、重试、repair prompt、人工确认 |
| MIDI 旋律质量不足 | 用户不愿继续使用 | 定位为草稿、支持版本再生成与用户导出编辑 |
| 版权/模仿风险 | 产品与合规风险 | 禁止特定艺人模仿、记录来源、增加用户提示 |
| 聊天记录膨胀 | 成本、速度与一致性下降 | 以结构化状态和版本实体为真相来源 |
| 资产版本管理复杂 | 修改可能覆盖历史成果 | 所有生成与编辑均追加版本，不做原地覆盖 |

---

## 13. 首轮验收清单

### 产品验收

- [ ] 用户可以创建歌曲项目。
- [ ] 用户可以用自然语言输入灵感。
- [ ] 系统可以生成并让用户确认 SongSpec。
- [ ] 系统可以生成歌词、和弦、MIDI 与编曲方案。
- [ ] 用户可以查看每类资产的历史版本。
- [ ] 用户可以提出自然语言修改请求。
- [ ] 系统可以对修改影响范围进行说明。
- [ ] 用户可以导出项目 ZIP。
- [ ] 用户可以试听至少一个 Demo 版本。

### 工程验收

- [ ] API、Worker、数据库和对象存储可通过 Docker Compose 启动。
- [ ] 异步任务具备 pending/running/succeeded/failed/cancelled 状态。
- [ ] 核心数据模型有迁移和约束。
- [ ] 关键业务逻辑有单元测试。
- [ ] 完整主流程有集成测试。
- [ ] 生产环境日志可关联 `project_id`、`generation_run_id`、`artifact_version_id`。
- [ ] 音乐生成 Provider 可替换，不与业务层强耦合。

---

## 14. 推荐的首个 Demo 场景

为避免首轮范围失控，建议以一个标准演示场景为中心开发：

```text
输入：
“写一首关于深夜回家的中文日系 Indie Rock 歌曲。
主歌孤独克制，副歌有向上、释怀的感觉。
128 BPM，4/4，时长约 3 分半。”

输出：
1. SongSpec
2. 歌词（主歌/预副歌/副歌/桥段）
3. E Major 下的和弦进行
4. 主旋律与 Hook MIDI
5. 编曲方案
6. Demo
7. 用户反馈“副歌更高、更炸，桥段去掉鼓”后的 v2 版本
8. 可下载项目 ZIP
```

这个场景应成为：

- 产品演示基准。
- 端到端测试样本。
- Agent Evaluation 样本。
- 对外展示作品集的核心案例。

---

## 15. 下一步建议

开发开始前，优先完成以下三件事：

1. 定义 `SongSpec`、`ArtifactVersion`、`RevisionRequest` 的 Pydantic Schema。
2. 画出 LangGraph 主流程及每个节点的输入、输出、失败策略。
3. 先完成“无音频生成模型”的资产闭环，再接入 Demo Provider。

这样可以让首轮产品在模型质量波动、GPU 不稳定或音频生成成本较高的情况下，仍然具备独立可用价值。
