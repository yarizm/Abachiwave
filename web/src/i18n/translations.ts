export const LOCALE_COOKIE = "abachiwave_locale";
export const THEME_COOKIE = "abachiwave_theme";

export type Locale = "en" | "zh-CN";
export type Theme = "light" | "dark";
export type TranslationParams = Record<string, number | string>;

export const DEFAULT_LOCALE: Locale = "en";
export const DEFAULT_THEME: Theme = "light";

export const zhCN = {
  "Music creation workspace": "音乐创作工作台",
  Primary: "主导航",
  Login: "登录",
  Projects: "项目",
  Language: "语言",
  English: "英文",
  Chinese: "中文",
  "Color theme": "主题",
  Light: "浅色",
  Dark: "深色",
  "Toggle theme": "切换主题",
  "Creation chain": "创作链路",
  "Section view": "分段对照",
  "Full editors": "完整编辑器",
  "Composition view": "创作视图",
  "Lyrics, chords and melody for each section of the song.": "逐段对照歌词、和弦与旋律。",
  "No lyrics in this section": "本段暂无歌词",
  "No chords in this section": "本段暂无和弦",
  "No melody in this section": "本段暂无旋律",
  "Needs lyrics": "缺歌词",
  "Needs chords": "缺和弦",
  "Needs melody": "缺旋律",
  "Audition {section}": "试听{section}",
  "Stop {section}": "停止{section}",
  "Nothing to play in this section": "本段没有可播放的内容",
  "Audio could not start": "音频无法启动",
  "Unassigned melody": "未归段旋律",
  "{count} notes carry no section. Audio extraction reads a MIDI file, which has no song structure — assign them to hear them in place.":
    "有 {count} 个音符未归段。音频提取读的是 MIDI 文件，其中没有歌曲结构信息——指派后即可按段查看。",
  "Assign to {section}": "指派到{section}",
  "Assign selected notes": "指派选中音符",
  "Sections used by an asset but missing from the SongSpec structure: {ids}":
    "以下段落被资产引用，但不在 SongSpec 结构中：{ids}",
  "Approve a SongSpec to lay out sections": "审批 SongSpec 后即可按段排列",
  "Workspace sections": "工作台分区",
  SongSpec: "歌曲规格",
  Composition: "词曲创作",
  History: "历史",
  Settings: "设置",
  "Back to projects": "返回项目列表",
  "Step {number}": "第 {number} 步",
  "Chain step: idea": "灵感",
  "Chain step: song spec": "歌曲规格",
  "Chain step: approve": "审批",
  "Chain step: composition": "词曲资产",
  "Chain step: arrangement": "编排",
  "Chain step: demo": "试听",
  "Chain step: export": "导出",
  "Jump to {step}": "跳转到{step}",
  "Go to SongSpec": "前往歌曲规格",
  "Go to composition": "前往词曲资产",
  "Go to arrangement": "前往编排",
  "Approve a SongSpec first": "请先审批歌曲规格",
  "Generate lyrics after approving a SongSpec": "审批歌曲规格后即可生成歌词草稿。",
  "Generate a lyrics draft from your approved SongSpec.": "基于已审批的歌曲规格生成歌词草稿。",
  "Add composition assets first": "请先补齐词曲资产",
  "Generate MIDI from approved chords and lyrics": "基于已审批的和弦与歌词生成 MIDI。",
  "Complete composition before arrangement": "请先完成词曲资产",
  "Generate an arrangement from your composition": "基于词曲资产生成编排方案。",
  "Complete arrangement before demo": "请先完成编排",
  "Generate a demo from your arrangement": "基于编排生成试听 Demo。",
  Dismiss: "关闭",
  "Project saved": "项目已保存",
  "Lyrics saved": "歌词已保存",
  "Chords saved": "和弦已保存",
  "SongSpec saved": "歌曲规格已保存",
  "SongSpec approved": "歌曲规格已审批",
  "Arrangement saved": "编排已保存",
  "Comment added": "评论已添加",
  "Demo generation started": "Demo 生成已开始",
  "Arrangement generation started": "编排生成已开始",
  "Lyrics generation started": "歌词生成已开始",
  "Chords generation started": "和弦生成已开始",
  "MIDI generation started": "MIDI 生成已开始",
  "Status: queued": "状态：排队中",
  "Status: running": "状态：生成中",
  "Status: succeeded": "状态：已完成",
  "Status: failed": "状态：失败",
  "Status: cancelled": "状态：已取消",
  "Task is queued, will start shortly": "任务已排队，即将开始",
  "Task is running, status refreshes automatically": "任务进行中，状态自动刷新",
  "Press {keys} to submit": "按 {keys} 提交",
  "Press {keys} to save": "按 {keys} 保存",
  "Press Esc to close": "按 Esc 关闭",
  "Approve a SongSpec to enable generation": "需先审批歌曲规格才能生成",
  "Complete lyrics, chords, and MIDI to enable arrangement": "需先完成歌词、和弦与 MIDI 才能生成编排",
  "Complete all prerequisites to enable export": "需先补齐所有前置资产才能导出",
  "Complete all prerequisites to enable demo": "需先补齐所有前置资产才能生成 Demo",
  "A generation run is already active": "已有生成任务在运行中",
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
  "AI candidates": "AI 候选",
  "AI provider list could not be loaded.": "无法加载 AI 提供方列表。",
  "AI candidate list could not be loaded.": "无法加载 AI 候选列表。",
  "Retry AI data": "重新加载 AI 数据",
  Workflow: "工作流",
  Provider: "提供方",
  Candidates: "候选数量",
  "Generate candidates": "生成候选",
  "Use local fallback": "使用本地回退",
  "Candidate {number}": "候选 {number}",
  "Score {score}": "评分 {score}",
  Selected: "已选择",
  "Select candidate": "选择候选",
  "No candidates for this workflow yet.": "此工作流尚无候选。",
  "Save an idea intake first.": "请先保存灵感输入。",
  "Approve a SongSpec first.": "请先确认 SongSpec。",
  "Complete the arrangement prerequisites first.": "请先完成编曲所需资产。",
  "{count} sections": "{count} 个段落",
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
  "Edit in Song Structure": "在歌曲结构编辑器中修改",
  "Missing: {items}": "缺少：{items}",
  "Save new version": "保存新版本",
  Approve: "确认",
  Lyrics: "歌词",
  "Lyrics editor": "歌词编辑器",
  "Edit controlled lyric lines, rhyme marks, and rewrite candidates.":
    "按行编辑歌词、韵脚标记和改写候选。",
  Unsaved: "未保存",
  "{count} lines": "{count} 行",
  "Rewrite section": "改写段落",
  "{section} line {number}": "{section}第 {number} 行",
  "{count} chars": "{count} 字",
  "{count} syllables": "{count} 音节",
  "Rhyme: {value}": "韵脚：{value}",
  "Stress: {value}": "重音：{value}",
  Mark: "标记",
  "Rewrite line": "改写本行",
  "Delete line": "删除本行",
  "Add line": "添加一行",
  "Rewrite studio": "改写工作区",
  "Targeting one selected line.": "正在处理选中的一行。",
  "Targeting {section}.": "正在处理{section}。",
  "a section": "一个段落",
  "Targeting all lyric lines.": "正在处理全部歌词。",
  "Rewrite scope": "改写范围",
  Line: "单行",
  Section: "段落",
  Action: "操作",
  Direction: "改写要求",
  "Use a sharper image and fewer filler words": "使用更鲜明的意象，减少填充词",
  Tone: "语气",
  "intimate, restrained": "亲密、克制",
  "Rhyme ending": "韵脚结尾",
  home: "归途",
  "Rhyme mark": "韵脚标记",
  "Avoided expressions": "避免使用的表达",
  "Comma-separated words or phrases": "用逗号分隔词语或短语",
  "Preferred vocabulary": "偏好词汇",
  "Words and images to favor": "希望优先使用的词语和意象",
  "{count} avoided-expression matches in the current draft.":
    "当前草稿中有 {count} 处命中应避免的表达。",
  "Generating preview": "正在生成预览",
  "Preview rewrite": "预览改写",
  "Original / candidate diff": "原文与候选对比",
  "{count} changed lines. Accept changes into the local draft before saving.":
    "共改动 {count} 行。请先接受改动到本地草稿，再保存版本。",
  "Accept section": "接受本段",
  "Accept all": "全部接受",
  Original: "原文",
  Candidate: "候选",
  "Accept line": "接受本行",
  "Discard draft": "放弃草稿",
  Saving: "正在保存",
  Expand: "扩写",
  Compress: "压缩",
  "Change rhyme": "调整韵脚",
  "Adjust tone": "调整语气",
  Rewrite: "改写",
  "Enter a rhyme ending before generating a preview.": "生成预览前请先输入韵脚结尾。",
  "Avoided expressions were detected and removed from rewrite candidates.":
    "检测到应避免的表达，已从改写候选中移除。",
  "The deterministic rewrite did not change the selected lines.":
    "本次确定性改写没有改变选中的歌词行。",
  "Generate lyrics": "生成歌词",
  "Hook candidates": "Hook 候选",
  "Hook candidate {number}": "Hook 候选 {number}",
  "Save lyrics version": "保存歌词版本",
  "Approve a SongSpec, then generate a lyrics draft.": "请先确认 SongSpec，再生成歌词草稿。",
  Chords: "和弦",
  "Chord editor": "和弦编辑器",
  "Place validated chords by measure and beat, then audition the progression.":
    "按小节和拍点放置经过校验的和弦，并试听整段进行。",
  "Generate chords": "生成和弦",
  "Chord project settings": "和弦工程设置",
  Meter: "拍号",
  "Chord display mode": "和弦显示方式",
  Symbols: "和弦符号",
  Roman: "罗马数字",
  Nashville: "Nashville 数字谱",
  "Chord audition controls": "和弦试听控制",
  Validated: "已校验",
  Validate: "校验",
  Stop: "停止",
  Audition: "试听",
  Metronome: "节拍器",
  Loop: "循环",
  "{count} measures": "{count} 小节",
  "Add measure": "添加小节",
  "Measure {number}": "第 {number} 小节",
  "Delete measure": "删除小节",
  "Chord symbol in measure {number}": "第 {number} 小节的和弦符号",
  "Delete chord": "删除和弦",
  Borrowed: "借用和弦",
  Beat: "拍点",
  Length: "时值",
  Inversion: "转位",
  Root: "原位",
  "Validate to refresh theory labels and playback notes.": "校验后刷新理论标记与试听音高。",
  "Add chord": "添加和弦",
  Transpose: "移调",
  Interval: "音程",
  semitones: "半音",
  Scope: "范围",
  "Entire song": "全曲",
  "Create transposed version": "创建移调版本",
  "Saving creates a new immutable version.": "保存会创建一个新的不可变版本。",
  "All chord edits are saved.": "所有和弦修改均已保存。",
  "Browser audio could not start. Check audio permissions and try again.":
    "浏览器音频无法启动，请检查音频权限后重试。",
  "Save or discard the local draft before transposing.": "移调前请先保存或放弃本地草稿。",
  "This measure has no free beat for another chord.": "该小节没有可放置新和弦的空闲拍点。",
  Bars: "小节数",
  "Save chords version": "保存和弦版本",
  "Approve a SongSpec, then generate a chord progression.": "请先确认 SongSpec，再生成和弦进行。",
  "Generate MIDI": "生成 MIDI",
  "Generated chord, melody, and hook MIDI files will appear here.":
    "生成的和弦、旋律和 Hook MIDI 文件会显示在这里。",
  "Edit notes on a piano roll and save immutable MIDI versions.":
    "在钢琴卷帘中编辑音符，并保存为不可变 MIDI 版本。",
  "MIDI track": "MIDI 轨道",
  "Overlay tracks": "叠加显示轨道",
  "MIDI editor tools": "MIDI 编辑工具",
  "MIDI piano roll": "MIDI 钢琴卷帘",
  "Add note": "添加音符",
  Copy: "复制",
  Paste: "粘贴",
  "Duplicate notes": "复制所选音符",
  "Delete notes": "删除音符",
  "Save MIDI version": "保存 MIDI 版本",
  "MIDI versions": "MIDI 版本",
  "MIDI source: analysis v{version}": "MIDI 来源：分析 v{version}",
  "MIDI extraction has no linked analysis candidate.": "MIDI 提取未关联参考分析候选。",
  "Linked reference analysis": "已关联参考分析",
  "Direct audio extraction": "直接音频提取",
  "{count} notes selected": "已选择 {count} 个音符",
  notes: "个音符",
  Quantize: "量化",
  Velocity: "力度",
  Legato: "连奏",
  Humanize: "人性化",
  "Scale snap": "吸附到调式",
  "Save or discard the local MIDI draft before transforming.":
    "执行变换前，请先保存或放弃本地 MIDI 草稿。",
  "This legacy MIDI has no editable note data. Regenerate it to open the piano roll.":
    "该旧版 MIDI 没有可编辑音符数据，请重新生成后再打开钢琴卷帘。",
  "Failed to save MIDI": "保存 MIDI 失败",
  "Failed to transform MIDI": "变换 MIDI 失败",
  "MIDI saved": "MIDI 已保存",
  "MIDI transformed": "MIDI 已变换",
  Audio: "音频",
  "WAV file": "WAV 文件",
  "Audio file": "音频文件",
  Kind: "类型",
  Humming: "哼唱",
  Reference: "参考音频",
  Scratch: "草稿",
  Other: "其他",
  Notes: "备注",
  "Chorus melody sketch, reference groove, or scratch idea...": "副歌旋律草稿、参考律动或临时想法...",
  "Upload WAV": "上传 WAV",
  "Upload audio": "上传音频",
  "MIDI ready: {id}": "MIDI 已就绪：{id}",
  Cancel: "取消",
  "midi ready": "MIDI 已就绪",
  "Uploaded WAV sketches and references will appear here.": "上传的 WAV 草稿和参考音频会显示在这里。",
  "Uploaded audio sketches and references will appear here.":
    "上传的音频草稿和参考音频会显示在这里。",
  Save: "保存",
  "Extracting": "正在提取",
  "Extract MIDI": "提取 MIDI",
  "Create PCM WAV": "生成 PCM WAV",
  "Normalizing audio": "正在标准化音频",
  "PCM WAV ready": "PCM WAV 已就绪",
  "PCM WAV ready: {filename}": "PCM WAV 已就绪：{filename}",
  "Standard PCM WAV has not been generated yet.": "尚未生成标准 PCM WAV。",
  "PCM WAV normalization queued": "PCM WAV 标准化任务已加入队列",
  "Waiting for audio normalization": "等待音频标准化",
  "Playback will be available after normalization.": "标准化完成后即可试听。",
  "Audio normalization is queued.": "音频标准化任务正在排队。",
  "Audio normalization failed. Retry to continue.": "音频标准化失败，请重试后继续。",
  "Retry normalization": "重试标准化",
  "Audio waveform": "音频波形",
  "Waveform interaction mode": "波形交互模式",
  "Marker point": "标记点",
  "Analysis range": "分析范围",
  "Choose marker position from waveform": "从波形中选择标记位置",
  "Select analysis range from waveform": "从波形中选择分析范围",
  "Click the waveform to choose a marker position.": "点击波形即可选择标记位置。",
  "Drag across the waveform to choose an analysis range.": "在波形上拖动以选择分析范围。",
  Playhead: "播放头",
  "Selected range": "已选范围",
  "No range selected; extraction uses the full audio.": "尚未选择范围，将分析完整音频。",
  "Clear range": "清除范围",
  "Range start (seconds)": "范围起点（秒）",
  "Range end (seconds)": "范围终点（秒）",
  "Preview selected range": "试听所选范围",
  "Stop range preview": "停止范围试听",
  "Extract selected range": "提取所选范围",
  "Analyze reference": "分析参考音频",
  "Analyze selected range": "分析所选范围",
  "Analyzing reference": "正在分析参考音频",
  "Reference analysis queued": "参考音频分析任务已加入队列",
  "Reference analysis candidate": "参考分析候选",
  "Candidate only": "仅候选",
  "Analyzed range": "分析范围",
  beats: "拍",
  Tempo: "速度",
  "Time signature": "拍号",
  "Key / mode": "调性 / 调式",
  "Pitch range": "音高范围",
  "Integrated loudness": "综合响度",
  "Dynamic range": "动态范围",
  "Energy curve": "能量曲线",
  "Structure candidates": "结构候选",
  "Chord candidates": "和弦候选",
  "This analysis is a candidate and has not changed the SongSpec or current assets.":
    "此分析仅为候选，尚未更改 SongSpec 或当前资产。",
  "Apply selected fields to a new SongSpec draft": "将所选字段应用到新的 SongSpec 草稿",
  "Preview impact before creating a draft version.": "创建草稿版本前先预览影响。",
  "Checking impact": "正在检查影响",
  "Preview selected fields": "预览所选字段",
  Applied: "已应用",
  "Linked assets": "关联资产",
  "A new SongSpec draft will be created; the approved version remains current until approval.":
    "将创建新的 SongSpec 草稿；在确认该草稿前，当前已批准版本保持不变。",
  "Existing lyrics, chords, MIDI, and arrangements remain linked to the source SongSpec.":
    "现有歌词、和弦、MIDI 和编曲仍关联到来源 SongSpec，不会被修改。",
  "Confirm new SongSpec draft": "确认创建 SongSpec 草稿",
  "Created SongSpec v{version}": "已创建 SongSpec v{version}",
  "Approve a SongSpec before applying reference analysis.":
    "请先确认一个 SongSpec，再应用参考分析。",
  "Reference fields applied as SongSpec v{version}":
    "参考字段已应用为 SongSpec v{version}",
  "Jump to marker": "跳转到标记",
  "Audio markers": "音频标记",
  "Position (seconds)": "位置（秒）",
  "Marker label": "标记名称",
  "Verse entry, chorus lift, edit point...": "主歌进入、副歌抬升、编辑点...",
  "Section ID": "段落 ID",
  "Optional section link": "可选段落关联",
  "Marker notes": "标记备注",
  "Add marker": "添加标记",
  "Add markers to identify sections and analysis ranges.": "添加标记来标识段落和分析范围。",
  "Save marker": "保存标记",
  "Delete marker": "删除标记",
  "Delete this marker?": "确定删除这个标记吗？",
  "Audio marker added": "音频标记已添加",
  "Audio marker saved": "音频标记已保存",
  "Audio marker deleted": "音频标记已删除",
  "Marker label is required.": "请输入标记名称。",
  "Marker label must be 120 characters or fewer.": "标记名称不能超过 120 个字符。",
  "Marker position must be zero or greater.": "标记位置必须大于或等于 0。",
  "Marker position must be within the audio duration.": "标记位置必须位于音频时长范围内。",
  "Audio upload not found.": "未找到音频上传。",
  "Audio marker not found.": "未找到音频标记。",
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
  "Choose an audio file to upload.": "请选择要上传的音频文件。",
  "Use a WAV, MP3, M4A, FLAC, or OGG audio file.":
    "请选择 WAV、MP3、M4A、FLAC 或 OGG 音频文件。",
  "The audio filename and media type do not match.": "音频文件名与媒体类型不匹配。",
  "Audio notes must be 2000 characters or fewer.": "音频备注不能超过 2000 个字符。",
  "At least one lyric section is required.": "至少需要一个歌词段落。",
  "Lyric section text must not be empty.": "歌词段落内容不能为空。",
  "Each lyric section needs at least one line.": "每个歌词段落至少需要一行。",
  "Lyric lines must not be empty.": "歌词行不能为空。",
  "Lyric line IDs must be unique.": "歌词行 ID 必须唯一。",
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
  "Failed to generate candidates": "生成候选失败",
  "Failed to select candidate": "选择候选失败",
  "Failed to edit SongSpec": "编辑 SongSpec 失败",
  "Failed to approve SongSpec": "确认 SongSpec 失败",
  "Failed to generate lyrics": "生成歌词失败",
  "Failed to edit lyrics": "编辑歌词失败",
  "Failed to preview lyrics rewrite": "预览歌词改写失败",
  "Failed to generate chords": "生成和弦失败",
  "Failed to edit chords": "编辑和弦失败",
  "Failed to validate chords": "校验和弦失败",
  "Failed to transpose chords": "和弦移调失败",
  "Failed to generate MIDI": "生成 MIDI 失败",
  "Failed to upload audio": "上传音频失败",
  "Failed to update audio": "更新音频失败",
  "Failed to extract melody MIDI": "提取旋律 MIDI 失败",
  "Failed to analyze reference audio": "参考音频分析失败",
  "Failed to apply reference analysis": "应用参考分析失败",
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
  pending: "待选择",
  selected: "已选择",
  ready: "就绪",
  available: "可用",
  processing: "处理中",
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
  "Song structure": "歌曲结构",
  "Based on approved SongSpec v{version}": "基于已确认的 SongSpec v{version}",
  "Approve a SongSpec to edit its timeline.": "请先确认 SongSpec，再编辑段落时间线。",
  "Local draft restored": "已恢复本地草稿",
  Undo: "撤销",
  Redo: "重做",
  "Chord positions must fit within their measure.": "和弦拍点和时值必须位于对应小节内。",
  "Chord events must not overlap.": "和弦事件不能重叠。",
  "Section {number}": "第 {number} 段",
  "Move up": "上移",
  "Move down": "下移",
  "Duplicate section": "复制段落",
  "Delete section": "删除段落",
  "{label} copy": "{label} 副本",
  "New section": "新段落",
  "Add section": "添加段落",
  "Preview impact": "预览影响",
  "Apply and create versions": "应用并创建新版本",
  "No approved structure is available.": "当前没有已确认的歌曲结构。",
  "Change impact": "变更影响",
  "{count} assets affected": "影响 {count} 项资产",
  "{count} added": "新增 {count}",
  "{count} removed": "删除 {count}",
  "{count} renamed": "重命名 {count}",
  Reordered: "已调整顺序",
  "New version": "创建新版本",
  Regenerate: "重新生成",
  "At least one song section is required.": "至少需要一个歌曲段落。",
  "Section labels must not be empty.": "段落名称不能为空。",
  "Section IDs must be unique.": "段落 ID 必须唯一。",
  "Failed to update song structure": "更新歌曲结构失败",
  "Existing MIDI files keep their history but must be regenerated.":
    "现有 MIDI 会保留在历史中，但需要重新生成。",
  "Existing demos remain playable but no longer match the current structure.":
    "现有 Demo 仍可播放，但已不再匹配当前歌曲结构。",
  midi_chord: "和弦 MIDI",
  midi_melody: "旋律 MIDI",
  midi_hook: "Hook MIDI",
  structure: "歌曲结构",
  None: "无",
  missing: "缺失",
} as const;

