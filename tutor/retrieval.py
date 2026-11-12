"""将来の RAG(教材検索)の差し込み口。

今は何も返さない NullRetriever だけ。後で教材を検索する実装に差し替えれば、
TutorSession 側は変更せずに参考資料をプロンプトへ追加できる。
"""
from typing import Protocol


class Retriever(Protocol):
    def retrieve(self, query: str, limit: int = 3) -> list[str]:
        """query に関連する資料の断片を返す。"""


class NullRetriever:
    def retrieve(self, query: str, limit: int = 3) -> list[str]:
        return []
