---
name: multiview-surface-defect
description: Inspect multi-view photos of the same object with a general-purpose multimodal model to identify linear surface marks (such as scratches and abrasions) and localized material loss (such as chips or missing material). Produce traceable evidence, approximate locations, and confidence labels.
metadata:
  short-description: Multi-view surface defect inspection
---

# multiview-surface-defect — Multi-view Surface Defect Inspection

Each input folder represents one object, and each image is one view of that object. Use the host Agent's available multimodal image-understanding capabilities to identify visible surface details. Compare views to avoid duplicate counting and false positives from normal structures.

## Installation

Copy the entire `multiview-surface-defect` folder into the Agent's skills directory. Codex uses `$CODEX_HOME/skills/`, or `~/.codex/skills/` when `CODEX_HOME` is unset. Alternatively, provide the full path to this file to an Agent that can read local images; installation is not required.

This Skill does not include model weights and does not require training. Recognition is performed by the host Agent; the validation scripts check structure and counts but do not recognize images. See [README.md](README.md) for usage details. This is an English counterpart to [SKILL.md](SKILL.md); both entrypoints describe the same workflow and use the same output schema.

## Capabilities and deliverables

- Two surface-candidate types: `linear_mark` (scratches and abrasions) and `material_loss` (chips and missing material).
- Multi-view evidence: source view, approximate normalized bounding box, object-relative location, and cross-view checks.
- A result for every input object, including objects with no visible candidates and objects requiring review.
- Standard artifacts: `inspection_results.json`, one-object-per-line `inspection_results.jsonl`, and `evaluation.md`.
- Runnable validation for fields, references, input coverage, candidate boxes, and aggregate counts. Process coverage is distinguished from recognition performance.
- Evidence preparation and inspection logs, including source-image hashes, pixel-preserving crops, per-view checks of both defect classes, and strict evidence validation.

## When to use

Use this Skill when the user provides multi-angle photos grouped by object and asks to identify either target class, provide evidence, or compare inspection results. A single object group is valid; do not invent cross-view confirmation when too few views are available. Ask for the input path only when it cannot be inferred from the request or context.

## Quick start

1. **Confirm input grouping.** Read [references/inspection-guide.md](references/inspection-guide.md) and enumerate the images in each object folder. Keep evidence from different objects separate.
2. **Prepare and inspect the images.** Follow [references/evidence-workflow.md](references/evidence-workflow.md) to prepare previews or pixel-preserving crops with source hashes and coordinates. Update the inspection log only after actually viewing each artifact. Check both linear marks and material loss in every view; for material loss, inspect outlines, holes, thin-layer edges, and ends. Use contact sheets for navigation only.
3. **Cross-check views.** Merge observations into one physical candidate only when object position, orientation, shape, and surface location support the match. Record whether other views confirm, contradict, or cannot show the candidate.
4. **Write the standard results.** Read [references/output-schema.md](references/output-schema.md), follow [templates/inspection-results.json](templates/inspection-results.json), and produce JSON plus one JSONL record per object. The template is illustrative and must not be reported as an inspection result.
5. **Validate the output.** From the Skill directory, run:

   ```powershell
   python scripts/validate_results.py --results "<output-dir>/inspection_results.json" --images "<image-dir>" --jsonl "<output-dir>/inspection_results.jsonl" --inspection-log "<output-dir>/inspection_log.json" --strict-evidence
   ```

6. **Report the evaluation.** Follow [references/evaluation.md](references/evaluation.md) to write `evaluation.md`. Separate file-read, visual-screening, and detail-inspection coverage. Without independent ground truth, do not report accuracy, precision, recall, or F1.

For candidates with ambiguity between a mark and reflection/process texture, unclear loss boundaries, or uncertain identity across views of a rotationally symmetric object, read [references/inspection-strategy.md](references/inspection-strategy.md). Request targeted additional views that can distinguish the competing explanations. If new images cannot be obtained, keep the object in `review`.

## Inspection rules