export type TranslationKey = keyof typeof zhCN;

export function isLocale(value: string | undefined): value is Locale {
  return value === "en" || value === "zh-CN";
}

export function isTheme(value: string | undefined): value is Theme {
  return value === "light" || value === "dark";
}

/** Resolve the initial theme from a cookie (or DOM-applied) value, falling
 * back to the caller-provided value (e.g. the first-paint DOM theme), then
 * the default. */
export function resolveInitialTheme(
  value: string | undefined,
  fallback: Theme = DEFAULT_THEME,
): Theme {
  return isTheme(value) ? value : fallback;
}

export function toggleThemeValue(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark";
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
  if (
    typeof error === "object" &&
    error !== null &&
    "errorCode" in error &&
    typeof (error as { errorCode: unknown }).errorCode === "string"
  ) {
    const code = (error as { errorCode: string }).errorCode;
    return errorCodeMessage(code, locale) ?? translate(locale, fallback);
  }
  if (locale === "en" && error instanceof Error) {
    return error.message;
  }
  const base = translate(locale, fallback);
  if (typeof error !== "object" || error === null) {
    return base;
  }
  const status =
    "status" in error && typeof error.status === "number"
      ? ` (${error.status})`
      : "";
  const requestId =
    "requestId" in error && typeof error.requestId === "string"
      ? ` - ${translate(locale, "Request ID: {id}", { id: error.requestId })}`
      : "";
  return `${base}${status}${requestId}`;
}

