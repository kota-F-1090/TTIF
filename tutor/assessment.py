"""先生モードの会話から、学習者の理解度を評価する。

LLM に JSON スキーマ付きで採点させ、結果を検証する。小さなモデルは形式を崩すことが
あるので、不正なら1回だけ再試行し、それでもだめなら None を返す(会話は止めない)。
"""
import json
from dataclasses import dataclass

from .llm import LLMBackend, LLMError, Message

MAX_FIELD_LEN = 40
MAX_WEAKNESSES = 3
EMA_ALPHA = 0.6  # 新しい評価をどれだけ重く見るか(0〜1)

ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string", "description": "教科(例: 数学, 物理, プログラミング)"},
        "unit": {"type": "string", "description": "単元(例: 二次関数, 運動方程式)"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "weaknesses": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_WEAKNESSES},
        "rationale": {"type": "string"},
    },
    "required": ["subject", "unit", "score", "weaknesses", "rationale"],
}

ASSESSOR_PROMPT = """あなたは公平な採点者です。以下は先生と学習者の会話です。
学習者の発言だけをもとに、学習者の理解度を評価してください。

採点基準(score, 0〜100):
- 90〜100: 正確に理解し、応用もできている
- 70〜89: 基本は理解しているが、細かい誤りや抜けがある
- 40〜69: 部分的に理解しているが、重要な誤解がある
- 0〜39: ほとんど理解できていない、または答えられていない

出力のルール:
- subject は教科名、unit は単元名を、それぞれ短い日本語で書く。
- weaknesses には、学習者の発言に実際に現れた誤り・答えられなかった点だけを、
  「平方完成の符号」のような具体的な短い言葉で最大3つ書く。
  先生がまだ聞いていないことや推測は書かない。該当がなければ空の配列にする。
- 点数と weaknesses は矛盾させない(高得点なら weaknesses は少ないはず)。
- rationale には、点数の理由を1〜2文で書く。"""


@dataclass(frozen=True)
class AssessmentResult:
    subject: str
    unit: str
    score: int
    weaknesses: list[str]
    rationale: str


def _clean(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} が空、または文字列ではありません")
    return value.strip()[:MAX_FIELD_LEN]


def parse_assessment(data: dict) -> AssessmentResult:
    """LLM の出力を検証して AssessmentResult にする。不正なら ValueError。"""
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("score が数値ではありません")
    if not 0 <= score <= 100:
        raise ValueError(f"score が範囲外です: {score}")

    raw_weak = data.get("weaknesses", [])
    if not isinstance(raw_weak, list):
        raise ValueError("weaknesses が配列ではありません")
    weaknesses: list[str] = []
    for w in raw_weak:
        if isinstance(w, str) and w.strip():
            note = w.strip()[:MAX_FIELD_LEN]
            if note not in weaknesses:
                weaknesses.append(note)
    rationale = data.get("rationale", "")
    return AssessmentResult(
        subject=_clean(data.get("subject"), "subject"),
        unit=_clean(data.get("unit"), "unit"),
        score=round(score),
        weaknesses=weaknesses[:MAX_WEAKNESSES],
        rationale=rationale.strip() if isinstance(rationale, str) else "",
    )


def build_assessment_messages(history: list[Message]) -> list[Message]:
    lines = []
    for m in history:
        if m["role"] == "user":
            lines.append(f"学習者: {m['content']}")
        elif m["role"] == "assistant":
            lines.append(f"先生: {m['content']}")
    transcript = "\n".join(lines)
    return [
        {"role": "system", "content": ASSESSOR_PROMPT},
        {"role": "user", "content": f"会話:\n{transcript}\n\n上の会話の学習者を評価してください。"},
    ]


def assess(backend: LLMBackend, history: list[Message], retries: int = 1) -> tuple[AssessmentResult, dict] | None:
    """評価結果と元の JSON を返す。評価できなければ None。"""
    if not any(m["role"] == "user" for m in history):
        return None
    messages = build_assessment_messages(history)
    for _ in range(retries + 1):
        try:
            data = backend.chat_json(messages, ASSESSMENT_SCHEMA, temperature=0)
            return parse_assessment(data), data
        except (LLMError, ValueError):
            continue
    return None


def blend_score(old: float | None, new: float, alpha: float = EMA_ALPHA) -> float:
    """指数移動平均で理解度を更新する。初回は新しい点数をそのまま使う。"""
    if old is None:
        value = new
    else:
        value = old * (1 - alpha) + new * alpha
    return round(min(100.0, max(0.0, value)), 1)


def to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
