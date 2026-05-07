---
name: auto-yolo-dataset
description: Generate object-detection annotations and dataset assets from images using the active model's multimodal vision or a future Gamma 4-compatible detector. Use when Codex needs to inspect images, draft bounding boxes, write standard YOLO labels, convert detections into COCO/Pascal VOC/Label Studio assets, validate detection manifests, or prepare portable local target-detection datasets for Claude Code, Codex, or other agent hosts.
---

# Auto YOLO Dataset

Use this skill to turn images into local object-detection dataset assets. The model reads images; the bundled script only validates and converts a detection manifest. Keep those responsibilities separate so Gamma 4 can replace the active model later without changing the dataset writer.

## Workflow

1. Identify the images, target classes, and output directory. If target classes are not supplied, infer a minimal class list from visible objects and ask only when class names would change the user's task.
2. Read the images with the active model's multimodal capability. For each object, record an absolute pixel `xyxy` box and class name in the manifest format from `references/annotation-contract.md`.
3. If visual confidence is low, mark the detection with lower `confidence` or add a `notes` field. Do not create boxes for objects that cannot be localized.
4. Save the manifest as JSON, resolve this skill's installed directory, then run the bundled builder from that directory:

```bash
AUTO_YOLO_DATASET_SKILL="$HOME/.codex/skills/auto-yolo-dataset"
python "$AUTO_YOLO_DATASET_SKILL/scripts/build_yolo_dataset.py" \
  --manifest detections.json \
  --output dataset \
  --image-root .
```

Add `--visualize` when the user wants human-review overlays:

```bash
AUTO_YOLO_DATASET_SKILL="$HOME/.codex/skills/auto-yolo-dataset"
python "$AUTO_YOLO_DATASET_SKILL/scripts/build_yolo_dataset.py" \
  --manifest detections.json \
  --output dataset \
  --image-root . \
  --visualize
```

If running under Claude Code only, use `$HOME/.claude/skills/auto-yolo-dataset` for `AUTO_YOLO_DATASET_SKILL`.

5. Inspect the generated `validation.json`. If `--visualize` was used, review `visualizations/index.html` or the per-image SVG overlays. Fix any manifest errors and rerun until the command exits 0.
6. Return the dataset path, class list, split counts, and any limitations in the visual annotations.

## Model Contract

Read `references/annotation-contract.md` before writing or accepting a manifest. The same manifest is the integration boundary for Codex vision, Claude Code vision, Gamma 4, or any external detector.

Gamma 4 migration rule: keep the user prompt and dataset command the same. Only replace the image-observation step with a Gamma 4 adapter that emits the same JSON fields.

## Generated Assets

Read `references/generated-assets.md` when the user asks what files are created or when checking dataset completeness. The builder writes YOLO, COCO, Pascal VOC, Label Studio import JSON, a dataset card, validation metadata, and optional visualization overlays.

## Portability Rules

Read `references/migration.md` before changing this skill for a specific host. The skill must not rely on Codex-only APIs, Claude-only slash commands, hardcoded personal paths, network access, or a specific Gamma 4 API shape.

## Skill Forge Review

When auditing or preparing this skill for distribution, apply `references/skill-forge-checklist.md`: discoverability, reliability, efficiency, trustworthiness, boundedness, value, structure, security, and cross-platform registration.