export function formatLocalizedHint(
  locale: Locale,
  error: unknown,
): string | null {
  if (
    typeof error === "object" &&
    error !== null &&
    "hint" in error &&
    typeof (error as { hint: unknown }).hint === "string"
  ) {
    return hintActionMessage((error as { hint: string }).hint, locale);
  }
  return null;
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
  structure: "歌曲结构",
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
  const unusedPreferredTerms = /^Preferred vocabulary not used: (.+)$/.exec(value);
  if (unusedPreferredTerms) {
    return `未使用偏好词汇：${unusedPreferredTerms[1]}`;
  }

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

// ─── error_code / hint resolution (phase 1) ────────────────────────────────

const ERROR_CODE_EN: Record<string, string> = {
  resource_not_found: "Resource not found",
  song_spec_not_approved: "SongSpec must be approved first",
  prerequisites_missing: "Required assets are missing",
  asset_version_conflict: "Concurrent edit detected — retry",
  upload_too_large: "File exceeds 25 MB limit",
  unsupported_media_type: "Unsupported audio format",
  validation_failed: "Validation failed",
  chord_theory_error: "Invalid chord input",
  song_spec_incomplete: "SongSpec has missing fields",
  internal_error: "Unexpected server error",
  song_structure_change_requires_preview: "Song structure changes require an impact preview",
  provider_unavailable: "Demo provider is unavailable",
};

const ERROR_CODE_ZH: Record<string, string> = {
  resource_not_found: "未找到资源",
  song_spec_not_approved: "请先确认 SongSpec",
  prerequisites_missing: "所需资产缺失",
  asset_version_conflict: "检测到并发编辑，请重试",
  upload_too_large: "文件超过 25 MB 限制",
  unsupported_media_type: "不支持的音频格式",
  validation_failed: "校验失败",
  chord_theory_error: "和弦输入无效",
  song_spec_incomplete: "SongSpec 字段不全",
  internal_error: "服务器内部错误",
  song_structure_change_requires_preview: "歌曲结构变更需要先预览影响范围",
  provider_unavailable: "Demo provider 不可用",
};

const HINT_EN: Record<string, string> = {
  retry: "Retry",
  approve_song_spec: "Approve SongSpec",
  check_prerequisites: "Generate missing assets first",
  trim_audio_under_25mb: "Use a file under 25 MB",
  check_format: "Use WAV format",
  check_required_fields: "Fill in required fields",
  check_chord_symbol: "Check chord symbol or timing",
  contact_support: "Contact support",
  use_structure_editor: "Open Song Structure editor",
};

const HINT_ZH: Record<string, string> = {
  retry: "重试",
  approve_song_spec: "去确认 SongSpec",
  check_prerequisites: "先生成缺失的资产",
  trim_audio_under_25mb: "使用 25 MB 以内的文件",
  check_format: "使用 WAV 格式",
  check_required_fields: "填写必填字段",
  check_chord_symbol: "检查和弦符号或节拍",
  contact_support: "联系支持",
  use_structure_editor: "打开歌曲结构编辑器",
};

export function errorCodeMessage(
  code: string | null | undefined,
  locale: Locale,
): string | null {
  if (!code) return null;
  return locale === "zh-CN"
    ? (ERROR_CODE_ZH[code] ?? code)
    : (ERROR_CODE_EN[code] ?? code);
}

export function hintActionMessage(
  hint: string | null | undefined,
  locale: Locale,
): string | null {
  if (!hint) return null;
  return locale === "zh-CN"
    ? (HINT_ZH[hint] ?? hint)
    : (HINT_EN[hint] ?? hint);
}
