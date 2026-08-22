# Abachiwave 文档索引

本目录把“当前事实”“后续目标”“开发方法”和“历史计划”分开维护。新成员或新任务不要从历史
计划反推当前实现，先阅读下面的 canonical 文档。

## 当前事实来源

| 文档 | 回答的问题 | 更新时机 |
| --- | --- | --- |
| [`status.md`](status.md) | 产品现在完成到哪里、当前证据和已知风险是什么 | 每个阶段结束或验证结论变化时 |
| [`architecture.md`](architecture.md) | 系统当前怎样运行、边界和不变量是什么 | 组件、数据流或不变量变化时 |
| [`api.md`](api.md) | 当前 HTTP 接口和错误契约是什么 | API 合同变化时 |
| [`development.md`](development.md) | 开发、迁移、测试和交付应怎样执行 | 工程流程或门禁变化时 |
| [`runbook.md`](runbook.md) | 怎样启动、验证、排障和恢复本地环境 | 命令、服务或运维流程变化时 |

## 目标与专项

| 文档 | 定位 |
| --- | --- |
| [`roadmap.md`](roadmap.md) | 从当前状态出发的有序开发路径和阶段退出条件 |
| [`audio-to-midi-benchmark.md`](audio-to-midi-benchmark.md) | Audio-to-MIDI 数据集、指标、参数扫描与放行口径 |
| [`backup-restore.md`](backup-restore.md) | PostgreSQL 与 MinIO 备份恢复流程 |
| [`plans/02-full-product.md`](plans/02-full-product.md) | Milestone 8～13 的长期产品目标，不代表完成度 |

## 历史材料

`plans/01-product.md`、`plans/03-milestone-7.md`、`plans/04-ux-improvement.md`、
`plans/00-status-and-roadmap.md` 和 `superpowers/plans/` 是规划或实施快照。它们用于解释决策背景，
不再作为当前完成度和下一步优先级的事实来源。

## 推荐阅读路径

- 接手开发：`status` → `architecture` → `development` → 当前专项文档。
- 修改 API：`architecture` → `api` → `development` 的迁移与验证清单。
- 排查本地环境：`runbook` → `architecture` 的相关组件章节。
- 讨论下一阶段：`status` → `roadmap` → `plans/02-full-product`。
- 调整音频模型：`audio-to-midi-benchmark` → `runbook` 的模型与资源验证章节。

## 维护规则

1. `status.md` 只写已被当前代码、测试、运行报告或外部状态证明的事实。
2. `roadmap.md` 只写尚未完成的工作、排序理由和退出条件，不复制实现历史。
3. `architecture.md` 描述已落地设计；未来设想只能写入 roadmap 或长期计划。
4. 专项报告必须记录数据集、Provider、版本、参数、checksum 和运行环境；`passed: true` 只有在
   配置了正式阈值时才可解释为质量通过。
5. 文档中的命令应从仓库根目录可执行，并与 CI/Compose 的实际服务名保持一致。
6. 完成一个阶段时同时更新 status、roadmap 和受影响的架构/API/runbook，避免只改计划勾选框。
