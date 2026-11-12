import unittest

from tutor import Mode, TutorSession
from tutor.llm import FakeBackend, LLMError
from tutor.store import Repository, connect

VALID = {"subject": "数学", "unit": "二次関数", "score": 40, "weaknesses": ["平方完成"], "rationale": "r"}


class ListRetriever:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def retrieve(self, query, limit=3):
        self.queries.append(query)
        return self.docs


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(connect(":memory:"))
        self.addCleanup(self.repo.conn.close)
        self.learner = self.repo.get_or_create_learner("高橋")

    def make(self, replies=(), json_replies=(), **kw):
        self.backend = FakeBackend(list(replies), list(json_replies))
        return TutorSession(self.backend, self.repo, self.learner, **kw)

    def test_ask_streams_and_saves(self):
        s = self.make(["微分とは変化の割合です。"])
        chunks = list(s.ask("  微分とは?  "))
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), "微分とは変化の割合です。")
        saved = self.repo.get_messages(s.session_id)
        self.assertEqual([(m.role, m.content) for m in saved],
                         [("user", "微分とは?"), ("assistant", "微分とは変化の割合です。")])

    def test_empty_message_is_rejected(self):
        s = self.make()
        with self.assertRaises(ValueError):
            list(s.ask("   "))

    def test_system_prompt_reflects_mode_and_profile(self):
        self.repo.update_learner(self.learner.id, level="beginner")
        self.learner = self.repo.get_or_create_learner("高橋")
        s = self.make(["a"], mode=Mode.CORRECT)
        list(s.ask("この答案を見て"))
        system = self.backend.chat_calls[0][0]
        self.assertEqual(system["role"], "system")
        self.assertIn("【添削モード】", system["content"])
        self.assertIn("初学者", system["content"])

    def test_history_is_sent_on_next_turn_and_trimmed(self):
        s = self.make(["a1", "a2", "a3"], max_history=2)
        for q in ["q1", "q2", "q3"]:
            list(s.ask(q))
        last = self.backend.chat_calls[-1]
        self.assertEqual([m["content"] for m in last if m["role"] != "system"], ["q2", "a2", "q3"])

    def test_mode_reminder_is_placed_just_before_user_message(self):
        s = self.make(["a1", "h1"])
        list(s.ask("q1"))
        s.set_mode(Mode.HINT)
        list(s.ask("わかりません"))
        *_, reminder, user = self.backend.chat_calls[-1]
        self.assertEqual((reminder["role"], user["role"]), ("system", "user"))
        self.assertIn("【ヒントモード】", reminder["content"])
        self.assertIn("段階1", reminder["content"])

    def test_llm_error_saves_nothing(self):
        s = self.make([])  # 台本なし → LLMError
        with self.assertRaises(LLMError):
            list(s.ask("質問"))
        self.assertEqual(self.repo.get_messages(s.session_id), [])
        self.assertEqual(s.history, [])

    def test_resume_restores_history_and_mode(self):
        s = self.make(["a1"], mode=Mode.EXPLAIN)
        list(s.ask("q1"))
        resumed = TutorSession(FakeBackend(["a2"]), self.repo, self.learner, session_id=s.session_id)
        self.assertEqual(resumed.mode, Mode.EXPLAIN)
        self.assertEqual([m["content"] for m in resumed.history], ["q1", "a1"])
        list(resumed.ask("q2"))
        self.assertEqual(len(self.repo.get_messages(s.session_id)), 4)

    def test_cannot_resume_other_learners_session(self):
        other = self.repo.get_or_create_learner("谷内")
        sid = self.repo.create_session(other.id, "question")
        with self.assertRaises(ValueError):
            self.make(session_id=sid)

    def test_new_session(self):
        s = self.make(["a1"])
        list(s.ask("q1"))
        first = s.session_id
        s.new_session()
        self.assertNotEqual(s.session_id, first)
        self.assertEqual(s.history, [])

    def test_hint_level_rises_to_three_and_resets_on_mode_change(self):
        s = self.make(["h1", "h2", "h3", "h4"], mode=Mode.HINT)
        for _ in range(4):
            list(s.ask("わかりません"))
        levels = [call[0]["content"].split("現在のヒント段階: ")[1][0] for call in self.backend.chat_calls]
        self.assertEqual(levels, ["1", "2", "3", "3"])
        s.set_mode(Mode.QUESTION)
        s.set_mode(Mode.HINT)
        self.assertEqual(s.hint_level, 1)
        with self.assertRaises(ValueError):
            s.set_hint_level(4)

    def test_teacher_mode_assesses_every_n_turns(self):
        s = self.make(["t1", "t2", "t3", "t4", "t5", "t6"],
                      [VALID, {**VALID, "score": 80, "weaknesses": ["平方完成", "符号"]}],
                      mode=Mode.TEACHER, assess_every=3)
        outcomes = []
        for i in range(6):
            list(s.ask(f"答え{i}"))
            outcomes.append(s.maybe_assess())
        self.assertEqual([o is not None for o in outcomes], [False, False, True, False, False, True])
        self.assertEqual(outcomes[2].mastery_score, 40)
        self.assertEqual(outcomes[5].mastery_score, 64.0)  # 移動平均
        [m] = self.repo.get_mastery(self.learner.id)
        self.assertEqual((m.score, m.attempts), (64.0, 2))
        weak = {w.note: w.count for w in self.repo.get_weaknesses(self.learner.id)}
        self.assertEqual(weak, {"平方完成": 2, "符号": 1})

    def test_assessment_is_reflected_in_next_prompt(self):
        s = self.make(["t1", "t2"], [VALID], mode=Mode.TEACHER, assess_every=1)
        list(s.ask("答え"))
        s.maybe_assess()
        list(s.ask("次"))
        system = self.backend.chat_calls[-1][0]["content"]
        self.assertIn("理解が浅い単元: 数学/二次関数(40点)", system)
        self.assertIn("平方完成", system)

    def test_no_auto_assessment_outside_teacher_mode(self):
        s = self.make(["a"] * 5, mode=Mode.QUESTION, assess_every=1)
        list(s.ask("q"))
        self.assertIsNone(s.maybe_assess())
        self.assertEqual(self.backend.json_calls, [])

    def test_failed_assessment_records_nothing(self):
        s = self.make(["t1"], [LLMError("x"), LLMError("y")], mode=Mode.TEACHER, assess_every=1)
        list(s.ask("答え"))
        self.assertIsNone(s.maybe_assess())
        self.assertEqual(self.repo.get_mastery(self.learner.id), [])

    def test_retriever_documents_are_added(self):
        retriever = ListRetriever(["二次関数 y=a(x-p)^2+q の頂点は (p, q)"])
        s = self.make(["a"], retriever=retriever)
        list(s.ask("頂点は?"))
        self.assertEqual(retriever.queries, ["頂点は?"])
        self.assertIn("【参考資料】", self.backend.chat_calls[0][0]["content"])

    def test_no_reference_block_without_documents(self):
        s = self.make(["a"])
        list(s.ask("q"))
        self.assertNotIn("【参考資料】", self.backend.chat_calls[0][0]["content"])


if __name__ == "__main__":
    unittest.main()
