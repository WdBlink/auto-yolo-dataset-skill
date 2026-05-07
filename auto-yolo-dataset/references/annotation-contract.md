---
name: annotation-contract
description: Detection manifest schema shared by active model vision, future Gamma 4 adapters, and the deterministic dataset builder.
---

# Annotation Contract

Use this JSON contract as the only boundary between visual reasoning and dataset generation.

## Manifest Shape

```json
{
  "dataset": {
    "name": "sample-detection-dataset",
    "version": "0.1.0",
    "description": "Short purpose statement",
    "license": "UNSPECIFIED"
  },
  "classes": ["red-block", "blue-disc"],
  "images": [
    {
      "file": "images/sample-001.png",
      "width": 320,
      "height": 240,
      "split": "train",
      "detections": [
        {
          "class": "red-block",
          "bbox": [40, 50, 140, 150],
          "confidence": 0.93,
          "source": "active-model",
          "notes": "optional"
        }
      ]
    }
  ]
}
```

## Field Rules

- `classes`: unique non-empty names. Order is the YOLO class id order.
- `images[].file`: relative image path under `--image-root` or the manifest directory.
- `width` and `height`: positive integers. If omitted, the builder reads PNG/JPEG dimensions.
- `split`: one of `train`, `val`, or `test`; defaults to `train`.
- `bbox`: absolute pixel `[x_min, y_min, x_max, y_max]`, using half-open extents where `x_max` and `y_max` are the exclusive lower-right bounds.
- Box bounds: `0 <= x_min < x_max <= width` and `0 <= y_min < y_max <= height`.
- `confidence`: optional number in `[0,1]`; not written into YOLO labels.

## Visual Annotation Procedure

1. Open each image with multimodal vision.
2. Name only visible object categories relevant to the requested dataset.
3. Estimate tight boxes around visible object extents, not shadows or labels.
4. Prefer fewer reliable boxes over many uncertain boxes.
5. Save uncertainty in `confidence` or `notes`; never hide uncertainty inside class names.
6. Run the builder and correct any validation failures mechanically.
