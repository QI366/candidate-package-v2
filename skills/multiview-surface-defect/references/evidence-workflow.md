# 证据链与双类别检查

## 图像准备

使用 Python 和 Pillow 运行 `scripts/prepare_views.py`。脚本生成导航预览、源图 SHA-256 及尺寸；可按 Agent 选定的原图像素框生成无缩放 PNG 裁剪。安装依赖见 `../requirements.txt`。自动去背景、锐化、生成式补全均不是判定缺陷所必需；本脚本不执行这些变换。

```powershell
python scripts/prepare_views.py --images "<images>" --out "<run>/prepared"
python scripts/prepare_views.py --images "<images>" --out "<run>/prepared" --objects object-a --regions "<run>/regions.json"
```

`regions.json` 示例：

```json
{"regions":[{"object_id":"object-a","view":"front.png","box_pixel":[100,200,500,600]}]}
```

保留整体预览以确认方向与物体完整边界；局部裁剪以原图像素输出，脚本不猜测物体范围。裁剪框必须覆盖候选周边，不能只展示被认为有缺陷的像素。证据坐标沿用源文件像素方向，不应用 EXIF 旋转；若先做旋转，需另记变换且按统一坐标系评估。

生成图像与 manifest 不算看过图像。Agent 实际查看后，才更新 `inspection_log.json`。

## 双类别检查

同一物体分别回答两个问题：

1. **表面痕迹**：是否有不规则细长线、局部擦伤？看平面和侧壁，区分规则工艺纹、接缝和反光。
2. **局部缺损**：是否有边界中断、局部凹入、不规则断口或套层露底？看轮廓、端部、孔边、薄层下缘和接合处。不能因为未见划痕就结束这一检查。

明显单视角证据也可报告，其他视角无法看见时填 `not_visible`。不能强制“两视角确认”作为检出门槛，也不能把不同侧面的相似痕迹自动合并。圆管等旋转对称物体尤其缺少稳定锚点，应保留“同一实体数量未知”的不确定性。

对已有候选对象的剩余表面继续检查，允许同一物体同时包含两类细节。密集线痕只有在难以分离时才合并为局部区域簇；空间分离的痕迹分开定位，不用一个整物体框掩盖遗漏。

## 阴性与证据门槛

阴性结论要说明两类检查的实际范围。纯导航、较低分辨率初筛或局部区域检查不足以支持完整对象阴性；需要细节核查，做不到则 `review`。对称性、外观类似的其他物体只能作为提出检查问题的线索，不能当作该物体缺损的直接证据。

## 查看记录契约

`inspection_log.json` 与 JSON 结果分别保存，后者仍保持版本 1.0。日志格式：

```json
{
  "log_version":"1.0",
  "scope":["object-a"],
  "views":[{
    "object_id":"object-a",
    "view":"front.png",
    "source_sha256":"源图的64位十六进制哈希",
    "stage":"detail",
    "artifacts_seen":["prepared/object-a/front.png.region-01.png"],
    "checks":{"linear_mark":"complete","material_loss":"complete"},
    "note":"描述查看范围及两类检查依据，不复制其他视图结论。"
  }]
}
```

`stage` 为 `navigation`、`detail` 或 `unreadable`；`checks` 为 `complete`、`limited`、`not_checked`。`complete` 仅针对该视角的可见表面，不能意味着未知背面已检查。检查原图时 `artifacts_seen` 可指向原文件；所有路径相对日志位置，也可用绝对路径。

每个 scope 对象的收到视角都列一项；未有效查看的视角填对应 limited/not_checked。日志是执行者自报，源图哈希和文件存在只能检查来源一致性，不能从技术上证明模型确实看过图片。

用 `validate_results.py --inspection-log <日志>` 检查日志引用、源图哈希和视角覆盖。明确的 `no_visible_defect` 对象要求各视角为 detail、两类 checks 为 complete；不满足时应 review。缺失日志在兼容校验中只产生提醒，在 `--strict-evidence` 中报错。局部回归需显式传 `--objects` 声明对象范围。
