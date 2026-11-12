"""Ollama のローカル API (http://localhost:11434) を叩く最小クライアント。標準ライブラリのみ。"""
import json
import os
import urllib.request
from typing import Iterator

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")


def _post(path: str, payload: dict):
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req)


def chat_stream(messages: list[dict], model: str = DEFAULT_MODEL, **options) -> Iterator[str]:
    """messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    応答をトークン(断片)ごとに yield する。"""
    payload = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options  # 例: temperature=0.7, num_ctx=4096
    with _post("/api/chat", payload) as resp:
        for line in resp:
            if not line.strip():
                continue
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(data["error"])
            yield data.get("message", {}).get("content", "")
            if data.get("done"):
                break


def chat(messages: list[dict], model: str = DEFAULT_MODEL, **options) -> str:
    return "".join(chat_stream(messages, model, **options))


def list_models() -> list[str]:
    with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags") as resp:
        return [m["name"] for m in json.load(resp)["models"]]
