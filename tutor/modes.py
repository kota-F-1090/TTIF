"""5つの学習モードの定義。"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
MAX_HINT_LEVEL = 3


class Mode(str, Enum):
    QUESTION = "question"
    EXPLAIN = "explain"
    CORRECT = "correct"
    TEACHER = "teacher"
    HINT = "hint"


@dataclass(frozen=True)
class ModeSpec:
    mode: Mode
    label: str          # 表示名
    description: str    # 一言説明
    temperature: float  # このモードに向いた温度


MODE_SPECS: dict[Mode, ModeSpec] = {
    Mode.QUESTION: ModeSpec(Mode.QUESTION, "質問", "疑問に簡潔に答える", 0.5),
    Mode.EXPLAIN: ModeSpec(Mode.EXPLAIN, "解説", "段階を追って丁寧に説明する", 0.6),
    Mode.CORRECT: ModeSpec(Mode.CORRECT, "添削", "答案の良い点と直す点を指摘する", 0.3),
    Mode.TEACHER: ModeSpec(Mode.TEACHER, "先生", "質問を通して理解度を確かめる", 0.7),
    Mode.HINT: ModeSpec(Mode.HINT, "ヒント", "答えは言わず、ヒントだけ出す", 0.6),
}


# 小さなモデルは長い会話で最初の指示を忘れやすいので、最新の発言の直前で要点だけ念押しする
MODE_REMINDERS: dict[Mode, str] = {
    Mode.QUESTION: "結論から簡潔に答える。",
    Mode.EXPLAIN: "段階を追って説明し、具体例を入れ、最後に理解を確認する。",
    Mode.CORRECT: "良い点→直す点の順に指摘する。正しい答え・完成した解答は書かず、直す箇所と直す方向だけ示す。",
    Mode.TEACHER: "質問は1つだけ出す。答えや正解を先に言わない。点数は言わない。",
    Mode.HINT: "答えや計算結果は絶対に言わない。段階{hint_level}のヒントを1つだけ短く出す。",
}


def mode_reminder(mode: Mode, hint_level: int = 1) -> str:
    label = MODE_SPECS[mode].label
    rule = MODE_REMINDERS[mode].replace("{hint_level}", str(hint_level))
    return f"(現在は【{label}モード】です。{rule}それ以前の会話が別のモードでも、このモードのルールに従う。)"


def parse_mode(text: str) -> Mode:
    """'teacher' でも '先生' でも受け付ける。不明なら ValueError。"""
    key = text.strip().lower()
    for spec in MODE_SPECS.values():
        if key in (spec.mode.value, spec.label):
            return spec.mode
    names = ", ".join(f"{s.mode.value}({s.label})" for s in MODE_SPECS.values())
    raise ValueError(f"モード '{text}' はありません。使えるモード: {names}")


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


def system_prompt(mode: Mode, hint_level: int = 1) -> str:
    """共通ルール + モード別の指示。"""
    mode_text = load_prompt(mode.value).replace("{hint_level}", str(hint_level))
    return f"{load_prompt('common')}\n\n{mode_text}"
