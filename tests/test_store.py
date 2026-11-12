import sqlite3
import tempfile
import unittest
from pathlib import Path

from tutor.store import Repository, connect
from tutor.store.db import MIGRATIONS


class FakeClock:
    def __init__(self):
        self.t = 0

    def __call__(self) -> str:
        self.t += 1
        return f"2026-11-12T00:00:{self.t:02d}+00:00"


def make_repo(test: unittest.TestCase) -> Repository:
    repo = Repository(connect(":memory:"), now=FakeClock())
    test.addCleanup(repo.conn.close)
    return repo


class DbTest(unittest.TestCase):
    def test_migration_sets_version_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "sub" / "tutor.db")  # 親ディレクトリも作られること
            conn = connect(path)
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], len(MIGRATIONS))
            conn.close()
            conn = connect(path)  # 2回目は何もしない(エラーにならない)
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], len(MIGRATIONS))
            conn.close()

    def test_newer_database_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "tutor.db")
            raw = sqlite3.connect(path)
            raw.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
            raw.close()
            with self.assertRaisesRegex(RuntimeError, "新しい"):
                connect(path)

    def test_foreign_keys_are_enforced(self):
        repo = make_repo(self)
        with self.assertRaises(sqlite3.IntegrityError):
            repo.add_turn(999, "question", "a", "b")


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(self)
        self.learner = self.repo.get_or_create_learner("高橋")

    def test_get_or_create_learner_is_idempotent(self):
        again = self.repo.get_or_create_learner("高橋")
        self.assertEqual(again.id, self.learner.id)
        self.assertEqual(again.level, "standard")

    def test_update_learner(self):
        updated = self.repo.update_learner(self.learner.id, level="beginner", style="例え多め")
        self.assertEqual((updated.level, updated.style), ("beginner", "例え多め"))

    def test_turns_are_saved_in_order(self):
        sid = self.repo.create_session(self.learner.id, "question")
        self.repo.add_turn(sid, "question", "質問1", "回答1")
        self.repo.add_turn(sid, "hint", "質問2", "回答2")
        msgs = self.repo.get_messages(sid)
        self.assertEqual([m.content for m in msgs], ["質問1", "回答1", "質問2", "回答2"])
        self.assertEqual([m.role for m in msgs], ["user", "assistant"] * 2)
        self.assertEqual(msgs[-1].mode, "hint")

    def test_list_sessions_newest_first_with_title(self):
        s1 = self.repo.create_session(self.learner.id, "question")
        s2 = self.repo.create_session(self.learner.id, "explain")
        self.repo.add_turn(s1, "question", "二次関数の頂点の求め方を教えてください", "…")
        sessions = self.repo.list_sessions(self.learner.id)
        self.assertEqual([s.id for s in sessions], [s1, s2])  # s1 が後から更新された
        self.assertEqual(sessions[0].message_count, 2)
        self.assertEqual(sessions[0].mode, "question")
        self.assertTrue(sessions[0].title.startswith("二次関数"))
        self.assertEqual(sessions[1].title, "")
        self.assertEqual(self.repo.latest_session_id(self.learner.id), s1)

    def test_sessions_are_separated_by_learner(self):
        other = self.repo.get_or_create_learner("谷内")
        sid = self.repo.create_session(other.id, "question")
        self.assertFalse(self.repo.session_belongs_to(sid, self.learner.id))
        self.assertEqual(self.repo.list_sessions(self.learner.id), [])
        self.assertIsNone(self.repo.latest_session_id(self.learner.id))

    def test_save_assessment_updates_mastery_and_weaknesses(self):
        sid = self.repo.create_session(self.learner.id, "teacher")
        common = dict(learner_id=self.learner.id, session_id=sid, subject="数学", unit="二次関数",
                      rationale="r", raw_json="{}")
        self.repo.save_assessment(score=40, new_mastery_score=40, weaknesses=["平方完成"], **common)
        self.repo.save_assessment(score=80, new_mastery_score=64, weaknesses=["平方完成", "符号"], **common)

        [m] = self.repo.get_mastery(self.learner.id)
        self.assertEqual((m.subject, m.unit, m.score, m.attempts), ("数学", "二次関数", 64, 2))
        weak = self.repo.get_weaknesses(self.learner.id)
        self.assertEqual([(w.note, w.count) for w in weak], [("平方完成", 2), ("符号", 1)])
        info = self.repo.list_sessions(self.learner.id)[0]
        self.assertEqual((info.subject, info.unit), ("数学", "二次関数"))
        count = self.repo.conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
        self.assertEqual(count, 2)

    def test_get_mastery_filters(self):
        sid = self.repo.create_session(self.learner.id, "teacher")
        for subject, unit, score in [("数学", "微分", 90), ("物理", "力学", 30)]:
            self.repo.save_assessment(learner_id=self.learner.id, session_id=sid, subject=subject, unit=unit,
                                      score=score, new_mastery_score=score, weaknesses=[], rationale="",
                                      raw_json="{}")
        self.assertEqual([m.unit for m in self.repo.get_mastery(self.learner.id)], ["力学", "微分"])
        self.assertEqual([m.unit for m in self.repo.get_mastery(self.learner.id, "数学", "微分")], ["微分"])
        self.assertEqual(self.repo.get_mastery(self.learner.id, "数学", "積分"), [])


if __name__ == "__main__":
    unittest.main()
