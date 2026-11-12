import unittest

from tutor.profile import LEVELS, build_profile_prompt, parse_level
from tutor.store import Learner, Mastery, Weakness


def learner(level="standard", style=""):
    return Learner(id=1, name="高橋", level=level, style=style)


class ProfileTest(unittest.TestCase):
    def test_level_only(self):
        text = build_profile_prompt(learner("beginner"), [], [])
        self.assertIn(LEVELS["beginner"], text)
        self.assertNotIn("理解が浅い", text)
        self.assertNotIn("得意", text)

    def test_style_is_included(self):
        self.assertIn("本人の希望: 図や例え多め", build_profile_prompt(learner(style="図や例え多め"), [], []))

    def test_low_high_and_weaknesses(self):
        mastery = [
            Mastery("数学", "二次関数", 35, 2, ""),
            Mastery("数学", "微分", 70, 1, ""),
            Mastery("物理", "力学", 92, 3, ""),
        ]
        weak = [Weakness("数学", "二次関数", "平方完成", 3, "")]
        text = build_profile_prompt(learner(), mastery, weak)
        self.assertIn("理解が浅い単元: 数学/二次関数(35点)", text)
        self.assertIn("得意な単元: 物理/力学", text)
        self.assertNotIn("微分", text)  # 中間の点数は書かない
        self.assertIn("平方完成(数学/二次関数)", text)

    def test_unknown_level_falls_back_to_standard(self):
        self.assertIn(LEVELS["standard"], build_profile_prompt(learner("???"), [], []))

    def test_parse_level(self):
        self.assertEqual(parse_level("初級"), "beginner")
        self.assertEqual(parse_level("ADVANCED"), "advanced")
        with self.assertRaises(ValueError):
            parse_level("最強")


if __name__ == "__main__":
    unittest.main()
