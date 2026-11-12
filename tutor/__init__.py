"""TTIF AI家庭教師。

ライブラリとして使う例:
    from tutor import Mode, TutorSession
    from tutor.llm import OllamaBackend
    from tutor.store import Repository, connect

    repo = Repository(connect("data/tutor.db"))
    learner = repo.get_or_create_learner("高橋")
    session = TutorSession(OllamaBackend("qwen3:4b-instruct"), repo, learner, mode=Mode.EXPLAIN)
    for chunk in session.ask("微分とは何ですか?"):
        print(chunk, end="")
"""
from .modes import Mode
from .session import AssessmentOutcome, TutorSession

__all__ = ["Mode", "TutorSession", "AssessmentOutcome"]
