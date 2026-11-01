# 多视角表面缺陷识别

本项目包含一个多视角表面缺陷识别 Skill，用于检查同一物体的多角度照片，识别线状痕迹和局部缺损，并输出带有视角、位置和复核状态的结构化结果。

Skill 使用宿主 Agent 已有的多模态视觉能力进行识别，不包含独立推理服务。校验脚本只检查结果文件结构和记录一致性，不能替代实际图像检查，也不能证明识别结论正确。

## 项目结构

- `skills/multiview-surface-defect/SKILL.md`：中文 Skill 入口。
- `skills/multiview-surface-defect/SKILL.en.md`：英文 Skill 入口。
- `skills/multiview-surface-defect/references/`：检查规范、证据流程和输出字段说明。
- `skills/multiview-surface-defect/scripts/`：图像准备与结果校验脚本。
- `skills/multiview-surface-defect/tests/`：工作流测试。
- `results/`：项目已有的结构化检查结果和评估记录。

原始图片、裁剪图和预览图不包含在仓库中。运行前请将图片放入本地 `images/` 目录，并按物体分组：每个一级子目录对应一个物体，目录内放该物体的多个视角。支持 PNG、JPG、JPEG、WebP、BMP、TIF 和 TIFF 格式。

```text
images/
├── object-a/
│   ├── view-01.png
│   └── view-02.png
└── object-b/
    ├── front.jpg
    └── back.jpg
```

## 安装依赖

结果校验使用 Python 标准库。图像准备脚本需要 Pillow；在 PowerShell 中运行：

```powershell
python -m pip install -r .\skills\multiview-surface-defect\requirements.txt
```

## 使用 Skill

将 `skills/multiview-surface-defect` 目录复制到 Agent 的 Skills 目录，或直接向支持本地图片的 Agent 提供 `skills/multiview-surface-defect/SKILL.md` 路径。请求检查 `images/` 中的所有物体，并将 JSON、JSONL 和评估记录写入 `results/`。

Skill 的详细输入约定、证据记录流程及输出格式见其 [README](skills/multiview-surface-defect/README.md) 和 [使用说明](skills/multiview-surface-defect/使用说明.md)。

## 校验结果

从仓库根目录运行：

```powershell
python .\skills\multiview-surface-defect\scripts\validate_results.py `
  --results .\results\inspection_results.json `
  --images .\images `
  --jsonl .\results\inspection_results.jsonl
```

仅校验示例模板时：

```powershell
python .\skills\multiview-surface-defect\scripts\validate_results.py `
  --results .\skills\multiview-surface-defect\templates\inspection-results.json
```

更多参数和严格证据校验方式见 [Skill 使用说明](skills/multiview-surface-defect/README.md#校验结果) 与 [证据工作流](skills/multiview-surface-defect/references/evidence-workflow.md)。
