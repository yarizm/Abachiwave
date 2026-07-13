export const LOCALE_COOKIE = "abachiwave_locale";

export type Locale = "en" | "zh-CN";
export type TranslationParams = Record<string, number | string>;

export const DEFAULT_LOCALE: Locale = "en";

export const zhCN = {
  "Music creation workspace": "音乐创作工作台",
  Primary: "主导航",
  Login: "登录",
  Projects: "项目",
  Language: "语言",
  English: "英文",
  Chinese: "中文",
  "Local development login": "本地开发登录",
  "Authentication is intentionally a placeholder in Milestone 0. Use the local projects workspace to verify the API, database, and frontend integration.":
    "Milestone 0 暂时使用登录占位页。请进入本地项目工作台，验证 API、数据库和前端集成。",
  "Open projects": "打开项目",
  "Create project": "创建项目",
  "Start with a song title or working idea. Creative asset generation begins later.":
    "先输入歌曲标题或创作构想，之后再生成创作资产。",
  "Project name": "项目名称",
  "Night Ride": "夜行",
  Description: "描述",
  "Chinese indie rock demo about riding home late at night": "关于深夜骑车回家的中文独立摇滚 Demo",
  Creating: "正在创建",
  "{active} active - {archived} archived": "{active} 个进行中 - {archived} 个已归档",
  Refresh: "刷新",
  "Project filters": "项目筛选",
  Active: "进行中",
  Archived: "已归档",
  All: "全部",
  "Search projects": "搜索项目",
  "Loading projects...": "正在加载项目...",
  "No projects yet. Create one to verify the local stack.": "还没有项目。创建一个项目以验证本地服务。",
  "No projects match the current filters.": "没有符合当前筛选条件的项目。",
  "No description": "暂无描述",
  "Updated {date}": "更新于 {date}",
  "Project workspace": "项目工作台",
  "Loading project": "正在加载项目",
  "Project settings": "项目设置",
  Name: "名称",
  "Save details": "保存详情",
  "Current status: {status}": "当前状态：{status}",
  "Restore project": "恢复项目",
  "Archive project": "归档项目",
  Archive: "归档",
  "Loading status": "正在加载状态",
  "Idea intake": "灵感输入",
  "Song idea": "歌曲灵感",
  "Chinese indie rock song about riding home late at night...": "一首关于深夜骑车回家的中文独立摇滚歌曲...",
  "Save intake": "保存灵感",
  "Generate SongSpec draft": "生成 SongSpec 草稿",
  "SongSpec editor": "SongSpec 编辑器",
  "No SongSpec draft yet. Save an intake, then generate a draft.":
    "尚无 SongSpec 草稿。请先保存灵感，再生成草稿。",
  "SongSpec versions": "SongSpec 版本",
  "No versions have been generated.": "尚未生成任何版本。",
  "Missing {count}": "缺少 {count} 项",
  Complete: "完整",
  Theme: "主题",
  Genre: "风格",
  BPM: "BPM",
  Key: "调式",
  Time: "拍号",
  "Duration seconds": "目标时长（秒）",
  "Mood curve JSON": "情绪曲线 JSON",
  "Song structure, one section per line": "歌曲结构（每行一个段落）",
  "Missing: {items}": "缺少：{items}",
  "Save new version": "保存新版本",
  Approve: "确认",
  Lyrics: "歌词",
  "Generate lyrics": "生成歌词",
  "Hook candidates": "Hook 候选",
  "Hook candidate {number}": "Hook 候选 {number}",
  "Save lyrics version": "保存歌词版本",
  "Approve a SongSpec, then generate a lyrics draft.": "请先确认 SongSpec，再生成歌词草稿。",
  Chords: "和弦",
  "Generate chords": "生成和弦",
  Bars: "小节数",
  "Save chords version": "保存和弦版本",
  "Approve a SongSpec, then generate a chord progression.": "请先确认 SongSpec，再生成和弦进行。",
  "Generate MIDI": "生成 MIDI",
  "Generated chord, melody, and hook MIDI files will appear here.":
    "生成的和弦、旋律和 Hook MIDI 文件会显示在这里。",
  Audio: "音频",
  "WAV file": "WAV 文件",
  Kind: "类型",
  Humming: "哼唱",
  Reference: "参考音频",
  Scratch: "草稿",
  Other: "其他",
  Notes: "备注",
  "Chorus melody sketch, reference groove, or scratch idea...": "副歌旋律草稿、参考律动或临时想法...",
  "Upload WAV": "上传 WAV",
  "MIDI ready: {id}": "MIDI 已就绪：{id}",
  Cancel: "取消",
  "midi ready": "MIDI 已就绪",
  "Uploaded WAV sketches and references will appear here.": "上传的 WAV 草稿和参考音频会显示在这里。",
  Save: "保存",
  "Extracting": "正在提取",
  "Extract MIDI": "提取 MIDI",
  "Audio waveform": "音频波形",
  Demo: "Demo",
  "Generate WAV demo": "生成 WAV Demo",
  "Demo generation is running. Status refreshes automatically.": "Demo 正在生成，状态会自动刷新。",
  "Demo comparison": "Demo 对比",
  "Demo v{version}": "Demo v{version}",
  "demo ready": "Demo 已就绪",
  Retry: "重试",
  "Generated WAV demos will appear here for browser playback.":
    "生成的 WAV Demo 会显示在这里，可直接在浏览器中播放。",
  Arrangement: "编曲方案",
  "Generate arrangement": "生成编曲方案",
  Overview: "概览",
  Instruments: "乐器",
  Energy: "能量",
  "Production notes": "制作备注",
  "Mix notes": "混音备注",
  "Reference notes": "参考备注",
  "Save arrangement version": "保存编曲方案版本",
  "Complete SongSpec, lyrics, chords, and MIDI before generating an arrangement.":
    "请先完成 SongSpec、歌词、和弦与 MIDI，再生成编曲方案。",
  Export: "导出",
  "Export ZIP": "导出 ZIP",
  "Current assets": "当前资产",
  Timeline: "时间线",
  "Export {id}": "导出包 {id}",
  "no file": "无文件",
  "Not downloadable": "不可下载",
  "Ready export bundles will appear here.": "可下载的导出包会显示在这里。",
  Revisions: "修改请求",
  Feedback: "反馈",
  "Make the chorus lyric stronger, lift the chorus melody, or make the bridge more sparse...":
    "让副歌歌词更有力量、抬高副歌旋律，或让桥段更简洁...",
  "Plan revision": "规划修改",
  "Impact preview": "影响范围预览",
  "all sections": "所有段落",
  "demo recommended": "建议重新生成 Demo",
  "demo optional": "可不重新生成 Demo",
  supported: "支持",
  unsupported: "不支持",
  Apply: "应用",
  "Apply + demo": "应用并生成 Demo",
  Reject: "拒绝",
  "Planned revisions will show their affected assets before changes are applied.":
    "规划后的修改会在应用前显示受影响的资产。",
  "Version tools": "版本工具",
  "Melody MIDI": "旋律 MIDI",
  "Need at least two versions": "至少需要两个版本",
  "Compare v{left} to v{right}": "对比 v{left} 与 v{right}",
  Diff: "对比",
  Restore: "恢复",
  "Before:": "修改前：",
  "After:": "修改后：",
  empty: "空",
  "No field-level changes detected.": "未检测到字段级变化。",
  "Revision history": "修改历史",
  "Created: {versions}": "已创建：{versions}",
  "{count} tasks": "{count} 个任务",
  "Revision history is empty.": "修改历史为空。",
  Comments: "评论",
  "{count} open": "{count} 条待处理",
  Author: "作者",
  Target: "目标",
  Comment: "评论内容",
  "Leave feedback, handoff notes, or a decision to revisit later...": "留下反馈、交接备注或待后续确认的决定...",
  "Add comment": "添加评论",
  Resolve: "解决",
  Reopen: "重新打开",
  "Comments and handoff notes will appear here.": "评论和交接备注会显示在这里。",
  Project: "项目",
  "Audio: {filename}": "音频：{filename}",
  "Export: {status}": "导出：{status}",
  "Revision: {status}": "修改请求：{status}",
  Activity: "活动记录",
  "No activity has been recorded.": "尚无活动记录。",
  "Handoff summary": "交接摘要",
  Readiness: "就绪度",
  "Open comments": "待处理评论",
  "Missing items": "缺失项",
  "Next actions": "后续操作",
  "Handoff summary will appear after the workspace loads.": "工作台加载后会显示交接摘要。",
  "Project review": "项目审查",
  "Project review will appear after the workspace loads.": "工作台加载后会显示项目审查。",
  "Ready for handoff": "可以交接",
  "Needs work": "需要完善",
  Blocked: "受阻",
  "No linked asset": "无关联资产",
  "revision {id}": "修改请求 {id}",
  "run {id}": "任务 {id}",
  "asset {id}": "资产 {id}",
  "{count} versions": "{count} 个版本",
  Download: "下载",
  Downloading: "正在下载",
  "Download failed": "下载失败",
  "Task failed": "任务失败",
  "Export failed": "导出失败",
  "Request ID: {id}": "请求 ID：{id}",
  "Project name is required.": "项目名称不能为空。",
  "Project name must be 120 characters or fewer.": "项目名称不能超过 120 个字符。",
  "Project description must be 1000 characters or fewer.": "项目描述不能超过 1000 个字符。",
  "Song idea is required.": "歌曲灵感不能为空。",
  "Song idea must be 4000 characters or fewer.": "歌曲灵感不能超过 4000 个字符。",
  "Revision feedback is required.": "修改反馈不能为空。",
  "Comment text is required.": "评论内容不能为空。",
  "Choose a WAV file to upload.": "请选择要上传的 WAV 文件。",
  "Only WAV uploads are supported.": "仅支持上传 WAV 文件。",
  "Audio notes must be 2000 characters or fewer.": "音频备注不能超过 2000 个字符。",
  "At least one lyric section is required.": "至少需要一个歌词段落。",
  "Lyric section text must not be empty.": "歌词段落内容不能为空。",
  "At least one chord section is required.": "至少需要一个和弦段落。",
  "Chord sections need at least one bar and one chord.": "每个和弦段落至少需要一个小节和一个和弦。",
  "Chord names must not be empty.": "和弦名称不能为空。",
  "Arrangement overview is required.": "编曲方案概览不能为空。",
  "At least one arrangement section is required.": "至少需要一个编曲段落。",
  "Arrangement sections need instruments, notes, and energy from 1 to 10.":
    "编曲段落需要乐器、制作备注以及 1 到 10 的能量值。",
  "Mix notes and reference notes are required.": "混音备注和参考备注不能为空。",
  "Mood curve must be valid JSON.": "情绪曲线必须是有效的 JSON。",
  "Local collaborator": "本地协作者",
  "What is the song about, and what perspective should it use?": "歌曲讲述什么主题，应采用什么叙事视角？",
  "Which genre or reference style should guide the song?": "歌曲应以哪种风格或参考类型为方向？",
  "Which language should the lyrics use?": "歌词应使用哪种语言？",
  "What BPM should the song target?": "歌曲的目标 BPM 是多少？",
  "Which musical key should the draft use?": "草稿应使用什么调式？",
  "What time signature should the song use?": "歌曲应使用什么拍号？",
  "What target duration should the song have?": "歌曲的目标时长是多少？",
  "How should the emotion change between verse and chorus?": "主歌到副歌之间的情绪应如何变化？",
  "Which sections should the song include?": "歌曲应包含哪些段落？",
  "Loading workspace": "正在加载工作台",
  "Failed to load workspace": "加载工作台失败",
  "Failed to refresh task status": "刷新任务状态失败",
  "Failed to load projects": "加载项目失败",
  "Failed to create project": "创建项目失败",
  "Failed to save intake": "保存灵感失败",
  "Failed to generate SongSpec": "生成 SongSpec 失败",
  "Failed to edit SongSpec": "编辑 SongSpec 失败",
  "Failed to approve SongSpec": "确认 SongSpec 失败",
  "Failed to generate lyrics": "生成歌词失败",
  "Failed to edit lyrics": "编辑歌词失败",
  "Failed to generate chords": "生成和弦失败",
  "Failed to edit chords": "编辑和弦失败",
  "Failed to generate MIDI": "生成 MIDI 失败",
  "Failed to upload audio": "上传音频失败",
  "Failed to update audio": "更新音频失败",
  "Failed to extract melody MIDI": "提取旋律 MIDI 失败",
  "Failed to generate arrangement": "生成编曲方案失败",
  "Failed to edit arrangement": "编辑编曲方案失败",
  "Failed to export project": "导出项目失败",
  "Failed to generate demo": "生成 Demo 失败",
  "Failed to retry demo": "重试 Demo 失败",
  "Failed to cancel task": "取消任务失败",
  "Failed to plan revision": "规划修改失败",
  "Failed to apply revision": "应用修改失败",
  "Failed to reject revision": "拒绝修改失败",
  "Failed to create comment": "创建评论失败",
  "Failed to update comment": "更新评论失败",
  "Failed to compare versions": "对比版本失败",
  "Failed to restore version": "恢复版本失败",
  "Failed to update project": "更新项目失败",
  "Failed to update project status": "更新项目状态失败",
  "Create an idea intake before generating a SongSpec.": "生成 SongSpec 前请先创建灵感输入。",
  "Approve a SongSpec before generating lyrics.": "生成歌词前请先确认 SongSpec。",
  "Approve a SongSpec before generating chords.": "生成和弦前请先确认 SongSpec。",
  "Approve a SongSpec before generating MIDI.": "生成 MIDI 前请先确认 SongSpec。",
  "Approve a SongSpec before extracting melody MIDI.": "提取旋律 MIDI 前请先确认 SongSpec。",
  "Approve a SongSpec before generating an arrangement.": "生成编曲方案前请先确认 SongSpec。",
  active: "进行中",
  archived: "已归档",
  loading: "正在加载",
  clarification: "需要澄清",
  draft: "草稿",
  approved: "已确认",
  superseded: "已取代",
  planned: "已规划",
  applied: "已应用",
  rejected: "已拒绝",
  open: "待处理",
  resolved: "已解决",
  queued: "排队中",
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  cancelled: "已取消",
  ready: "就绪",
  available: "可用",
  humming: "哼唱",
  reference: "参考音频",
  scratch: "草稿",
  other: "其他",
  chord: "和弦",
  melody: "旋律",
  hook: "Hook",
  lyrics: "歌词",
  chords: "和弦",
  midi: "MIDI",
  arrangement: "编曲方案",
  demo: "Demo",
  song_spec: "SongSpec",
  audio_upload: "音频上传",
  revision: "修改请求",
  export: "导出",
  theme: "主题",
  genre: "风格",
  language: "语言",
  tempo_bpm: "BPM",
  key: "调式",
  time_signature: "拍号",
  target_duration_seconds: "目标时长",
  mood_curve: "情绪曲线",
  song_structure: "歌曲结构",
  pass: "通过",
  warning: "提醒",
  fail: "未通过",
  "Approved SongSpec": "已确认的 SongSpec",
  "MIDI assets": "MIDI 资产",
  "Export bundle": "导出包",
  "Task health": "任务健康状态",
  "approved song spec": "已确认的 SongSpec",
  "chord midi": "和弦 MIDI",
  "melody midi": "旋律 MIDI",
  "hook midi": "Hook MIDI",
  "Approve a complete SongSpec before generating assets.": "生成资产前请先确认完整的 SongSpec。",
  "Generate or restore a lyrics version.": "请生成或恢复一个歌词版本。",
  "Generate or restore a chord progression.": "请生成或恢复一个和弦进行版本。",
  "Chord, melody, and hook MIDI exist.": "和弦、旋律与 Hook MIDI 均已存在。",
  "Generate chord, melody, and hook MIDI.": "请生成和弦、旋律与 Hook MIDI。",
  "Generate an arrangement plan from the complete asset chain.": "请基于完整资产链生成编曲方案。",
  "At least one playable demo exists.": "至少已有一个可播放的 Demo。",
  "A generation task is still running.": "仍有生成任务正在运行。",
  "Generate a demo for listening review.": "请生成 Demo 以进行试听审查。",
  "Complete the asset chain before generating a demo.": "生成 Demo 前请先完成资产链。",
  "A ready ZIP export exists.": "已有可用的 ZIP 导出包。",
  "The latest export attempt failed.": "最近一次导出失败。",
  "Create a ZIP export package.": "请创建 ZIP 导出包。",
  "Resolve missing prerequisites first.": "请先补齐缺失的前置资产。",
  "No active or failed tasks.": "没有运行中或失败的任务。",
  Intro: "前奏",
  Verse: "主歌",
  "Pre-Chorus": "预副歌",
  Chorus: "副歌",
  Bridge: "桥段",
  Outro: "尾奏",
  Hook: "Hook",
  "Chord MIDI": "和弦 MIDI",
  "The request could not be mapped to lyrics, melody MIDI, or arrangement.":
    "无法将该请求映射到歌词、旋律 MIDI 或编曲方案。",
  "Lyric text changed.": "歌词文本已变化。",
  "MIDI file content changed.": "MIDI 文件内容已变化。",
  "MIDI file content is unchanged.": "MIDI 文件内容未变化。",
  "MIDI file size changed.": "MIDI 文件大小已变化。",
  "Arrangement text changed.": "编曲方案文本已变化。",
  "Arrangement section details changed.": "编曲段落详情已变化。",
  "Demo duration comparison.": "Demo 时长对比。",
  "Demo audio content changed.": "Demo 音频内容已变化。",
  "Demo audio content is unchanged.": "Demo 音频内容未变化。",
  "MIDI checksum": "MIDI 校验和",
  "File size": "文件大小",
  "Arrangement sections": "编曲段落",
  "Audio checksum": "音频校验和",
  Duration: "时长",
  overview: "概览",
  "mix notes": "混音备注",
  "reference notes": "参考备注",
  chorus: "副歌",
  verse: "主歌",
  bridge: "桥段",
  intro: "前奏",
  outro: "尾奏",
  "the most relevant section": "最相关的段落",
  "the hook/chorus": "Hook/副歌",
  "the requested sections": "指定段落",
  "No changes detected.": "未检测到变化。",
  "Project status": "项目状态",
  Review: "审查",
  Generated: "生成时间",
  "Current Assets": "当前资产",
  "Missing Prerequisites": "缺失的前置资产",
  "Open Comments": "待处理评论",
  "Recent Activity": "最近活动",
  None: "无",
  missing: "缺失",
} as const;