- **Use visible evidence.** Do not infer a defect from a thumbnail, object category, filename, or another object's photos. State when an image or detail was not visible or was not inspected.
- **Inspect both classes independently.** After checking for linear marks, separately check for localized material loss, especially at object outlines, openings, thin-layer edges, and fracture surfaces. A bright abrasion alone does not prove material loss; regular texture alone does not rule out every linear mark.
- **Exclude normal structures.** Seams, teeth, openings, texture, printing, shadows, reflections, and stains are not target defects by themselves. If a candidate remains ambiguous, describe the uncertainty and use low confidence plus `review`; do not invent an undefined class.
- **Keep locations traceable.** `bbox_1000` uses coordinates from the top-left of the evidence source image, scaled to 0–1000. Map crop coordinates back to the original image. Do not describe an approximate box as pixel-level segmentation or a physical measurement in millimeters.
- **Deduplicate only with evidence.** Merge observations across views only when location and morphology correspond. Similar-looking marks are not automatically the same scratch. Dense marks that cannot be separated may be reported as one region cluster; state the counting unit.
- **Do not require multiple views for detection.** A clear single-view shape may be reported. For tubes and other rotationally symmetric objects, retain unresolved identity and use `review` when views cannot be mapped reliably. The number of candidate records is not necessarily the number of physical defects.
- **Use review when evidence is insufficient.** Set object status to `review` and populate `review_reason` for low-confidence candidates, important occlusion, contradictory evidence, or incomplete inspection. No candidate means only that no recognizable target detail was visible in the supplied images.
- **Report coverage honestly.** `views_inspected` must not include images that were only decoded but not visually inspected by the model. Report inspection depth separately; file-read coverage is not defect-detection coverage.
- **Support negative conclusions with records.** For new runs, write `inspection_log.json` with source hashes, artifacts actually viewed, and the inspection depth for both classes in each view. Objects with only navigation or incomplete detail checks should be reviewed. Historical results without logs may be validated in compatibility mode only.
- **Control optimization claims.** Fix the model, inputs, and evaluation protocol for quantitative comparisons; split tuning and acceptance data by object. Do not claim an F1 improvement without a controlled comparison and independent ground truth.

## References (load as needed)

| Task | Reference |
|---|---|
| Per-view inspection, confounders, and cross-view deduplication | [inspection-guide.md](references/inspection-guide.md) |
| Image preparation, two-class checks, inspection logs, and strict evidence gates | [evidence-workflow.md](references/evidence-workflow.md) |
| Targeted recapture for uncertain candidates; photometric versus shape evidence | [inspection-strategy.md](references/inspection-strategy.md) |
| JSON fields, coordinates, statuses, and counts | [output-schema.md](references/output-schema.md) |
| Coverage, evaluation design, and quantitative optimization | [evaluation.md](references/evaluation.md) |
| Installation, invocation examples, and Windows commands | [README.md](README.md) |

## File structure

```text
multiview-surface-defect/
├── SKILL.md                         # Chinese entrypoint
├── SKILL.en.md                      # English entrypoint
├── README.md                        # Installation and usage
├── references/
│   ├── inspection-guide.md          # Per-view inspection and cross-view checks
│   ├── evidence-workflow.md         # Evidence trail and two-class checks
│   ├── inspection-strategy.md       # Ambiguity-driven review and recapture
│   ├── output-schema.md             # JSON 1.0 data contract
│   └── evaluation.md                # Quantitative evaluation and optimization
├── templates/
│   └── inspection-results.json      # Illustrative output template
├── tests/
│   └── test_workflow.py             # Workflow and evidence regression tests
└── scripts/
    ├── prepare_views.py             # Pixel-preserving crops, hashes, and coordinate mapping
    └── validate_results.py          # Dependency-free result validation
```

## Troubleshooting

- **The Agent cannot read images:** State the limitation and use a multimodal Agent with local-image access. Never infer visual results from filenames.
- **Images are unreadable or views are missing:** Keep the object and record the specific problem. Do not silently skip it and claim complete inspection.
- **Fine marks are not visible in a contact sheet:** Return to the source image or a crop of the relevant object region. A contact sheet is not sufficient evidence for a negative conclusion about subtle defects.
- **Validation fails:** Correct the fields, image references, and aggregate counts before delivery. Passing structural validation does not establish recognition correctness.

## Completion checklist

- [ ] Every input object is represented, and the view list matches the actual inspection log.
- [ ] Both classes have traceable evidence; repeated observations across views are not double-counted.
- [ ] Uncertainty, occlusion, and inspection depth are recorded in the results or report.
- [ ] JSON, JSONL, and aggregate counts pass validation.
- [ ] New runs have per-view inspection logs and pass strict evidence validation; partial regressions declare their object scope.
- [ ] The evaluation states the ground-truth source, metric denominators, and actual scope of validation.
