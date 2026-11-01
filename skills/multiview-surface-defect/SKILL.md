---
name: multiview-surface-defect
description: 使用通用多模态大模型检查同一物体的多角度照片，识别划痕、擦痕等线状痕迹，以及崩缺、材料缺失等局部缺损，输出带证据视图、近似位置和置信等级的结构化结果。适用于多视角表面检查、外观瑕疵识别与识别效果量化评估。
metadata:
  short-description: 多视角表面缺陷识别
---

# multiview-surface-defect — 多视角表面缺陷识别

每个目录对应一个物体，每张照片对应一个视角。使用当前 Agent 可用的通用多模态模型识别可见表面细节，通过跨视角核验减少重复计数和正常结构误报。

## Install（安装）

将整个 `multiview-surface-defect` 目录复制到 Agent 的 skills 目录。Codex 使用 `$CODEX_HOME/skills/`；未设置时使用 `~/.codex/skills/`。也可直接把本文件路径交给支持本地图片读取的 Agent，无需安装。

本 Skill 不自带模型权重、不需要训练。识别由宿主 Agent 的图像理解能力完成；校验脚本只检查结构和计数。详细使用方法见 [README.md](README.md)。英文入口见 [SKILL.en.md](SKILL.en.md)，与本文件保持相同的识别规则和输出契约。

## What the skill gives you（能力与交付物）

- **两类表面候选**：`linear_mark`（划痕、擦痕）和 `material_loss`（崩缺、材料缺失）。
- **多视角证据**：证据图、归一化近似框、物体相对位置及其他视角的核验记录。
- **完整对象结果**：包括未发现目标候选的对象，以及需要复核的对象。
- **标准交付**：`inspection_results.json`、逐对象的 `inspection_results.jsonl` 和 `evaluation.md`。
- **可运行校验**：检查字段、引用、覆盖范围、候选框和汇总计数，区分过程指标与识别性能。
- **证据准备与检查日志**：无缩放局部裁剪、原图哈希、逐视角双类别检查，以及严格证据校验。

## When to use（适用场景）

用户提供按物体分组的多角度照片，要求识别两类表面细节、输出证据或比较识别效果时使用。单组也可执行；不因视角少而虚构佐证。若用户未说明路径且上下文不能确定，再询问输入位置。

## Quick start（快速开始）

1. **确认输入分组**：读取 [references/inspection-guide.md](references/inspection-guide.md)，枚举每个物体目录内的图片。保持不同物体的证据隔离。
2. **准备并检查图像**：按 [references/evidence-workflow.md](references/evidence-workflow.md) 生成带原图哈希和坐标的预览/局部裁剪，实际查看后更新检查日志。每视角分别检查表面线痕，以及轮廓、孔边、薄层和端部的缺损；联系表只用于导航。
3. **跨视角核验**：按物体位置、朝向与形状合并同一物理候选，记录确认、矛盾或不可见的视角。
4. **写入标准结果**：读取 [references/output-schema.md](references/output-schema.md)，参照 [templates/inspection-results.json](templates/inspection-results.json) 输出 JSON，再生成每对象一行的 JSONL。模板是演示数据，不能当作输入对象结果。
5. **运行校验**：在 Skill 目录执行：

   ```powershell
   python scripts/validate_results.py --results "<输出目录>/inspection_results.json" --images "<输入图片目录>" --jsonl "<输出目录>/inspection_results.jsonl" --inspection-log "<输出目录>/inspection_log.json" --strict-evidence
   ```

6. **记录量化结果**：按 [references/evaluation.md](references/evaluation.md) 写 `evaluation.md`。区分读取、初筛和细节复核覆盖；没有独立真值时不报告准确率、precision、recall 或 F1。

对存在反光/加工纹歧义、缺损边界不清或旋转对称物体实体映射不清的候选，读取 [references/inspection-strategy.md](references/inspection-strategy.md)，按歧义提出有判别力的补拍请求；不能补拍时保持 `review`。

## Inspection rules（识别规则）

