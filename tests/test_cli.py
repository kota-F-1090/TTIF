import unittest

from tutor import Mode, TutorSession
from tutor.cli import Cli
from tutor.llm import FakeBackend
from tutor.store import Repository, connect

VALID = {"subject": "数学", "unit": "二次関数", "score": 55, "weaknesses": ["符号"], "rationale": "途中まで正しい"}


class CliTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(connect(":memory:"))
        self.addCleanup(self.repo.conn.close)
        learner = self.repo.get_or_create_learner("高橋")
        self.backend = FakeBackend(["こんにちは!", "t1", "t2", "t3"], [VALID])
        self.session = TutorSession(self.backend, self.repo, learner, assess_every=3)
        self.out: list[str] = []
        self.cli = Cli(self.session, write=self.out.append)

    def text(self) -> str:
        return "".join(self.out)

    def test_chat_prints_streamed_reply(self):
        self.assertTrue(self.cli.handle("やあ"))
        self.assertIn("AI> こんにちは!", self.text())

    def test_exit(self):
        self.assertFalse(self.cli.handle("/exit"))

    def test_mode_switch(self):
        self.cli.handle("/mode 先生")
        self.assertIs(self.session.mode, Mode.TEACHER)
        self.assertIn("先生モード", self.text())
        self.assertIn("[先生]", self.cli.prompt_label())

    def test_bad_input_shows_message_instead_of_crashing(self):
        for line in ["/mode 雑談", "/mode", "/hint x", "/level 最強", "/resume abc", "/resume 999", "/unknown"]:
            with self.subTest(line=line):
                self.assertTrue(self.cli.handle(line))
        self.assertIn("/help", self.text())

    def test_teacher_auto_assessment_and_profile(self):
        self.cli.handle("/mode teacher")
        for line in ["やあ", "答え1", "答え2"]:
            self.cli.handle(line)
        self.assertIn("[理解度] 数学 / 二次関数: 今回 55 点", self.text())
        self.out.clear()
        self.cli.handle("/profile")
        self.assertIn("数学 / 二次関数: 55 点(1 回評価)", self.text())
        self.assertIn("符号", self.text())

    def test_level_and_style(self):
        self.cli.handle("/level 上級")
        self.cli.handle("/style 例えを多めに")
        self.assertEqual(self.session.learner.level, "advanced")
        self.assertEqual(self.session.learner.style, "例えを多めに")

    def test_history_and_resume(self):
        self.cli.handle("最初の質問")
        first = self.session.session_id
        self.cli.handle("/new")
        self.out.clear()
        self.cli.handle("/history")
        self.assertIn("最初の質問", self.text())
        self.cli.handle(f"/resume {first}")
        self.assertEqual(self.session.session_id, first)
        self.assertEqual(len(self.session.history), 2)


if __name__ == "__main__":
    unittest.main()
