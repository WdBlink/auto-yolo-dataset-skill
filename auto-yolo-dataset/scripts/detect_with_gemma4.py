#!/usr/bin/env python3
"""Generate an auto-yolo-dataset detection manifest through local Gemma 4 service."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def split_for_index(index: int, total: int) -> str:
    if total < 3:
        return "train"
    if index == total - 2:
        return "val"
    if index == total - 1:
        return "test"
    return "train"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", required=True, help="Directory containing source images.")
    parser.add_argument("--classes", required=True, help="Comma-separated class names, e.g. truck,car.")
    parser.add_argument("--manifest", required=True, help="Output detection manifest JSON path.")
    parser.add_argument("--detector-url", default="http://127.0.0.1:11500/detect")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    image_root = Path(args.image_dir).expanduser().resolve()
    classes = [item.strip() for item in args.classes.split(",") if item.strip()]
    if not classes:
        raise SystemExit("--classes must contain at least one class")
    image_paths = sorted(path for path in image_root.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS)
    if not image_paths:
        raise SystemExit(f"no images found under {image_root}")

    images = []
    for index, image_path in enumerate(image_paths):
        result = post_json(
            args.detector_url,
            {"image_path": str(image_path), "classes": classes, "max_new_tokens": args.max_new_tokens},
            args.timeout,
        )
        if not result.get("ok"):
            raise SystemExit(f"detector failed for {image_path}: {result.get('error')}")
        with Image.open(image_path) as image:
            width, height = image.size
        images.append(
            {
                "file": image_path.relative_to(image_root).as_posix(),
                "width": int(result.get("width") or width),
                "height": int(result.get("height") or height),
                "split": split_for_index(index, len(image_paths)),
                "detections": result.get("detections", []),
            }
        )

    manifest = {
        "dataset": {
            "name": image_root.name,
            "source": "gemma4-local-detector",
            "image_root": str(image_root),
        },
        "classes": classes,
        "images": images,
    }
    output = Path(args.manifest).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} with {len(images)} images and {sum(len(item['detections']) for item in images)} detections")


if __name__ == "__main__":
    main()
