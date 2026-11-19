"""タイマーの動きのテスト。偽の時計を使うので、25分待たずに一瞬で終わる。

実行: python -m unittest discover tests
"""
import unittest

from features.timer.formatting import format_clock, format_duration
from features.timer.timer_logic import StudyTimer, TimerError, TimerState


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class StudyTimerTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.timer = StudyTimer(clock=self.clock)

    def test_countdown(self):
        self.timer.start(25)
        self.clock.advance(60)
        self.assertEqual(self.timer.elapsed_seconds, 60)
        self.assertEqual(self.timer.remaining_seconds, 24 * 60)

    def test_pause_excludes_paused_time(self):
        self.timer.start(25)
        self.clock.advance(100)
        self.timer.pause()
        self.clock.advance(500)  # 一時停止中は数えない
        self.assertEqual(self.timer.elapsed_seconds, 100)
        self.timer.resume()
        self.clock.advance(50)
        self.assertEqual(self.timer.elapsed_seconds, 150)

    def test_finishes_at_planned_time(self):
        self.timer.start(1)
        self.clock.advance(59)
        self.assertFalse(self.timer.check_finished())
        self.clock.advance(5)
        self.assertTrue(self.timer.check_finished())
        self.assertIs(self.timer.state, TimerState.FINISHED)
        self.assertEqual(self.timer.elapsed_seconds, 60)  # 設定時間を超えない
        self.assertEqual(self.timer.progress, 1.0)

    def test_invalid_operations(self):
        with self.assertRaises(TimerError):
            self.timer.pause()
        with self.assertRaises(ValueError):
            self.timer.start(0)
        with self.assertRaises(ValueError):
            self.timer.start(301)
        self.timer.start(25)
        with self.assertRaises(TimerError):
            self.timer.start(25)
        with self.assertRaises(TimerError):
            self.timer.resume()

    def test_reset(self):
        self.timer.start(25)
        self.clock.advance(30)
        self.timer.reset()
        self.assertIs(self.timer.state, TimerState.IDLE)
        self.assertEqual(self.timer.elapsed_seconds, 0)


class FormattingTest(unittest.TestCase):
    def test_format_clock(self):
        self.assertEqual(format_clock(1500), "25:00")
        self.assertEqual(format_clock(59), "00:59")
        self.assertEqual(format_clock(3725), "1:02:05")

    def test_format_duration(self):
        self.assertEqual(format_duration(1500), "25分")
        self.assertEqual(format_duration(3600), "1時間")
        self.assertEqual(format_duration(3900), "1時間5分")
        self.assertEqual(format_duration(30), "0分")


if __name__ == "__main__":
    unittest.main()
