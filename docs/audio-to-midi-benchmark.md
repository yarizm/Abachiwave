# Audio-to-MIDI 质量基准

本文定义 Basic Pitch 和兼容 Provider 的离线质量、时延与资源验收口径。基准直接调用隔离推理
服务，不经过项目 API、队列或 MinIO；应用级状态机和故障恢复由
`support/validate_basic_pitch_faults.py` 单独验证。

## 1. 数据集要求

每个样例必须包含：

- 一个可由 Provider 读取的 WAV；正式数据集应先统一为与产品派生链一致的 48 kHz、双声道、
  16-bit PCM WAV；
- 一个与音频时间轴对齐、包含完整 note-on/note-off 的参考 MIDI；
- 稳定、唯一的样例 ID；
- 分类标签，正式验收至少应分别覆盖单旋律乐器、人声和复调素材；
- 数据集名称、版本、许可证、许可证 URL 和来源 URL；
- 标准化音频与参考 MIDI 的 SHA-256；转换型数据集还应记录归档 member 和原始音频 SHA-256。

音频或 MIDI 文件可以放在仓库外。manifest 中的相对路径以 manifest 所在目录为基准。禁止把
来源不明、不可重新分发或含敏感内容的评测音频提交进仓库。

## 2. Manifest

```json
{
  "schema_version": 1,
  "dataset": {
    "name": "licensed-evaluation-set",
    "version": "2026-08-09",
    "license": "dataset license identifier",
    "license_url": "https://example.test/dataset-license",
    "source_url": "https://example.test/dataset",
    "reference_policy": "How note onset, pitch, velocity and offset were established.",
    "source_archive_etag": "immutable-source-version",
    "source_artifact_checksums": {
      "audio.zip": "md5:275966d6610ac34999b58426beb119c3"
    },
    "synthetic": false
  },
  "onset_tolerance_seconds": 0.05,
  "offset_tolerance_seconds": 0.05,
  "offset_tolerance_ratio": 0.2,
  "reference_selection_policy": "best_onset_pitch_offset_f1",
  "provider_params": {
    "onset_threshold": 0.5,
    "frame_threshold": 0.3
  },
  "samples": [
    {
      "id": "voice-001",
      "category": "vocal",
      "audio_path": "audio/voice-001.wav",
      "reference_id": "annotator_1",
      "reference_midi_path": "midi/voice-001.mid",
      "audio_sha256": "2ff4dca5905df3d44c08f68b0128277319c3b20ddd701a36ac81205ee464a433",
      "reference_midi_sha256": "297aa16a4f25bcca345dd20fae9ea658abac85939d6fc98ddb4349d772e21abf",
      "source_member": "dataset/audio/voice-001.wav",
      "source_audio_sha256": "6f235fa3ce42c6940e69ccf2f17f85e3187e359b004638524e97d3246e91892c",
      "source_annotation_member": "dataset/annotation/voice-001.json",
      "source_annotation_sha256": "ba56a15060a2d6b83199ef2ee07cdeec81f4e436615abb07010df9c5f78604e9",
      "alternative_references": [
        {
          "id": "annotator_2",
          "midi_path": "midi/voice-001-a2.mid",
          "midi_sha256": "6923ead14fc1b9fad13039b96032fc9f0c0bead7de187af87392c4235a44a1f8",
          "source_annotation_member": "dataset/annotation/voice-001-a2.json",
          "source_annotation_sha256": "31ef06d39ed934a388232957043368cba6d35ddeb231d7d47bf50f32b8db8d0c"
        }
      ],
      "attributes": {
        "language": "English",
        "singer_id": "S1"
      }
    }
  ],
  "thresholds": {
    "overall": {
      "onset_pitch_f1_min": 0.0,
      "onset_pitch_offset_f1_min": 0.0,
      "macro_onset_pitch_f1_min": 0.0,
      "macro_onset_pitch_offset_f1_min": 0.0,
      "mean_onset_mae_ms_max": 1000,
      "mean_duration_mae_ms_max": 1000,
      "mean_velocity_mae_max": 127,
      "mean_onset_aligned_pitch_mae_semitones_max": 12,
      "empty_result_rate_max": 1,
      "median_real_time_factor_max": 10,
      "p95_latency_seconds_max": 300,
      "peak_cpu_percent_max": 800,
      "peak_memory_mib_max": 4096
    },
    "vocal": {
      "onset_pitch_f1_min": 0.0
    }
  }
}
```

示例中的数值只展示 schema，不是产品放行标准。正式阈值必须由固定版本真实数据集的基线结果、
失败样例复核和目标部署机器容量共同决定；阈值一旦用于发布门禁，必须随 manifest 版本化。
容器 CPU/内存阈值只能写在 `overall` scope。

加载 manifest 时会重新计算音频和 MIDI 的 SHA-256；文件缺失、内容漂移或真实数据集缺少
`license_url` / `source_url` 都会在调用 Provider 前失败。

