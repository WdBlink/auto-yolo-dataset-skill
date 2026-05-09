#!/usr/bin/env python3
"""Small Anthropic Messages API shim for routing Claude Code to Ollama."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif item.get("type") == "tool_result":
                parts.append(str(item.get("content", "")))
        else:
            parts.append(str(item))
    return "\n".join(part for part in parts if part)


def anthropic_to_ollama_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system = payload.get("system")
    if system:
        messages.append({"role": "system", "content": flatten_content(system)})
    for msg in payload.get("messages", []):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        if role not in {"user", "assistant", "system"}:
            role = "user"
        text = flatten_content(msg.get("content", ""))
        if text:
            messages.append({"role": role, "content": text})
    return messages or [{"role": "user", "content": ""}]


def call_ollama(payload: dict[str, Any], model: str, ollama_url: str) -> str:
    request = {
        "model": model,
        "messages": anthropic_to_ollama_messages(payload),
        "stream": False,
        "options": {
            "num_predict": int(payload.get("max_tokens") or 1024),
        },
    }
    data = json.dumps(request).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=int(os.environ.get("OLLAMA_PROXY_TIMEOUT", "600"))) as response:
        result = json.loads(response.read().decode("utf-8"))
    return str(result.get("message", {}).get("content", ""))


def sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "OllamaAnthropicProxy/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("PROXY_VERBOSE") == "1":
            super().log_message(fmt, *args)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"ok": True, "model": self.server.model})
            return
        if self.path == "/v1/models":
            self.send_json(200, {"data": [{"id": self.server.model, "type": "model"}]})
            return
        self.send_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        request_path = self.path.split("?", 1)[0].rstrip("/")
        if request_path != "/v1/messages":
            self.send_json(404, {"error": {"message": "not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            text = call_ollama(payload, self.server.model, self.server.ollama_url)
        except (ValueError, urllib.error.URLError, TimeoutError) as exc:
            self.send_json(500, {"error": {"type": "proxy_error", "message": str(exc)}})
            return

        message_id = f"msg_{int(time.time() * 1000)}"
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(
                sse(
                    "message_start",
                    {
                        "type": "message_start",
                        "message": {
                            "id": message_id,
                            "type": "message",
                            "role": "assistant",
                            "model": self.server.model,
                            "content": [],
                            "stop_reason": None,
                            "stop_sequence": None,
                            "usage": {"input_tokens": 0, "output_tokens": 0},
                        },
                    },
                )
            )
            self.wfile.write(
                sse(
                    "content_block_start",
                    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                )
            )
            self.wfile.write(
                sse(
                    "content_block_delta",
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
                )
            )
            self.wfile.write(sse("content_block_stop", {"type": "content_block_stop", "index": 0}))
            self.wfile.write(
                sse(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": 0},
                    },
                )
            )
            self.wfile.write(sse("message_stop", {"type": "message_stop"}))
            return

        self.send_json(
            200,
            {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": self.server.model,
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        )


class ProxyServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], model: str, ollama_url: str):
        super().__init__(address, Handler)
        self.model = model
        self.ollama_url = ollama_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("PROXY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PROXY_PORT", "11435")))
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "minimax-m2.5:iq4_xs"))
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    args = parser.parse_args()
    server = ProxyServer((args.host, args.port), args.model, args.ollama_url)
    print(f"proxy listening on http://{args.host}:{args.port} -> {args.ollama_url} model={args.model}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
