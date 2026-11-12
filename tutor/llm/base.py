"""LLM 接続の共通インターフェース。

Ollama / Claude API / テスト用の偽物を、同じ形で差し替えられるようにする。
"""
from typing import Iterator, Protocol

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": str}


class LLMError(RuntimeError):
    """LLM との通信や応答の解釈に失敗したときのエラー。メッセージは利用者にそのまま見せてよい。"""


class LLMBackend(Protocol):
    def check(self) -> None:
        """接続と利用可能性を確認する。使えないときは LLMError を投げる。"""

    def chat_stream(self, messages: list[Message], **options) -> Iterator[str]:
        """応答を断片ごとに yield する。"""

    def chat(self, messages: list[Message], **options) -> str:
        """応答全体を文字列で返す。"""

    def chat_json(self, messages: list[Message], schema: dict, **options) -> dict:
        """JSON スキーマに沿った応答を dict で返す。解釈できないときは LLMError。"""