默认 `reference_selection_policy` 为 `primary`。多位标注者都被视为有效参考时，可设置
`best_onset_pitch_offset_f1`：每个样本分别计算所有参考，先按 onset+pitch+offset F1、再按
onset+pitch F1 选择最佳参考，并用该参考计算其余指标；报告保留被选中的 `reference_id`。

## 3. 指标

- `onset_pitch_*`：音高相同且起音误差不超过 onset tolerance 的 micro precision/recall/F1。
- `onset_pitch_offset_*`：在上项基础上，止音误差还需小于固定 offset tolerance 与参考音符
  时长比例容差两者中的较大值。
- `macro_onset_pitch_f1`、`macro_onset_pitch_offset_f1`：先逐样本计算 F1 再取等权平均，适合与
  按曲报告的论文基线比较；不等同于汇总所有音符计数得到的 micro F1。
- `mean_onset_mae_ms`：onset+pitch 匹配音符的平均起音绝对误差。
- `mean_duration_mae_ms`：onset+pitch 匹配音符的平均时长绝对误差。
- `mean_velocity_mae`：onset+pitch 匹配音符的 MIDI velocity 平均绝对误差。
- `mean_onset_aligned_pitch_mae_semitones`：只按起音匹配后计算的半音平均绝对误差，用于暴露
  八度或音高识别错误；复调同起音会优先选择音高误差最小的一一配对。
- `empty_result_rate`：返回零个完整音符的样例比例。
- `median_real_time_factor`：推理耗时除以音频时长，小于 1 表示快于实时。
- `p95_latency_seconds`：单样例推理延迟的线性插值 P95。
- `peak_memory_mib`、`peak_cpu_percent`：轮询 `docker stats --no-stream` 观察到的容器峰值。
  采样器在 benchmark 结束时等待当前采样完成；若仍没有有效 CPU 数值，CPU 保持 `null`，设置
  CPU 阈值会明确失败，不得把缺失值当作 0。

MIDI 解析按 tempo change 积分为绝对秒时间，不假设整份文件使用固定 BPM。聚合质量指标采用
micro 计数，分类结果按 manifest 的 category 单独输出。

## 4. 执行

先启动 Basic Pitch：

```bash
docker compose --profile basic-pitch up -d basic-pitch
curl http://localhost:8010/health/ready
```

运行真实数据集：

```bash
uv run python support/benchmark_audio_to_midi.py path/to/manifest.json \
  --output path/to/report.json
```

临时覆盖参数或只运行指定样本时使用可重复选项；未知参数、重复参数和不存在的样本 ID 会明确失败：

```bash
uv run python support/benchmark_audio_to_midi.py path/to/manifest.json \
  --provider-param onset_threshold=0.60 \
  --provider-param melodia_trick=true \
  --sample-id sample-001 \
  --output path/to/report.json
```

默认先执行一次不计入结果的 warm-up，并自动发现 Compose 中运行的 Basic Pitch 容器。资源采样
使用兼容 Windows Docker Desktop 的轮询快照，不依赖可能被 CLI 缓冲的无限流输出。可用
`--warmup-runs 0` 测量未预热调用，用 `--container` 指定其他容器。只有在无法使用 Docker 时才用
`--no-resource-sampling`；若 manifest 包含资源阈值，缺少采样会明确失败。

退出码：

- `0`：所有阈值通过；
- `1`：manifest、输入、服务或执行错误；
- `2`：基准完成，但至少一个质量或容量阈值失败。

## 5. 合成 smoke

以下命令生成三组正弦波/MIDI 真值，并验证完整评测管线：

```bash
uv run python support/create_audio_to_midi_smoke_dataset.py path/to/temp-dataset
uv run python support/benchmark_audio_to_midi.py \
  path/to/temp-dataset/manifest.json \
  --output path/to/temp-dataset/report.json
```

合成 smoke 用于验证 MIDI 秒级解析、音符匹配、阈值、HTTP 推理和资源采样。即使所有指标为
100%，也不能代表人声、真实乐器、混响、噪声或复调音乐上的产品质量。

## 6. NSynth 真实单音基线