export type TranslationKey = keyof typeof zhCN;

export function isLocale(value: string | undefined): value is Locale {
  return value === "en" || value === "zh-CN";
}

export function translate(
  locale: Locale,
  key: TranslationKey,
  params: TranslationParams = {},
): string {
  const template = locale === "zh-CN" ? zhCN[key] : key;
  return interpolate(template, params);
}

export function translateText(locale: Locale, value: string): string {
  if (locale !== "zh-CN") {
    return value;
  }
  return (zhCN as Record<string, string>)[value] ?? translatePattern(value) ?? value;
}

export function formatDateTime(locale: Locale, value: string): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatLocalizedError(
  locale: Locale,
  error: unknown,
  fallback: TranslationKey,
): string {
  if (locale === "en" && error instanceof Error) {
    return error.message;
  }
  const base = translate(locale, fallback);
  if (typeof error !== "object" || error === null) {
    return base;
  }
  const status = "status" in error && typeof error.status === "number" ? ` (${error.status})` : "";
  const requestId =
    "requestId" in error && typeof error.requestId === "string"
      ? ` - ${translate(locale, "Request ID: {id}", { id: error.requestId })}`
      : "";
  return `${base}${status}${requestId}`;
}

function interpolate(template: string, params: TranslationParams): string {
  return template.replaceAll(/\{([a-zA-Z_]+)\}/g, (match, key: string) =>
    key in params ? String(params[key]) : match,
  );
}

