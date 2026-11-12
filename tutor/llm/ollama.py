"""Ollama のローカル API を使う実装。標準ライブラリのみ。"""
import json
import urllib.error
import urllib.request
from typing import Iterator

from .base import LLMError, Message

TIMEOUT_SECONDS = 180


class OllamaBackend:
    def __init__(self, model: str, url: str = "http://localhost:11434", timeout: float = TIMEOUT_SECONDS):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout

    # --- 内部 ---------------------------------------------------------
    def _open(self, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}{path}", data=data, headers={"Content-Type": "application/json"}
        )
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            with e:  # 応答本文を読んだら接続を閉じる
                message = _error_text(e)
            raise LLMError(f"Ollama がエラーを返しました: {message}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LLMError("Ollama に接続できません。Ollama を起動してください (ollama serve)。") from e

    def _payload(self, messages: list[Message], stream: bool, options: dict) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": stream}
        if options:
            payload["options"] = options  # 例: temperature=0.7, num_ctx=4096
        return payload

    # --- 公開 ---------------------------------------------------------
    def check(self) -> None:
        with self._open("/api/tags") as resp:
            names = [m["name"] for m in json.load(resp).get("models", [])]
        if self.model not in names:
            raise LLMError(
                f"モデル {self.model} がありません。`ollama pull {self.model}` を実行してください。\n"
                f"インストール済み: {names}"
            )

    def chat_stream(self, messages: list[Message], **options) -> Iterator[str]:
        with self._open("/api/chat", self._payload(messages, True, options)) as resp:
            for line in resp:
                if not line.strip():
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise LLMError(f"Ollama がエラーを返しました: {data['error']}")
                yield data.get("message", {}).get("content", "")
                if data.get("done"):
                    break

    def chat(self, messages: list[Message], **options) -> str:
        return "".join(self.chat_stream(messages, **options))

    def chat_json(self, messages: list[Message], schema: dict, **options) -> dict:
        payload = self._payload(messages, False, options)
        payload["format"] = schema  # 構造化出力: スキーマに沿った JSON だけを返させる
        with self._open("/api/chat", payload) as resp:
            body = json.load(resp)
        if "error" in body:
            raise LLMError(f"Ollama がエラーを返しました: {body['error']}")
        content = body.get("message", {}).get("content", "")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"JSON として解釈できない応答でした: {content[:200]!r}") from e
        if not isinstance(result, dict):
            raise LLMError(f"JSON オブジェクトではない応答でした: {content[:200]!r}")
        return result


def _error_text(e: urllib.error.HTTPError) -> str:
    try:
        return json.load(e).get("error", str(e))
    except Exception:
        return str(e)
