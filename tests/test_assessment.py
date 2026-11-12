import unittest

from tutor.assessment import (
    ASSESSOR_PROMPT,
    assess,
    blend_score,
    build_assessment_messages,
    parse_assessment,
)
from tutor.llm import FakeBackend, LLMError

VALID = {"subject": "数学", "unit": "二次関数", "score": 72, "weaknesses": ["平方完成"], "rationale": "基本は理解"}
HISTORY = [
    {"role": "user", "content": "二次関数を教えて"},
    {"role": "assistant", "content": "頂点の求め方は?"},
    {"role": "user", "content": "平方完成します"},
]


class ParseAssessmentTest(unittest.TestCase):
    def test_valid(self):
        r = parse_assessment(VALID)
        self.assertEqual((r.subject, r.unit, r.score, r.weaknesses), ("数学", "二次関数", 72, ["平方完成"]))

    def test_float_score_is_rounded(self):
        self.assertEqual(parse_assessment({**VALID, "score": 71.6}).score, 72)

    def test_invalid_scores(self):
        for bad in [None, "70", True, -1, 101]:
            with self.subTest(score=bad), self.assertRaises(ValueError):
                parse_assessment({**VALID, "score": bad})

    def test_empty_subject_or_unit(self):
        for field in ("subject", "unit"):
            for bad in ["", "  ", None, 3]:
                with self.subTest(field=field, value=bad), self.assertRaises(ValueError):
                    parse_assessment({**VALID, field: bad})

    def test_weaknesses_are_cleaned(self):
        data = {**VALID, "weaknesses": [" 符号 ", "符号", "", 5, "a" * 100, "b", "c", "d"]}
        r = parse_assessment(data)
        self.assertEqual(r.weaknesses, ["符号", "a" * 40, "b"])  # 重複・空・非文字列を除き、最大3つ

    def test_weaknesses_must_be_list(self):
        with self.assertRaises(ValueError):
            parse_assessment({**VALID, "weaknesses": "符号"})

    def test_missing_rationale_is_allowed(self):
        data = dict(VALID)
        del data["rationale"]
        self.assertEqual(parse_assessment(data).rationale, "")


class AssessTest(unittest.TestCase):
    def test_transcript_contains_only_dialogue(self):
        msgs = build_assessment_messages([{"role": "system", "content": "秘密の指示"}, *HISTORY])
        self.assertEqual(msgs[0]["content"], ASSESSOR_PROMPT)
        self.assertNotIn("秘密の指示", msgs[1]["content"])
        self.assertIn("学習者: 平方完成します", msgs[1]["content"])
        self.assertIn("先生: 頂点の求め方は?", msgs[1]["content"])

    def test_success(self):
        backend = FakeBackend(json_replies=[VALID])
        result, raw = assess(backend, HISTORY)
        self.assertEqual(result.score, 72)
        self.assertEqual(raw, VALID)

    def test_retries_once_on_invalid_output(self):
        backend = FakeBackend(json_replies=[{"score": "bad"}, VALID])
        result, _ = assess(backend, HISTORY)
        self.assertEqual(result.unit, "二次関数")
        self.assertEqual(len(backend.json_calls), 2)

    def test_gives_up_after_retry(self):
        backend = FakeBackend(json_replies=[LLMError("x"), {"score": 500}, VALID])
        self.assertIsNone(assess(backend, HISTORY))
        self.assertEqual(len(backend.json_calls), 2)

    def test_no_learner_message_means_no_call(self):
        backend = FakeBackend(json_replies=[VALID])
        self.assertIsNone(assess(backend, [{"role": "assistant", "content": "何を学びますか?"}]))
        self.assertEqual(backend.json_calls, [])


class BlendScoreTest(unittest.TestCase):
    def test_first_score_is_used_as_is(self):
        self.assertEqual(blend_score(None, 55), 55)

    def test_new_score_weighs_more(self):
        self.assertEqual(blend_score(40, 80), 64.0)  # 40*0.4 + 80*0.6

    def test_clamped(self):
        self.assertEqual(blend_score(None, 120), 100)
        self.assertEqual(blend_score(None, -5), 0)


if __name__ == "__main__":
    unittest.main()
