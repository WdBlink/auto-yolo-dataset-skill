#!/usr/bin/env python3
"""Local Gemma 4 vision detector service for auto-yolo-dataset."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MODEL = None
PROCESSOR = None
LOAD_ERROR: str | None = None
LOCK = threading.Lock()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def load_model(model_dir: str) -> tuple[Any, Any]:
    global MODEL, PROCESSOR, LOAD_ERROR
    with LOCK:
        if MODEL is not None and PROCESSOR is not None:
            return MODEL, PROCESSOR
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor

            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            PROCESSOR = AutoProcessor.from_pretrained(model_dir, local_files_only=True, trust_remote_code=True)
            MODEL = AutoModelForImageTextToText.from_pretrained(
                model_dir,
                local_files_only=True,
                trust_remote_code=True,
                dtype=dtype,
                device_map="auto",
            )
            MODEL.eval()
            LOAD_ERROR = None
            return MODEL, PROCESSOR
        except Exception as exc:  # pragma: no cover - operational diagnostics
            LOAD_ERROR = f"{type(exc).__name__}: {exc}"
            raise


def extract_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S | re.I)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    if start >= 0:
        candidates.append(text[start:])
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed, _ = decoder.raw_decode(candidate.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise ValueError(f"model did not return parseable JSON: {text[:1000]}")


def normalize_detection(det: dict[str, Any], classes: list[str], width: int, height: int) -> dict[str, Any] | None:
    cls = det.get("class")
    if cls not in classes:
        return None
    bbox = det.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    x1 = max(0.0, min(float(width), x1))
    x2 = max(0.0, min(float(width), x2))
    y1 = max(0.0, min(float(height), y1))
    y2 = max(0.0, min(float(height), y2))
    if not (x1 < x2 and y1 < y2):
        return None
    confidence = det.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))
    return {"class": cls, "bbox": [x1, y1, x2, y2], "confidence": confidence, "source": "gemma4-local"}


def detect(model: Any, processor: Any, image_path: Path, classes: list[str], max_new_tokens: int) -> dict[str, Any]:
    import torch
    from PIL import Image

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    prompt = (
        "You are an object detection annotator. Detect only these target classes: "
        + ", ".join(classes)
        + ". Return only JSON in this exact schema: "
        + '{"detections":[{"class":"CLASS_NAME","bbox":[x1,y1,x2,y2],"confidence":0.0}]} '
        + f"Coordinates must be absolute pixel xyxy values within image width={width}, height={height}. "
        + "Keep the JSON compact. If no target object is visible, return {\"detections\":[]}."
    )
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    )
    inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    input_len = inputs["input_ids"].shape[-1]
    text = processor.decode(output[0][input_len:], skip_special_tokens=True)
    parsed = extract_json(text)
    detections = parsed.get("detections", [])
    if not isinstance(detections, list):
        detections = []
    normalized = [d for d in (normalize_detection(det, classes, width, height) for det in detections if isinstance(det, dict)) if d]
    return {"width": width, "height": height, "detections": normalized, "raw": text}


class Handler(BaseHTTPRequestHandler):
    server_version = "Gemma4VisionService/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("GEMMA4_VERBOSE") == "1":
            super().log_message(fmt, *args)

    def do_GET(self) -> None:
        if self.path == "/health":
            json_response(self, 200, {"ok": LOAD_ERROR is None, "loaded": MODEL is not None, "load_error": LOAD_ERROR})
            return
        json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/") != "/detect":
            json_response(self, 404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            image_path = Path(str(payload["image_path"])).expanduser().resolve()
            classes = payload["classes"]
            if not isinstance(classes, list) or not all(isinstance(item, str) and item for item in classes):
                raise ValueError("classes must be a non-empty string list")
            if not image_path.exists():
                raise ValueError(f"image not found: {image_path}")
            model, processor = load_model(self.server.model_dir)
            max_new_tokens = int(payload.get("max_new_tokens") or self.server.max_new_tokens)
            result = detect(model, processor, image_path, classes, max_new_tokens)
            json_response(self, 200, {"ok": True, **result})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


class Server(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], model_dir: str, max_new_tokens: int):
        super().__init__(address, Handler)
        self.model_dir = model_dir
        self.max_new_tokens = max_new_tokens


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("GEMMA4_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GEMMA4_PORT", "11500")))
    parser.add_argument("--model-dir", default=os.environ.get("GEMMA4_MODEL_DIR", "/home/c301/models/gemma-4-31B-it"))
    parser.add_argument("--max-new-tokens", type=int, default=int(os.environ.get("GEMMA4_MAX_NEW_TOKENS", "512")))
    parser.add_argument("--load-at-start", action="store_true")
    args = parser.parse_args()
    if args.load_at_start:
        load_model(args.model_dir)
    server = Server((args.host, args.port), args.model_dir, args.max_new_tokens)
    print(f"gemma4 vision service listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
