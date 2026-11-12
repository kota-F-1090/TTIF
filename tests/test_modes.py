import unittest

from tutor.modes import MODE_SPECS, Mode, load_prompt, parse_mode, system_prompt


class ModesTest(unittest.TestCase):
    def test_five_modes_are_defined(self):
        self.assertEqual(
            {m.value for m in MODE_SPECS}, {"question", "explain", "correct", "teacher", "hint"}
        )

    def test_parse_mode_accepts_english_and_japanese(self):
        self.assertIs(parse_mode("teacher"), Mode.TEACHER)
        self.assertIs(parse_mode(" 先生 "), Mode.TEACHER)
        self.assertIs(parse_mode("HINT"), Mode.HINT)
        self.assertIs(parse_mode("添削"), Mode.CORRECT)

    def test_parse_mode_rejects_unknown(self):
        with self.assertRaisesRegex(ValueError, "使えるモード"):
            parse_mode("雑談")

    def test_every_mode_has_a_prompt(self):
        common = load_prompt("common")
        for mode in Mode:
            text = system_prompt(mode)
            self.assertTrue(text.startswith(common))
            self.assertIn(f"【{MODE_SPECS[mode].label}モード】", text)

    def test_hint_level_is_inserted(self):
        text = system_prompt(Mode.HINT, hint_level=2)
        self.assertIn("現在のヒント段階: 2 / 3", text)
        self.assertNotIn("{hint_level}", text)


if __name__ == "__main__":
    unittest.main()