[NSynth 官方数据集](https://magenta.tensorflow.org/datasets/nsynth)使用 CC BY 4.0，提供带 pitch、
velocity 标签的 4 秒单音 WAV；音符在前 3 秒保持，最后 1 秒释放。仓库不保存数据集音频，下面的
采集器通过 HTTPS 流式读取官方 test archive，校验固定 ETag，只保存 7 个 acoustic 家族各 2 个
独立音高，并输出 48 kHz WAV、参考 MIDI 和逐文件 checksum：

```bash
uv run python support/fetch_nsynth_benchmark_subset.py path/to/nsynth-subset
uv run python support/benchmark_audio_to_midi.py \
  path/to/nsynth-subset/manifest.json \
  --output path/to/nsynth-subset/report.json
```

2026-08-09 在本地 Docker CPU 环境运行 Basic Pitch 0.4.0 的首次观察基线如下。manifest 暂未设置
质量阈值，因此报告中的 `passed: true` 只表示执行完成且没有阈值违规，不表示产品质量通过。

| Scope | 参考/预测音符 | onset+pitch F1 | onset+pitch+offset F1 | 空结果率 |
| --- | ---: | ---: | ---: | ---: |
| overall | 14 / 48 | 0.452 | 0.065 | 0% |
| monophonic_instrumental | 12 / 35 | 0.511 | 0.085 | 0% |
| vocal | 2 / 13 | 0.267 | 0.000 | 0% |

总体起音 MAE 为 27.9 ms，中位热推理时延 201 ms、P95 272 ms、RTF 0.050、容器峰值 CPU
261.73%、内存 716.3 MiB。所有参考音高均被命中，
但 14 个参考音产生了 48 个预测音，主要风险是持续音、泛音和音色变化导致的额外音符/过分段。

这组数据是 sample-library 的 isolated held notes，不是乐句、人声演唱段或复调音乐。3 秒 offset 来自
数据集生成约定，不是人工逐帧标注的声学终点，不能单独用来给产品设 offset 发布阈值。下一轮正式
门禁仍需补充可许可的乐句级单旋律、人声和复调对齐集，并人工复核失败样例。

## 7. GuitarSet 真实乐句基线

[GuitarSet 1.1.0 官方 Zenodo 记录](https://zenodo.org/records/3371780)以 CC BY 4.0 发布真实
木吉他录音和逐弦 JAMS `note_midi` 标注。采集器先核对 Zenodo record ID、版本、许可证、文件大小
和官方 MD5，再通过 HTTPS Range 只读取目标 ZIP member；默认选择两个 solo 与两个 comp 乐句，
并排除官方仓库 issues 4/5 记录的三个已知错误标注：

```bash
uv run python support/fetch_guitarset_benchmark_subset.py path/to/guitarset-subset
uv run python support/benchmark_audio_to_midi.py \
  path/to/guitarset-subset/manifest.json \
  --output path/to/guitarset-subset/report.json
```

2026-08-09 在本地 Docker CPU 环境运行 Basic Pitch 0.4.0 的观察基线：

| Scope | 参考/预测音符 | onset+pitch F1 | onset+pitch+offset F1 | 空结果率 |
| --- | ---: | ---: | ---: | ---: |
| overall | 785 / 772 | 0.744 | 0.444 | 0% |
| monophonic_instrumental_phrase | 150 / 155 | 0.866 | 0.708 | 0% |
| polyphonic_instrumental_phrase | 635 / 617 | 0.714 | 0.380 | 0% |

总体起音 MAE 12.4 ms、时长 MAE 111.9 ms，中位热推理 662 ms、P95 851 ms、RTF 0.022；
容器峰值 CPU 385.94%、内存 720.6 MiB。solo 的音高/起音明显优于 comp，复调主要损失集中在
漏音、和弦音高分配与止音。JAMS 没有逐音符 velocity，参考 MIDI 固定写入 100，因此该数据集的
velocity MAE 只能作为诊断输出，不能设置发布阈值。

2026-08-22 在同一子集上复现了上述 baseline（785/772、0.744/0.444、solo 0.866/0.708、
comp 0.714/0.380 全部一致），并追加 `onset_threshold=0.60` 的退化验证：

| Scope | baseline no-offset/offset F1 | onset 0.60 no-offset/offset F1 | Δ offset |
| --- | ---: | ---: | ---: |
| overall | 0.744 / 0.444 | 0.767 / 0.474 | +0.030 |
| monophonic_instrumental_phrase | 0.866 / 0.708 | 0.874 / 0.728 | +0.020 |
| polyphonic_instrumental_phrase | 0.714 / 0.380 | 0.739 / 0.409 | +0.029 |

三个类别均无退化，复调也在内。预测音符从 772 降到 699、overall recall 从 0.738 降到 0.725，
但 precision 的增益更大。起音 MAE 持平（12.4 ms），时长 MAE 从 111.9 ms 改善到 100.2 ms，
中位时延 725→708 ms、P95 1035→831 ms、峰值 CPU 447%→421%、峰值内存 763→771 MiB。
该参数在 Vocadito 上按歌手隔离选出，GuitarSet 未参与选参，因此这是一次跨数据集、跨乐器的
独立确认。

该子集已补足真实乐句级单旋律和复调乐器观察证据，但只有四条吉他 excerpt，仍不足以直接设置
通用产品门禁；报告 `passed: true` 同样只表示未配置阈值。正式阈值还需扩大演奏者/风格覆盖，
并补充真实演唱乐句与其他乐器。

## 8. Vocadito 真实演唱基线

[Vocadito 官方 Zenodo 记录](https://zenodo.org/records/5557945)以 CC BY 4.0 发布 40 条真实
单声部演唱，覆盖 29 位歌者和 7 种语言；每条音频都有两位音乐家独立创建的音符标注。采集器完整
读取 58.5 MB ZIP 到内存并实际校验官方 MD5，不把 ZIP 或第三方音频写入仓库；随后输出生产格式
WAV、A1/A2 两份 MIDI 和逐 member SHA-256：

```bash
uv run python support/fetch_vocadito_benchmark_dataset.py path/to/vocadito
uv run python support/evaluate_audio_to_midi_reference_agreement.py \
  path/to/vocadito/manifest.json \
  --output path/to/vocadito/reference-agreement.json
uv run python support/benchmark_audio_to_midi.py \
  path/to/vocadito/manifest.json \
  --output path/to/vocadito/report.json
```

manifest 使用 `best_onset_pitch_offset_f1` 实现论文建议的 A_max：本次 Basic Pitch 预测中 A2 被选中
26 条、A1 被选中 14 条。相同 evaluator 下，两位人类标注者的 macro no-offset/offset F1 为
0.722/0.633，与论文约 0.74/0.64 的结论接近，说明 Hz→MIDI 与容差实现没有制造虚假低分。

Basic Pitch 0.4.0 全集观察结果：

| 样本/参考/预测音符 | micro no-offset/offset F1 | macro no-offset/offset F1 | 空结果率 |
| ---: | ---: | ---: | ---: |
| 40 / 2028 / 2072 | 0.508 / 0.332 | 0.519 / 0.347 | 0% |

总体起音 MAE 16.0 ms、时长 MAE 88.1 ms、中位热推理 522 ms、P95 828 ms、RTF 0.026；
容器峰值 CPU 442.44%、内存 738.9 MiB。中等音域组的 macro no-offset/offset F1 为
0.567/0.400，高低音域约为 0.48–0.49/0.30–0.32，但各语言、歌者与音域样本量不均，当前只作为
失败复核线索，不能推导语言或声部优劣。

Vocadito 论文报告的人类一致性约 0.74/0.64，既有 Vocano A_max 约 0.64/0.50；当前 Basic Pitch
macro 0.519/0.347 明显低于两者，证明真实演唱转录尚未达到适合作为产品发布门禁的质量。velocity
未被标注，固定值 100 只为生成合法 MIDI，不能用于阈值。报告中的 `passed: true` 仍仅表示 manifest
没有配置正式阈值。

## 9. Basic Pitch 参数扫描

参数扫描必须把模型选择和最终验证分开。Vocadito 使用稳定 seed 按 `singer_id` 分组：30 条开发
样本来自 22 位歌者，10 条留出样本来自另外 7 位歌者；同一歌者不会跨分区。候选只按开发集
`macro_onset_pitch_offset_f1` 排序，随后才对 baseline 与入选候选运行留出集。

第一轮单参数扫描：

```bash
uv run python -m support.sweep_basic_pitch_parameters \
  path/to/vocadito/manifest.json \
  --definition support/basic_pitch_vocadito_sweep.json \
  --output path/to/vocadito/basic-pitch-sweep-v1.json
```

围绕 onset threshold 的细化扫描：

```bash
uv run python -m support.sweep_basic_pitch_parameters \
  path/to/vocadito/manifest.json \
  --definition support/basic_pitch_vocadito_refinement.json \
  --output path/to/vocadito/basic-pitch-sweep-refinement.json
```

2026-08-22 已完成 14 个候选的完整细化扫描。数据集 manifest sha256 `a3f3e9fb…`，扫描定义 sha256
`c998dd3f…`，Provider 为 Basic Pitch 0.4.0 / TensorFlow sidecar。baseline、`onset 0.60`、`onset 0.75`
的开发集结果与 2026-08-09 完全一致，baseline 留出集同样一致，因此两轮可直接比较。

开发集按 `macro_onset_pitch_offset_f1` 排名前六：

| 候选 | 开发 macro no-offset/offset F1 |
| --- | ---: |
| onset 0.80 | 0.584 / 0.428 |
| onset 0.75 | 0.584 / 0.424 |
| onset 0.85 | 0.578 / 0.422 |
| onset 0.70 | 0.577 / 0.414 |
| onset 0.90 | 0.544 / 0.402 |
| onset 0.65 | 0.566 / 0.399 |

开发集在 `onset 0.80` 见顶后单调下降。4 个 `onset/frame` 组合候选全部低于同 onset 的纯阈值候选，
`frame_threshold` 方向不再保留为调参维度。

留出集结果与开发集排名相反：

| 候选 | 开发 offset F1 | 留出 macro no-offset/offset F1 | 留出 offset 相对默认值 |
| --- | ---: | ---: | ---: |
| 默认参数 | 0.341 | 0.539 / 0.363 | — |
| onset 0.60 | 0.394 | 0.572 / 0.410 | +0.047 |
| onset 0.75 | 0.424 | 0.555 / 0.408 | +0.045 |
| onset 0.80 | 0.428 | 0.535 / 0.381 | +0.018 |

`onset 0.60` 与 `onset 0.75` 的留出值来自 2026-08-09；本轮按设计只对 baseline 与开发集冠军运行
留出集。

开发集冠军 `onset 0.80` 的留出增益 +0.018 低于 `minimum_macro_f1_improvement` 阈值 0.02，也低于
`onset 0.60` 的 +0.047：**开发集排名在尾部与留出集泛化反相关**，这正是“开发集最高分不能单独成为
默认参数”规则要拦截的情况。沿曲线 precision 从 0.491 升到 0.694，recall 从 0.507 降到 0.443，预测
音符数从 1610 降到 1030（参考 1557），说明剩余差距来自漏音而非阈值位置。

结论：onset threshold 的调参空间已经探完，`onset 0.60` 是当前最稳健候选，但其留出 offset F1 0.410
距 0.50 观察目标仍差 0.09。工具输出 `recommendation:
parameter_tuning_improves_quality_but_model_gap_remains`，
`selected_candidate_meets_targets_on_holdout: false`。GuitarSet 退化证据已于 2026-08-22 补齐（见
第 7 节）：`onset 0.60` 在 overall、solo 和 comp 三个类别上均优于默认值，无退化，因此可以作为默认
参数固化。这不改变模型差距的结论——换 Provider 的同口径比较现已具备完整的 Basic Pitch 基线。

扫描工具为每个候选保存独立报告。使用 `--reuse-existing` 时，只有有效参数和有序样本 ID 与当前
候选完全一致的报告才会复用。第三方音频和临时报告不得提交到仓库。

`support/basic_pitch_vocadito_sweep.json` 与 `support/basic_pitch_vocadito_refinement.json` 是针对
`onset_threshold` 默认值仍为 0.5 时写下的历史定义，其 sha256 已记录在对应报告中，因此不再修改。
默认值改为 0.6 后，这两份定义里的 `baseline` 与 `onset-0.60` 有效参数相同，直接重跑会触发
"unique effective parameters" 校验失败——这是工具在正确提示定义已过期。需要重跑时应新建定义，
不要改写历史文件。

## 10. 止音误差分解

`onset+pitch+offset F1` 永远不高于 `onset+pitch F1`，两者之差就是"一个完美止音层"能够收回的上限。
本工具测量这个上限，并给出它背后的**有符号**时长误差分布，同时网格搜索两种廉价的全局后处理
（时长缩放、时长平移）——只有当误差存在系统性偏置时，这类后处理才可能奏效：

```bash
uv run python -m support.analyze_audio_to_midi_offsets   path/to/vocadito/manifest.json   --output path/to/vocadito/offset-analysis.json
```

工具沿用参数扫描的同一 `singer_id` 分组切分，因此变换可以在开发组上挑选、在留出组上确认，而不是
在同一批样本上既拟合又验收。

2026-08-23 在 Vocadito 上以固化后的默认参数（`onset_threshold=0.60`）运行。`identity` 在两个分区
分别复现出 0.557/0.394 与 0.572/0.410，与第 9 节记录一致：

| 分区 | no-offset F1（完美止音层上限） | offset F1 | 止音缺口 |
| --- | ---: | ---: | ---: |
| development | 0.557 | 0.394 | 0.163 |
| holdout | 0.572 | 0.410 | 0.163 |

**缺口足够大**：留出集补满 0.163 即可从 0.410 到 0.572，越过 0.50 观察目标。但误差结构决定了它
收不回来：

| 分区 | 匹配音符对 | 有符号时长误差中位数 | p10 / p90 | 时长比中位数 | 越界中"偏长"占比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| development | 808 | +4.4 ms | −134 / +87 ms | 1.0155 | 0.544 |
| holdout | 254 | +0.1 ms | −146 / +87 ms | 1.0005 | 0.506 |

时长误差中位数接近 0、预测/参考时长比中位数接近 1、越界样本在"偏长"和"偏短"之间几乎五五开——
这是**无偏对称散布**的特征，不是可以整体平移或缩放掉的偏置。网格搜索证实了这一点：

| 分区 | 最优变换 | Δ macro offset F1 |
| --- | --- | ---: |
| development | 时长缩放 0.95 | +0.009 |
| holdout | 时长缩放 0.95 | +0.002 |

任何强到有意义的变换都会让指标下降（留出集：缩放 0.80 −0.081、平移 −60 ms −0.145）。

结论：止音缺口真实存在且是模型差距的主要可量化组成部分，但收回它需要逐音符的声学证据，
不是后处理能提供的。作为对照，两位人类标注者在同一 evaluator 下的止音缺口是
0.722−0.633 = 0.089（全集 40 条，与留出分区不同口径），Basic Pitch 是 0.163。这条线索到此关闭，
第 1.1 节的替代 Provider 比较是唯一剩余路径；新 Provider 的评估应同时报告 no-offset 上限与止音
缺口，以区分"漏音/错音"改善与"止音"改善。

注意时长 MAE（Vocadito 88.1 ms、GuitarSet 100–112 ms）之所以大，是散布宽，不是存在可移除的偏置；
绝对值均值无法区分这两种情况，这正是 `collect_note_timing_errors` 返回有符号误差的原因。

## 11. 召回缺口分解与被否候选

第 10 节关闭了止音后处理。同一批缓存预测还能回答一个更重要的问题：**剩下的缺口到底是什么**。
`analyze_audio_to_midi_offsets` 会把召回损失按"没检测到"和"欠切分"分开——两者需要的修复完全不同，
用 recall 一个数字无法区分：

| 分区 | 起音召回 | 未匹配参考音符 | 被同音高预测音覆盖（合并） | 被异音高覆盖 | 完全未覆盖 |
| --- | ---: | ---: | ---: | ---: | ---: |
| development | 0.599 | 611 / 1524 | 276（45.2%） | 73 | 262（42.9%） |
| holdout | 0.581 | 198 / 472 | 86（43.4%） | 25 | 87（43.9%） |

两个分区一致：约 42% 的参考音符**根本没有对应起音**，其中近一半是被一个同音高长音符盖住的
**欠切分**，而不是漏检。起音召回 0.58–0.60 是当前的约束条件，止音缺口 0.163 只是次要项。

### 11.1 已排除的后处理族

在 Vocadito 上用同一评测口径测过四族纯后处理，全部无效：

| 后处理 | 留出集 Δ macro offset F1 |
| --- | ---: |
| 时长缩放 / 平移（第 10 节） | +0.002 |
| 单声部重叠消解（keep_longest / keep_loudest / truncate） | −0.006 / −0.003 / −0.004 |
| 用 pYIN f0 重新指派每个音符的音高 | +0.002（开发集，重指派了 1442 中的 164 个） |
| 用 pYIN f0 在 Basic Pitch 音符内部再切分 | 最佳 −0.000；1 半音阈值多切出 487 个音符但 −0.077 |

Basic Pitch 的音高在起音对齐后基本正确，重指派几乎不改变分数；欠切分的那批音符其内部
f0 变化也不足以支撑正确切点。**Basic Pitch 的输出没有可用后处理挖掘的余量。**

### 11.2 被否候选：pYIN + 音符分割

Vocadito 论文报告的 Vocano 基线约 0.64/0.50 正好压线达标，且属于"f0 追踪 + 音符分割"的单声部
专用管线，因此先用最便宜的 pYIN 版本验证这个方向（16 kHz、10 ms hop、`fmin/fmax` 与 Basic Pitch
默认一致，分割参数在开发集上做了 320 组网格）：

| 系统 | 开发集 macro no-offset / offset F1 |
| --- | ---: |
| Basic Pitch 0.4.0（`onset 0.60`） | 0.557 / 0.394 |
| pYIN + 分割（未调参） | 0.447 / 0.281 |
| pYIN + 分割（开发集最优） | 0.467 / 0.332 |

调到头仍落后 0.090 / 0.062，音符总数却是对的（1666 预测 vs 1630 参考），说明不是过分割或欠分割
的量级问题。用 oracle 边界进一步定位：把参考音符的时间跨度当作已知，只用 pYIN 在该跨度内取中位数
定音高，音高准确率 79.3%，99.1% 的参考音符内至少有一个有声帧，F1 达到 0.814/0.811（该数字用
标注者 1 的边界再经 A_max 选参考，偏乐观，只作定位用途）。

**结论：f0 质量不是瓶颈，音符分割才是。** 因此换一个 f0 估计器（CREPE 等）不解决问题；单声部
专用路线需要的是一个**学习到的音符切分模型**，不是更好的音高曲线。该原型在 `uv run --with librosa`
的临时环境中运行，候选被否决后未并入依赖，仓库中不保留其代码。

### 11.3 对替代 Provider 的要求

替代候选必须在**演唱素材的音符事件切分**上有改善，而不是音高或止音：

1. 报告起音召回，以及未匹配参考音符中"欠切分/未检测/异音高覆盖"的构成。
2. 报告 no-offset 上限与止音缺口（Basic Pitch 0.163，人工标注者之间 0.089）。
3. 单声部与复调分别报告；单声部专用模型在 GuitarSet comp 上退化是预期内的，需要显式路由决策。

## 12. 替代 Provider 比较：YourMT3+

### 12.1 候选筛选

只有一个候选同时满足"权重可得 + 许可清晰 + CPU 可跑"：

| 候选 | 判定 | 依据 |
| --- | --- | --- |
| **YourMT3+**（YPTF.MoE+Multi noPS） | 采用 | Apache-2.0，45.8M 参数，`mt3-infer` 已 vendored 模型代码，`device="cpu"` |
| ROSVOT | 否 | 钉死 PyTorch 2.1.1+CUDA 11.8 / TF 2.9 / Py3.9，README 自承依赖易冲突；仅 M4Singer 训练 |
| Mel-RoFormer | 否 | 公开权重是人声**分离**模型，转录头未发布，权重无许可声明 |
| MusicMamba / VocalParse | 否 | 无可部署产物；Mamba 需 CUDA kernel，VocalParse 是音频 LLM |
| VOCANO | 否 | 无可用发布，只能作为 Vocadito 论文里的参照数字 |

权重 536 MB（`561544628` 字节）来自作者的 HF Space，sha256
`ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25`，本地独立校验通过。
`mt3-infer` 记录该哈希但**下载时不校验**，集成时必须自行验证。

环境约束：`mt3-infer` 声明 `transformers>=4.35.0` 无上界，但 vendored 的 YourMT3 代码在
transformers 5.x 缺 `model_parallel_utils`、在 4.57 因 T5 attention 需要 `cache_position` 而崩溃。
上游 Space 钉的是 `transformers==4.45.1`，必须照此固定。

### 12.2 Vocadito 结果（有效留出证据）

Vocadito **不在** YourMT3 的训练混合中（歌声部分只用 `mir_st500_voc`），因此以下数字是真实泛化结果。
分区沿用第 9 节的 `singer_id` 隔离切分。

留出集（10 条 / 7 位歌者）：

| 系统 | 起音召回 | no-offset F1 | offset F1 |
| --- | ---: | ---: | ---: |
| Basic Pitch 0.4.0（`onset 0.60`） | 0.581 | 0.572 | 0.410 |
| YourMT3 原样 | 0.783 | 0.558 | 0.357 |
| YourMT3 + pYIN 音高 | 0.783 | 0.625 | 0.386 |
| **YourMT3 + pYIN + 时长 ×0.85** | 0.772 | **0.623** | **0.441** |
| 人工标注者互评（全集 40 条） | — | 0.722 | 0.633 |

开发集（30 条 / 22 位歌者，用于选 `0.85`）：Basic Pitch 0.599 / 0.557 / 0.394，
组合方案 0.809 / 0.692 / 0.466。开发集曲线在 0.85 单峰、留出集在 0.88 单峰（0.445），
两者接近且平缓，未重现第 9 节那种开发/留出反相关。

留出集 offset F1 增益 **+0.031**，超过 `minimum_macro_f1_improvement` 阈值 0.02。

第 8 节引用的 Vocano 与人工一致性都是**全集 40 条**的数字，与留出集口径不同。为与已发表基线
同口径对照，全集结果如下（`0.85` 是在其中 30 条上选出的，因此该行部分在样本内；干净的样本外
数字仍以上表留出集为准）：

| 系统（同一 40 条） | no-offset F1 | offset F1 | 止音缺口 |
| --- | ---: | ---: | ---: |
| 人工标注者 A1 vs A2 | 0.722 | 0.633 | 0.089 |
| Vocano A_max（论文） | ~0.64 | ~0.50 | ~0.14 |
| **YourMT3 + pYIN + 时长 ×0.85** | **0.675** | **0.460** | 0.215 |
| Basic Pitch `onset 0.60` | 0.561 | 0.398 | 0.163 |
| Basic Pitch 默认参数 | 0.519 | 0.347 | 0.172 |

组合方案的 no-offset F1 已**超过** Vocano 的发表值，剩余差距全部落在止音：本方案止音缺口 0.215，
Vocano 约 0.14，人工标注者 0.089。因此 0.50 这个观察目标不是任意设定的门槛，它就是 Vocano 的
发表 offset F1；当前距其 0.04（全集）至 0.06（留出）。要越过它需要更好的音符边界，
Vocano 用的正是一个训练出来的音符切分网络。

### 12.3 为什么必须是三个部件

三者缺一不可，单独用 YourMT3 反而**劣于** Basic Pitch（留出 0.357 vs 0.410）：

1. **YourMT3 补音符检测。** 起音召回 0.581 → 0.783（+0.20），这是第 11 节确认的约束项。
2. **pYIN 补音高。** 起音对齐音符的音高准确率：Basic Pitch 87.6%（开发）/ 92.0%（留出），
   YourMT3 只有 70.3% / 70.8%。误差不是八度错误（±12 半音出现 **0** 次），也不是整轨调音偏移
   （40 条的 modal 偏差全部为 0），而是散在轨内、偏高为主（+1 半音占错误的 58–64%）。
   换用 pYIN 音高把留出 no-offset F1 从 0.558 抬到 0.625。
3. **时长缩放补止音（×0.85 是该族的上限）。** 与 Basic Pitch 不同，YourMT3 的时长误差是**有偏**的：
   有符号中位数 +39.6 ms（开发）/ +29.2 ms（留出），止音越界中偏长占 84.9% / 78.0%
   （Basic Pitch 对应为 +4.4/+0.1 ms、54.4%/50.6%，即无偏散布）。这正是第 10 节的方法
   在 Basic Pitch 上失败、在此处生效的原因——偏置存在时全局变换才有意义。
   残余结构确实存在（按参考时长分桶，理想缩放从短音 0.582 单调升到长音 0.980），但两参数形式
   `新时长 = 时长×k − c` 在开发集全面更差（最优 0.433 vs 纯缩放 0.466）：评测容差是
   `max(50 ms, 0.2×参考时长)`，短音受 50 ms 地板约束，加性项会把本来通过的中段音符过度压缩。
   全局时长修正在 ×0.85 处已探完。

### 12.4 部署成本

| 指标 | Basic Pitch 0.4.0 | YourMT3+ |
| --- | ---: | ---: |
| 中位 RTF | 0.023 | 0.824 |
| P95 RTF | — | 1.115 |
| 中位时延 | 0.44 s | 16.7 s |
| 进程峰值内存 | 720–770 MiB（容器） | 2205 MB |
| 模型加载 | — | 13.2 s |
| 权重体积 | 内置 | 536 MB + PyTorch CPU |

RTF 慢约 36 倍，内存约 3 倍，且 GuitarSet 复调片段最高到 RTF 1.698（慢于实时）。

### 12.5 已知缺陷与未决项

- **人声 program 不可用。** 干声独唱的输出音符落在 program 65（Alto Sax），GuitarSet 落在
  program 24；`SINGING_SOLO_CLASS` 定义的 program 100/101 在 40 条 Vocadito 中出现 **0** 次。
  集成时不能依赖 program 标签筛选人声。
- **GuitarSet 结果不可用作证据。** YourMT3 的训练混合包含 `guitarset_pshift`，官方切分是
  6 位演奏者中 4 位进训练集；本子集用的是演奏者 03 与 05，至少一位被训练过的概率约 93%。
  实测 overall 0.902/0.790、solo 0.904/0.810、comp 0.901/0.769 远高于 Basic Pitch，但这
  **很可能是训练集泄漏**，不能作为器乐类别的比较依据，也不足以支撑路由决策。器乐路由需要
  一个不在 MT3 训练混合中的数据集。
- **仍未达标。** 留出 offset F1 0.441 距 0.50 观察目标差 0.059，距人工标注者一致性 0.633 差 0.192。
- **第四部件已否。** 在 Basic Pitch 有邻近起音（±50 ms）的音符上改用它的音高、其余落回 pYIN：
  开发集 −0.015、留出集 +0.014，方向相反且均低于 0.02 阈值。按"开发集选参"规则否决，
  管线维持三部件。

### 12.6 组合方案是人声专用的，路由是必需项

pYIN 是单音 f0 追踪器，同一时刻只能给出一个音高，因此该组合在复调素材上按构造就会失效。
在 GuitarSet 上实测（同一音频的系统内对比，不受训练集泄漏影响——泄漏抬高的是 YourMT3 的
绝对分，不会制造 pYIN 的崩溃）：

| 类别 | YourMT3 原样 | + pYIN + 0.85 |
| --- | ---: | ---: |
| monophonic_instrumental_phrase | 0.904 / 0.810 | 0.854 / 0.707 |
| polyphonic_instrumental_phrase | 0.901 / 0.769 | **0.108 / 0.077** |

复调 offset F1 从 0.769 塌到 0.077。因此不存在"用组合方案统一替换默认 Provider"的选项：
必须按素材类型显式路由，且路由判据本身需要可靠依据——不能用输出的 MIDI program，因为
第 12.5 节已证明该标签不可用。人声路径与器乐路径的默认 Provider 必须分别记录在 run manifest 中。

现有代码已具备路由所需的全部信号，不需要新 schema：`AudioUploadKind` 的取值就是
`humming` / `reference` / `scratch` / `other`，由用户在上传时声明；`build_audio_to_midi_provider`
已接受 `provider_name` 覆盖；`upload` 在 `services/audio.py` 选择 Provider 的位置就在作用域内。
唯一缺口是 `input_manifest` 未记录 `audio_upload_kind`，而 lineage 要求它必须被记录。

本节的 YourMT3 原型运行在临时 venv（`transformers==4.45.1` + PyTorch CPU），权重存放在仓库外的
`MT3_CHECKPOINT_DIR`。候选尚未决策，因此推理侧代码与依赖都未并入仓库；重跑需按第 12.1 节
重建环境。

**评分侧是可复现的。** 任何无法与本项目共存的候选（依赖冲突、不同框架、权重不可再分发）都可以
把结果转录成 `<sample_id>.mid` 目录，再用同一 evaluator、同一容差与参考选择策略打分：

```bash
uv run python -m support.score_external_midi   path/to/vocadito/manifest.json   --midi-dir path/to/candidate-midi   --group-by partition   --candidate yourmt3-raw   --output path/to/candidate-report.json
```

目录内可选的 `index.json`（按 sample id 提供 `latency_seconds` 与 `audio_duration_seconds`）
会被用于时延与 RTF 统计；`--programs` 可只保留指定 MIDI program。该命令对本节的 YourMT3
输出复现出 development 0.594/0.351、holdout 0.558/0.357、overall 0.585/0.353，与上表一致。

## 13. 正式放行流程

1. 固定数据集版本、许可证、源归档与逐 member checksum 和分类覆盖。
2. 在目标 CPU/GPU 与容器资源限制下分别记录冷启动和预热基线。
3. 复核空结果、八度错误和长音频异常样例，再写入第一版真实阈值。
4. Provider、模型、参数、标准化格式或容器资源变化时创建新报告，不覆盖旧报告。
5. 只有真实数据集的 overall 与每个正式 category 都通过，才允许把质量结论写入路线图。
