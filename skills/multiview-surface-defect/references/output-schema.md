# 输出数据契约 · 1.0

完整合法示例见 [../templates/inspection-results.json](../templates/inspection-results.json)。该模板是虚构格式示例，不能作为实际图片的识别答案。JSON 文件只写 JSON；中文总结写入评估报告或最终回复。

## 顶层字段

| 字段 | 类型 | 约束 |
|---|---|---|
| `schema_version` | string | 固定 `1.0` |
| `objects` | array | 每个输入物体一项；不遗漏无候选对象 |
| `summary` | object | 五项整数计数，与 `objects` 实际内容一致 |

## 对象字段

| 字段 | 类型 | 约束 |
|---|---|---|
| `object_id` | string | 输入一级子目录名，唯一且非空 |
| `views_received` | string[] | 收到的支持图片文件名，无重复；不可读图片仍列入 |
| `views_inspected` | string[] | 真正视觉检查过的视角，是 received 的无重复子集 |
| `status` | string | `defects_found`、`no_visible_defect`、`review` 三选一 |
| `defects` | array | 候选列表，无候选时为 `[]` |
| `review_reason` | string/null | `review` 时必须非空，其他状态为 `null` |

`defects_found` 至少有一个候选。`no_visible_defect` 必须无候选、全部收到的视角已被视觉检查，且没有阻止判断的成像或覆盖问题。无图片、缺少检查或低置信候选时必须 `review`；不能用空数组掩盖失败。

## 候选字段

| 字段 | 类型 | 约束 |
|---|---|---|
| `defect_id` | string | 物体内唯一，例如 `D1` |
| `type` | string | `linear_mark` 或 `material_loss` |
| `confidence` | string | `high`、`medium` 或 `low` |
| `evidence_view` | string | 来自该对象 `views_inspected` |
| `bbox_1000` | number[4] | `[x1,y1,x2,y2]`，0–1000 且 x1<x2、y1<y2 |
| `relative_location` | string | 基于物体结构的位置描述，非空 |
| `visual_evidence` | string | 描述真实可见证据，非空 |
| `other_views` | array | 无可核验视角时为 `[]` |
| `uncertainty` | string/null | 无不确定性时 `null`；低置信时必须说明 |

`other_views` 每项含 `view`、`relation`、`note`：视角必须已检查、不能等于 `evidence_view`、不能重复；关系为 `confirms`、`contradicts` 或 `not_visible`；`note` 是具体核验依据。出现明确相反证据时保留候选为低置信并复核，或在复核后删除已被排除的候选，在评估报告记录原因。

## 汇总计数

- `objects_total`：对象数组长度。
- `objects_with_defects`：`defects` 非空的对象数，也包括带候选的 `review` 对象。
- `objects_for_review`：`status == "review"` 的对象数。
- `linear_mark_count`：所有对象中 `type == "linear_mark"` 的候选条目数。
- `material_loss_count`：所有对象中 `type == "material_loss"` 的候选条目数。

密集线痕作为区域簇记录时，计数仍按候选条目，报告需说明区域簇口径。

旋转对称物体的不同视角无法对应同一实体时，可保留多个观察候选待复核，必须在 `uncertainty` 和 `review_reason` 明确“身份未解决，可能重复”。此时汇总仅为候选记录数，不能解读成已去重的物理缺陷数。不能为提高跨视角佐证比例强制将这些记录合并。

## JSONL 与兼容性

`inspection_results.jsonl` 每行是 `objects` 的一个完整对象记录，不写顶层 wrapper、空行或 Markdown。顺序、字段内容与 JSON 中对象数组一致。

本次保持版本 1.0 和已有字段；额外的模型标识、检查深度、图像读取错误、耗时、实验版本等写入 `evaluation.md`。旧结果可以继续用校验工具核对，不因文档重组自动重写历史识别结果。

新运行的逐视角可追溯记录保存为 `inspection_log.json`，详细契约见 [evidence-workflow.md](evidence-workflow.md)。结果结构校验通过与证据充分是不同检查：严格模式同时检查日志与阴性依据。
