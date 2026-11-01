# multiview-surface-defect · 多视角表面缺陷识别

使用现有通用多模态大模型，对同一物体的多角度照片识别线状痕迹和局部缺损，输出可追溯的结构化证据。

## 安装

复制整个 `multiview-surface-defect` 文件夹到本地 Agent 的 skills 目录。Codex 默认目录为 `~/.codex/skills/`，设置了 `CODEX_HOME` 时使用对应目录下的 `skills/`。也可以不安装，直接在请求中提供 `SKILL.md` 的完整路径。

本 Skill 同时提供中文入口 [SKILL.md](SKILL.md) 和英文入口 [SKILL.en.md](SKILL.en.md)，两者共用同一套参考规则与 JSON 1.0 输出格式。按使用语言选择入口；调用英文版时将请求中的 `SKILL.md` 路径替换为 `SKILL.en.md`。

需要支持读取本地图片的多模态 Agent。Skill 不包含独立推理服务，校验脚本不执行图像识别；Python 3.9 或更新版本可运行校验。图像准备脚本额外依赖 Pillow，安装命令为 `python -m pip install -r requirements.txt`。识别是否联网、模型是否在本机推理由所用 Agent 决定，本地文件执行不等于模型权重本地部署。

## 输入格式

```text
images/
├── object-a/
│   ├── view-01.png
│   └── view-02.png
└── object-b/
    ├── front.jpg
    └── back.jpg
```

一级子目录代表物体，不同目录不能合并为同一物体。支持 `.png`、`.jpg`、`.jpeg`、`.webp`、`.bmp`、`.tif`、`.tiff`，具体解码能力以宿主 Agent 为准。不递归把物体目录中的嵌套目录当作额外视角；如存在这种布局，先明确分组。忽略隐藏目录和以 `._` 开头的 macOS 辅助文件。

## 调用示例

安装后向 Agent 发送：

```text
使用 $multiview-surface-defect 检查指定的 images 目录。
每个一级子目录对应同一个物体的多角度照片。
逐图检查线状痕迹与局部缺损，输出 JSON、JSONL 和量化评估记录。
请区分读取覆盖、视觉初筛覆盖与细节复核覆盖。
```

本项目无需安装的调用示例：

```text
请读取并执行
C:\Users\Lenovo\Desktop\candidate-package-v2\candidate-package-v2\skills\multiview-surface-defect\SKILL.md
输入目录：C:\Users\Lenovo\Desktop\candidate-package-v2\candidate-package-v2\images
输出目录：C:\Users\Lenovo\Desktop\candidate-package-v2\candidate-package-v2\results
使用现有多模态能力检查所有对象与视角，按 Skill 输出结果并运行校验。
```

路径只是本项目调用示例，复制到其他机器时替换成实际输入与输出目录。

## 输出文件

| 文件 | 内容 |
|---|---|
| `inspection_results.json` | 全量对象、候选、证据视图、近似框、复核状态和汇总 |
| `inspection_results.jsonl` | 每个对象一行，顺序和内容与 JSON 的 `objects` 一致 |
| `evaluation.md` | 实际检查深度、过程指标、真值情况及优化记录 |
| `inspection_log.json` | 新运行逐视角的来源哈希、查看产物、两类检查深度 |

字段定义见 [references/output-schema.md](references/output-schema.md)。`linear_mark` 是线状痕迹，`material_loss` 是材料缺失；近似框以原图左上角为原点，坐标为 0–1000。`review` 表示需要进一步复核；`no_visible_defect` 仅表示给定照片中未发现可辨认的目标候选。遇到反光、加工纹、边缘缺损或旋转对称实体对应歧义时，参照 [references/inspection-strategy.md](references/inspection-strategy.md) 设计针对性补拍，并分别记录光度与形貌证据。

跨视角重复观察合并计数；多个无法分离的痕迹可输出为一个区域簇，但应明确计数单位。当前结果保持 `schema_version: "1.0"`，与先前交付结果兼容。

## 校验结果

进入本 Skill 目录，在 PowerShell 执行：

```powershell
python .\scripts\validate_results.py --results "..\..\results\inspection_results.json" --images "..\..\images" --jsonl "..\..\results\inspection_results.jsonl"
```

或验证自带的演示模板：

```powershell
python .\scripts\validate_results.py --results ".\templates\inspection-results.json"
```

退出码 `0` 表示校验通过，`1` 表示数据或文件错误，`2` 表示命令参数错误。脚本输出 JSON 格式的错误与过程统计；它只能核对记录，无法证明 Agent 实际查看过图片，也不能判断识别结论是否正确。

新运行使用严格模式；兼容模式保留历史数据可读性，但缺失日志、重复证据说明和过大区域框会提示审计风险：

```powershell
python .\scripts\validate_results.py --results "<run>/inspection_results.json" --images "<images>" --jsonl "<run>/inspection_results.jsonl" --inspection-log "<run>/inspection_log.json" --strict-evidence
```

局部回归额外传 `--objects object-a object-b`，未指定时要求结果覆盖全部输入物体。图像准备、实际查看后更新日志及坐标映射见 [references/evidence-workflow.md](references/evidence-workflow.md)。针对不确定候选的补拍与验证设计见 [references/inspection-strategy.md](references/inspection-strategy.md)。结果使用既有字段契约；不会因文档更新而自动改写旧结果。

## 如何量化优化

无独立人工真值时，报告覆盖率、候选数量、跨视角佐证比例和复核比例，并标明分母。不要将这些数字当作准确率。有真值时按物体划分调参与验收集，固定模型、匹配规则与阈值后，比较两类的 TP/FP/FN、precision、recall 和 F1。方法见 [references/evaluation.md](references/evaluation.md)。

本项目上一次全量执行的产物位于项目 results/ 目录；本轮优化审计、原图证据与明确范围的回归产物位于 results/optimization-v2/。保留原结果用于对照，具体范围与限制见该目录的优化报告。

独立前向验证位于 results/forward-test/，只检查 p09、p10、p25，不读取本轮回归结论。它与针对性回归在 p10、p25 上出现分歧，说明这些是困难样本，不能把任一 Agent 输出当人工真值。

## 项目结构

入口与目录说明见 [SKILL.md](SKILL.md)。`references/` 存放按需读取的详细规则，`templates/` 存放可复制的数据格式，`scripts/` 存放确定性工具。仅创建实际使用的资源，不要求空的 `assets/`、`docs/` 或 PPT 主题目录。