- **先确认可见证据**：不能从缩略图、物体类别或其他物体的照片推断缺陷。图像不清或未查看时如实说明。
- **两类独立检查**：线痕检查结束后仍需检查局部缺损，重点看物体轮廓、孔口、薄层边界与断面；亮色擦痕本身不证明材料缺失，规则纹理也不能未经核验就排除全部线痕。
- **排除正常结构**：接缝、锯齿、开孔、纹理、印字、阴影、反光及污渍本身不属于目标缺陷；可疑时在 `uncertainty` 说明并使用低置信与 `review`，不新增未定义类别。
- **位置可追溯**：`bbox_1000` 为证据原图左上角起算的 0–1000 坐标。裁剪后需映射回原图；不把近似框描述成像素级分割或实际毫米尺寸。
- **去重有依据**：仅在位置和形态对应时合并跨视角候选；不能把“相似划痕”自动当作同一条。密集不可分离线痕可记作一个区域簇，并明确计数单位。
- **检出不以多视角为门槛**：单视角形态证据清楚也可报告。圆管等旋转对称物体无法对应实体时，保留未解决的身份关系、设为复核；候选条目数不能冒充真实物理缺陷数。
- **证据不足可复核**：低置信、重要遮挡或检查不完整时设为 `review` 并填写 `review_reason`。未发现候选仅表示照片中未见可辨认的目标细节。
- **覆盖如实记录**：`views_inspected` 不包含仅成功读取、未被模型查看的图片；检查深度在评估报告另记，不能把读取覆盖率写成细节检出率。
- **阴性有记录支撑**：新运行写 `inspection_log.json`，记录源图哈希、实际查看产物及两类检查深度。只有初筛、未完成细节查看的对象应复核；历史无日志结果只能做兼容检查。
- **控制优化范围**：量化比较固定模型、输入和评估口径，按物体划分调参与验收集。未做对照运行不能宣称 F1 提升。

## References（按需加载）

| 任务 | 参考文件 |
|---|---|
| 开始逐图识别、判断混淆项、跨视角去重 | [inspection-guide.md](references/inspection-guide.md) |
| 图像准备、双类别检查、检查日志与严格门槛 | [evidence-workflow.md](references/evidence-workflow.md) |
| 对不确定候选设计补拍、分开判断光度与形貌证据 | [inspection-strategy.md](references/inspection-strategy.md) |
| 写 JSON、框坐标、状态和计数 | [output-schema.md](references/output-schema.md) |
| 记录执行覆盖、设计评估与量化优化 | [evaluation.md](references/evaluation.md) |
| 安装、调用示例和 Windows 命令 | [README.md](README.md) |

## File structure（目录结构）

```text
multiview-surface-defect/
├── SKILL.md                         # Agent 入口与核心规则
├── SKILL.en.md                      # English entrypoint
├── README.md                        # 中文安装与使用说明
├── 使用说明.md                      # 原说明文件的兼容入口
├── requirements.txt                 # 图像准备脚本使用 Pillow
├── references/
│   ├── inspection-guide.md          # 逐图检查和多视角核验
│   ├── evidence-workflow.md         # 证据链与双类别检查
│   ├── inspection-strategy.md       # 歧义驱动复核与补拍策略
│   ├── output-schema.md             # JSON 1.0 数据契约
│   └── evaluation.md                # 量化评估与优化方法
├── templates/
│   └── inspection-results.json      # 字段与计数一致的演示模板
├── tests/
│   └── test_workflow.py             # 结果校验与证据流水线回归测试
└── scripts/
    ├── prepare_views.py             # 保真裁剪、哈希与坐标映射
    └── validate_results.py          # 无第三方依赖的结果校验
```

## Troubleshooting（常见问题）

- **Agent 不能读图片**：报告能力限制，改用可读取本地图片的多模态 Agent；不要用文件名生成识别结果。
- **图片不可读或缺少视角**：保留对象与错误记录；不能静默跳过后宣称完整检查。
- **细痕在联系表看不见**：回到原图或物体区域裁剪，不以联系表初筛作可靠阴性判断。
- **校验失败**：先修正字段、图像引用和汇总，再交付；结构通过不等于识别正确。

## Completion checklist（交付检查）

- [ ] 输入对象无遗漏，视角列表与实际查看记录一致。
- [ ] 两类候选均有可追溯证据，不同视角重复观察没有重复计数。
- [ ] 不确定、遮挡和检查深度写入结果或报告。
- [ ] JSON、JSONL 及汇总计数通过脚本校验。
- [ ] 新运行具备逐视角检查日志并通过严格证据校验；部分回归明确声明对象范围。
- [ ] 量化报告注明真值来源、指标分母和本轮优化的实际验证范围。
