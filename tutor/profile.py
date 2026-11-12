"""学習者の記録から、説明の仕方を調整する指示文を作る。"""
from .store import Learner, Mastery, Weakness

LEVELS: dict[str, str] = {
    "beginner": "初学者です。専門用語は使うたびにかみくだいて説明し、具体例を多めに使ってください。",
    "standard": "標準的な学習者です。基本用語は使ってよいですが、要点は丁寧に説明してください。",
    "advanced": "上級者です。基本の説明は省き、要点と発展的な内容を簡潔に伝えてください。",
}
LEVEL_ALIASES = {"初級": "beginner", "標準": "standard", "上級": "advanced"}
LEVEL_LABELS = {"beginner": "初級", "standard": "標準", "advanced": "上級"}

LOW_SCORE = 60   # これ未満は「理解が浅い」
HIGH_SCORE = 80  # これ以上は「得意」
MAX_ITEMS = 3


def parse_level(text: str) -> str:
    key = text.strip().lower()
    key = LEVEL_ALIASES.get(key, key)
    if key not in LEVELS:
        raise ValueError("レベルは 初級 / 標準 / 上級(beginner / standard / advanced)から選んでください")
    return key


def build_profile_prompt(learner: Learner, mastery: list[Mastery], weaknesses: list[Weakness]) -> str:
    lines = ["【この学習者について】", LEVELS.get(learner.level, LEVELS["standard"])]
    if learner.style:
        lines.append(f"本人の希望: {learner.style}")

    low = [m for m in mastery if m.score < LOW_SCORE][:MAX_ITEMS]
    high = sorted((m for m in mastery if m.score >= HIGH_SCORE), key=lambda m: -m.score)[:MAX_ITEMS]
    if low:
        items = "、".join(f"{m.subject}/{m.unit}({m.score:.0f}点)" for m in low)
        lines.append(f"理解が浅い単元: {items}。これらに関係する話題では、特に基礎から丁寧に説明してください。")
    if high:
        items = "、".join(f"{m.subject}/{m.unit}" for m in high)
        lines.append(f"得意な単元: {items}。これらは簡潔な説明でかまいません。")
    if weaknesses:
        items = "、".join(f"{w.note}({w.subject}/{w.unit})" for w in weaknesses[:MAX_ITEMS])
        lines.append(f"過去につまずいた点: {items}。関係する場面では、つまずきやすい点として補足してください。")
    return "\n".join(lines)
