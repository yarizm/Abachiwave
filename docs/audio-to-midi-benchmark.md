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

2026-08-09 已完成到 `onset_threshold=0.75` 的开发/留出结果：

| 候选 | 开发 macro no-offset/offset F1 | 留出 macro no-offset/offset F1 | 留出 offset 相对默认值 |
| --- | ---: | ---: | ---: |
| 默认参数 | 0.513 / 0.341 | 0.539 / 0.363 | — |
| onset 0.60 | 0.557 / 0.394 | 0.572 / 0.410 | +0.047 |
| onset 0.75 | 0.584 / 0.424 | 0.555 / 0.408 | +0.045 |

提高 onset threshold 的收益能够泛化到未参与选参的歌者，但 `0.75` 的开发集优势没有在留出集
继续扩大，不能仅因它在开发集排名第一就直接固化为默认。细化定义现已加入 `0.80～0.95` 候选，
尚未完成真实运行；跑完尾部曲线后仍需以开发/留出一致性、完整数据集和 GuitarSet 退化情况共同
决策。现有候选均未达到 0.64/0.50 观察目标，结论仍是“调参有效，但模型差距存在”。

扫描工具为每个候选保存独立报告。使用 `--reuse-existing` 时，只有有效参数和有序样本 ID 与当前
候选完全一致的报告才会复用。第三方音频和临时报告不得提交到仓库。

## 10. 正式放行流程

1. 固定数据集版本、许可证、源归档与逐 member checksum 和分类覆盖。
2. 在目标 CPU/GPU 与容器资源限制下分别记录冷启动和预热基线。
3. 复核空结果、八度错误和长音频异常样例，再写入第一版真实阈值。
4. Provider、模型、参数、标准化格式或容器资源变化时创建新报告，不覆盖旧报告。
5. 只有真实数据集的 overall 与每个正式 category 都通过，才允许把质量结论写入路线图。
