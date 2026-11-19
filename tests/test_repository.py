"""勉強記録の保存・集計のテスト。一時的な DB ファイルを使うので本番データには触れない。"""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from core.database import init_db
from core.subjects import add_subject, delete_subject, list_subjects
from features.timer import repository


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TTIF_DB_PATH"] = str(Path(self.tmp.name) / "test.db")
        init_db()
        repository.init_schema()
        subjects = {s.name: s.id for s in list_subjects()}
        self.math, self.english = subjects["数学"], subjects["英語"]

    def tearDown(self):
        del os.environ["TTIF_DB_PATH"]
        self.tmp.cleanup()

    def _save(self, subject_id, day: date, minutes: int, hour: int = 19):
        start = datetime(day.year, day.month, day.day, hour, 0)
        return repository.save_session(
            subject_id, start, start + timedelta(minutes=minutes), minutes, minutes * 60, True
        )

    def test_short_session_is_not_saved(self):
        start = datetime(2026, 11, 12, 19, 0)
        self.assertIsNone(repository.save_session(self.math, start, start, 25, 59, False))
        self.assertEqual(repository.list_recent_sessions(), [])

    def test_daily_totals_include_zero_days(self):
        d = date(2026, 11, 12)
        self._save(self.math, d, 25)
        self._save(self.english, d, 50, hour=20)
        self._save(self.math, d - timedelta(days=2), 30)
        daily = repository.get_daily_totals(d - timedelta(days=2), d)
        self.assertEqual([s for _, s in daily], [30 * 60, 0, 75 * 60])
        self.assertEqual(repository.get_today_total_seconds(d), 75 * 60)

    def test_totals_by_subject(self):
        d = date(2026, 11, 12)
        self._save(self.math, d, 25)
        self._save(self.math, d, 25, hour=21)
        self._save(self.english, d, 30, hour=20)
        totals = repository.get_totals_by_subject(d, d)
        self.assertEqual([(t.name, t.seconds) for t in totals], [("数学", 3000), ("英語", 1800)])

    def test_weekly_totals_start_on_monday(self):
        today = date(2026, 11, 12)  # 木曜日
        self._save(self.math, date(2026, 11, 9), 60)   # 今週の月曜
        self._save(self.math, date(2026, 11, 8), 30)   # 先週の日曜
        weekly = repository.get_weekly_totals(2, today)
        self.assertEqual(weekly, [(date(2026, 11, 2), 1800), (date(2026, 11, 9), 3600)])

    def test_delete_session(self):
        sid = self._save(self.math, date(2026, 11, 12), 25)
        repository.delete_session(sid)
        self.assertEqual(repository.list_recent_sessions(), [])

    def test_delete_subject_with_sessions(self):
        self._save(self.math, date(2026, 11, 12), 25)
        self._save(self.english, date(2026, 11, 12), 30, hour=20)
        self.assertEqual(repository.count_sessions_for_subject(self.math), 1)
        repository.delete_subject_with_sessions(self.math)
        self.assertNotIn("数学", [s.name for s in list_subjects()])
        self.assertEqual([s.subject_name for s in repository.list_recent_sessions()], ["英語"])

    def test_delete_subject_used_elsewhere_is_rolled_back(self):
        # 他の機能の表がこの教科を参照している状況を再現
        from core.database import get_connection
        with get_connection() as conn:
            conn.execute("CREATE TABLE other (subject_id INTEGER REFERENCES subjects(id))")
            conn.execute("INSERT INTO other VALUES (?)", (self.math,))
        self._save(self.math, date(2026, 11, 12), 25)
        with self.assertRaises(ValueError):
            repository.delete_subject_with_sessions(self.math)
        # 失敗したので勉強記録も残っている
        self.assertEqual(repository.count_sessions_for_subject(self.math), 1)
        with self.assertRaises(ValueError):
            delete_subject(self.math)

    def test_delete_unused_subject(self):
        subject = add_subject("間違い")
        delete_subject(subject.id)
        self.assertNotIn("間違い", [s.name for s in list_subjects()])

    def test_add_subject_validation(self):
        self.assertEqual(add_subject("情報").name, "情報")
        with self.assertRaises(ValueError):
            add_subject("数学")
        with self.assertRaises(ValueError):
            add_subject("  ")


if __name__ == "__main__":
    unittest.main()