const EVENT_SEGMENTS: Record<string, string> = {
  project: "项目",
  intake: "灵感输入",
  song_spec: "SongSpec",
  lyrics: "歌词",
  chords: "和弦",
  midi: "MIDI",
  arrangement: "编曲方案",
  export: "导出",
  demo: "Demo",
  task: "任务",
  revision: "修改请求",
  version: "版本",
  comment: "评论",
  audio: "音频",
  created: "已创建",
  updated: "已更新",
  generated: "已生成",
  edited: "已编辑",
  approved: "已确认",
  cancelled: "已取消",
  planned: "已规划",
  rejected: "已拒绝",
  applied: "已应用",
  restored: "已恢复",
  uploaded: "已上传",
  archived: "已归档",
  version_created: "已创建版本",
  midi_extracted: "已提取 MIDI",
};

function translatePattern(value: string): string | null {
  const numberedSection = /^(Verse|Chorus)\s+(\d+)$/.exec(value);
  if (numberedSection) {
    const label = numberedSection[1] === "Verse" ? "主歌" : "副歌";
    return `${label} ${numberedSection[2]}`;
  }

  const assetVersion = /^(SongSpec|Lyrics|Chords|Arrangement|Chord MIDI|Melody MIDI|Hook MIDI) v(\d+)$/.exec(
    value,
  );
  if (assetVersion) {
    const label = (zhCN as Record<string, string>)[assetVersion[1]] ?? assetVersion[1];
    return `${label} v${assetVersion[2]}`;
  }

  const usingAsset = /^Using (.+)\.$/.exec(value);
  if (usingAsset) {
    return `正在使用 ${translateText("zh-CN", usingAsset[1])}。`;
  }

  const missingMidi = /^Missing MIDI kinds: (.+)\.$/.exec(value);
  if (missingMidi) {
    return `缺少 MIDI 类型：${missingMidi[1]
      .split(", ")
      .map((kind) => translateText("zh-CN", kind))
      .join("、")}。`;
  }

  const activeTasks = /^(\d+) generation task is still active\.$/.exec(value);
  if (activeTasks) {
    return `仍有 ${activeTasks[1]} 个生成任务正在运行。`;
  }
  const failedTasks = /^(\d+) generation task has failed and may need retry\.$/.exec(value);
  if (failedTasks) {
    return `有 ${failedTasks[1]} 个生成任务失败，可能需要重试。`;
  }
  const openComments = /^Resolve (\d+) open project comment\(s\)\.$/.exec(value);
  if (openComments) {
    return `解决 ${openComments[1]} 条待处理项目评论。`;
  }

  const revisionTask = /^(Revise lyrics|Raise the melody guide|Update arrangement notes) for (.+)\.$/.exec(
    value,
  );
  if (revisionTask) {
    const target = translateText("zh-CN", revisionTask[2]);
    const action = (
      {
        "Revise lyrics": "修改歌词",
        "Raise the melody guide": "抬高旋律引导",
        "Update arrangement notes": "更新编曲备注",
      } as Record<string, string>
    )[revisionTask[1]];
    return `${action}：${target}。`;
  }

  const changes = /^(\d+) changes detected\.$/.exec(value);
  if (changes) {
    return `检测到 ${changes[1]} 处变化。`;
  }

  const sectionLyrics = /^(.+) lyrics$/.exec(value);
  if (sectionLyrics) {
    return `${translateText("zh-CN", sectionLyrics[1])}歌词`;
  }

  if (value.includes(".") && value.split(".").every((part) => /^[a-z_]+$/.test(part))) {
    return value
      .split(".")
      .map((part) => EVENT_SEGMENTS[part] ?? part.replaceAll("_", " "))
      .join(" · ");
  }
  return null;
}
