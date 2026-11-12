"""テスト用の偽 LLM。台本どおりに返し、受け取った入力を記録する。"""
from typing import Iterator

from .base import LLMError, Message


class FakeBackend:
    def __init__(self, replies: list[str] | None = None, json_replies: list[dict | Exception] | None = None):
        self.replies = list(replies or [])
        self.json_replies = list(json_replies or [])
        self.chat_calls: list[list[Message]] = []
        self.json_calls: list[list[Message]] = []

    def check(self) -> None:
        return None

    def chat_stream(self, messages: list[Message], **options) -> Iterator[str]:
        self.chat_calls.append([dict(m) for m in messages])
        if not self.replies:
            raise LLMError("FakeBackend: 返答の台本がありません")
        text = self.replies.pop(0)
        for i in range(0, len(text), 4):  # 4文字ずつ流してストリーミングを再現する
            yield text[i : i + 4]

    def chat(self, messages: list[Message], **options) -> str:
        return "".join(self.chat_stream(messages, **options))

    def chat_json(self, messages: list[Message], schema: dict, **options) -> dict:
        self.json_calls.append([dict(m) for m in messages])
        if not self.json_replies:
            raise LLMError("FakeBackend: JSON 返答の台本がありません")
        reply = self.json_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
