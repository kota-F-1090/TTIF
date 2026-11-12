"""設定。環境変数で上書きできる。"""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen3:4b-instruct"
    db_path: str = str(ROOT / "data" / "tutor.db")
    temperature: float = 0.7

    @classmethod
    def from_env(cls) -> "Config":
        d = cls()
        return cls(
            ollama_url=os.environ.get("OLLAMA_URL", d.ollama_url),
            model=os.environ.get("LLM_MODEL", d.model),
            db_path=os.environ.get("TUTOR_DB", d.db_path),
        )
