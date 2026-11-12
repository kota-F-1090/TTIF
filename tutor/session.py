"""TutorSession: 1つの学習セッションの司令塔。

プロンプトの組み立て(モード + 学習者プロフィール + 参考資料)、LLM 呼び出し、
会話の保存、先生モードの理解度評価をまとめて扱う。画面(CLI など)とは独立しているので、
他のメンバーが作る UI からもこのクラスをそのまま呼べる。
"""
from dataclasses import dataclass
from typing import Iterator

from .assessment import AssessmentResult, assess, blend_score, to_json
from .llm import LLMBackend, Message
from .modes import MAX_HINT_LEVEL, MODE_SPECS, Mode, mode_reminder, system_prompt
from .profile import build_profile_prompt
from .retrieval import NullRetriever, Retriever
from .store import Learner, Repository

ASSESS_EVERY = 3     # 先生モードで、学習者が何回答えたら自動評価するか
MAX_HISTORY = 20     # LLM に渡す直近の発言数(小さいモデルの文脈長に合わせる)


@dataclass(frozen=True)
class AssessmentOutcome:
    result: AssessmentResult
    mastery_score: float  # 移動平均で更新した後の理解度


class TutorSession:
    def __init__(
        self,
        backend: LLMBackend,
        repo: Repository,
        learner: Learner,
        *,
        mode: Mode = Mode.QUESTION,
        session_id: int | None = None,
        retriever: Retriever | None = None,
        temperature: float | None = None,
        assess_every: int = ASSESS_EVERY,
        max_history: int = MAX_HISTORY,
    ):
        self.backend = backend
        self.repo = repo
        self.learner = learner
        self.retriever = retriever or NullRetriever()
        self.temperature = temperature
        self.assess_every = assess_every
        self.max_history = max_history
        self.mode = mode
        self.history: list[Message] = []
        self.hint_level = 1
        self.turns_since_assessment = 0
        if session_id is None:
            self.session_id = repo.create_session(learner.id, mode.value)
        else:
            self._load(session_id)

    # --- セッション管理 -----------------------------------------------
    def _load(self, session_id: int) -> None:
        if not self.repo.session_belongs_to(session_id, self.learner.id):
            raise ValueError(f"セッション {session_id} が見つかりません")
        stored = self.repo.get_messages(session_id)
        self.session_id = session_id
        self.history = [{"role": m.role, "content": m.content} for m in stored]
        if stored:
            self.mode = Mode(stored[-1].mode)

    def new_session(self) -> None:
        self.session_id = self.repo.create_session(self.learner.id, self.mode.value)
        self.history = []
        self.hint_level = 1
        self.turns_since_assessment = 0

    def resume(self, session_id: int) -> None:
        self._load(session_id)
        self.hint_level = 1
        self.turns_since_assessment = 0

    def set_mode(self, mode: Mode) -> None:
        if mode != self.mode:
            self.mode = mode
            self.hint_level = 1
            self.turns_since_assessment = 0

    def set_hint_level(self, level: int) -> None:
        if not 1 <= level <= MAX_HINT_LEVEL:
            raise ValueError(f"ヒント段階は 1〜{MAX_HINT_LEVEL} で指定してください")
        self.hint_level = level

    def refresh_learner(self, learner: Learner) -> None:
        self.learner = learner

    # --- 対話 ---------------------------------------------------------
    def build_messages(self, user_text: str) -> list[Message]:
        parts = [system_prompt(self.mode, self.hint_level)]
        parts.append(
            build_profile_prompt(
                self.learner,
                self.repo.get_mastery(self.learner.id),
                self.repo.get_weaknesses(self.learner.id),
            )
        )
        docs = self.retriever.retrieve(user_text)
        if docs:
            refs = "\n".join(f"- {d}" for d in docs)
            parts.append(f"【参考資料】次の資料を優先して使い、資料にないことは推測と明示してください。\n{refs}")
        system: Message = {"role": "system", "content": "\n\n".join(parts)}
        reminder: Message = {"role": "system", "content": mode_reminder(self.mode, self.hint_level)}
        recent = self.history[-self.max_history :] if self.max_history > 0 else []
        return [system, *recent, reminder, {"role": "user", "content": user_text}]

    def ask(self, user_text: str) -> Iterator[str]:
        """返答を断片ごとに yield する。最後まで受け取れたときだけ会話を保存する。"""
        text = user_text.strip()
        if not text:
            raise ValueError("メッセージが空です")
        temperature = self.temperature if self.temperature is not None else MODE_SPECS[self.mode].temperature
        messages = self.build_messages(text)

        parts: list[str] = []
        for chunk in self.backend.chat_stream(messages, temperature=temperature):
            parts.append(chunk)
            yield chunk
        reply = "".join(parts).strip()

        self.repo.add_turn(self.session_id, self.mode.value, text, reply)
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        if self.mode is Mode.HINT:
            self.hint_level = min(self.hint_level + 1, MAX_HINT_LEVEL)
        if self.mode is Mode.TEACHER:
            self.turns_since_assessment += 1

    # --- 理解度評価 ---------------------------------------------------
    def should_assess(self) -> bool:
        return self.mode is Mode.TEACHER and self.turns_since_assessment >= self.assess_every

    def maybe_assess(self) -> AssessmentOutcome | None:
        """先生モードで一定回数答えたら、自動で評価する。"""
        return self.evaluate() if self.should_assess() else None

    def evaluate(self) -> AssessmentOutcome | None:
        """直近の会話で理解度を評価し、記録する。評価できなければ None。"""
        evaluated = assess(self.backend, self.history[-self.max_history :])
        if evaluated is None:
            return None
        result, raw = evaluated
        current = self.repo.get_mastery(self.learner.id, result.subject, result.unit)
        new_score = blend_score(current[0].score if current else None, result.score)
        self.repo.save_assessment(
            learner_id=self.learner.id,
            session_id=self.session_id,
            subject=result.subject,
            unit=result.unit,
            score=result.score,
            new_mastery_score=new_score,
            weaknesses=result.weaknesses,
            rationale=result.rationale,
            raw_json=to_json(raw),
        )
        self.turns_since_assessment = 0
        return AssessmentOutcome(result, new_score)
