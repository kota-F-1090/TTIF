"""勉強記録(study_sessions 表)の保存と集計。

他の機能(ホーム画面・学習記録・スケジュール)は、ここの get_ 関数を呼べば
勉強時間を取得できる。SQL を直接書く必要はない。
"""
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from core.database import get_connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS study_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id      INTEGER NOT NULL REFERENCES subjects(id),
    started_at      TEXT    NOT NULL,              -- 'YYYY-MM-DD HH:MM:SS'
    ended_at        TEXT    NOT NULL,
    planned_minutes INTEGER NOT NULL,              -- 設定した時間
    actual_seconds  INTEGER NOT NULL CHECK (actual_seconds >= 0),  -- 実際に勉強した時間
    status          TEXT    NOT NULL CHECK (status IN ('completed', 'stopped'))
);
CREATE INDEX IF NOT EXISTS idx_study_sessions_started_at ON study_sessions(started_at);
"""

MIN_RECORD_SECONDS = 60  # これより短い計測は誤操作とみなして記録しない

_DT_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class SubjectTotal:
    subject_id: int
    name: str
    color: str
    seconds: int


@dataclass(frozen=True)
class SessionRecord:
    id: int
    subject_name: str
    subject_color: str
    started_at: datetime
    planned_minutes: int
    actual_seconds: int
    completed: bool


def init_schema() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


# ---- 保存 ----
def save_session(
    subject_id: int,
    started_at: datetime,
    ended_at: datetime,
    planned_minutes: int,
    actual_seconds: int,
    completed: bool,
) -> Optional[int]:
    """1回分の勉強を保存して id を返す。短すぎる場合は保存せず None を返す。"""
    if actual_seconds < MIN_RECORD_SECONDS:
        return None
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO study_sessions
               (subject_id, started_at, ended_at, planned_minutes, actual_seconds, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                subject_id,
                started_at.strftime(_DT_FORMAT),
                ended_at.strftime(_DT_FORMAT),
                planned_minutes,
                int(actual_seconds),
                "completed" if completed else "stopped",
            ),
        )
        return cur.lastrowid


def delete_session(session_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM study_sessions WHERE id = ?", (session_id,))



def count_sessions_for_subject(subject_id: int) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE subject_id = ?", (subject_id,)
        ).fetchone()[0]


def delete_subject_with_sessions(subject_id: int) -> None:
    """教科と、その教科の勉強記録をまとめて削除する。

    1つの接続(トランザクション)で行うので、途中で失敗したら両方とも元に戻る。
    他の機能(スケジュールなど)がこの教科を使っている場合は ValueError。
    """
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM study_sessions WHERE subject_id = ?", (subject_id,))
            conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    except sqlite3.IntegrityError:
        raise ValueError("この教科は他の機能で使われているため削除できません") from None

# ---- 集計(他の機能から使う想定の公開関数) ----
def _range_params(start: date, end: date) -> tuple[str, str]:
    """start〜end(両端を含む)を SQL の比較用文字列にする。"""
    return f"{start.isoformat()} 00:00:00", f"{(end + timedelta(days=1)).isoformat()} 00:00:00"


def get_total_seconds(start: date, end: date) -> int:
    """期間内の合計勉強秒数。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(actual_seconds), 0) FROM study_sessions"
            " WHERE started_at >= ? AND started_at < ?",
            _range_params(start, end),
        ).fetchone()
    return row[0]


def get_today_total_seconds(today: Optional[date] = None) -> int:
    today = today or date.today()
    return get_total_seconds(today, today)


def get_totals_by_subject(start: date, end: date) -> list[SubjectTotal]:
    """期間内の教科別合計(多い順)。勉強していない教科は含まない。"""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT s.id, s.name, s.color, SUM(ss.actual_seconds) AS total
               FROM study_sessions ss JOIN subjects s ON s.id = ss.subject_id
               WHERE ss.started_at >= ? AND ss.started_at < ?
               GROUP BY s.id ORDER BY total DESC""",
            _range_params(start, end),
        ).fetchall()
    return [SubjectTotal(r["id"], r["name"], r["color"], r["total"]) for r in rows]


def get_daily_totals(start: date, end: date) -> list[tuple[date, int]]:
    """日ごとの合計。勉強しなかった日も 0 として含める(グラフで日が抜けないように)。"""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT substr(started_at, 1, 10) AS day, SUM(actual_seconds) AS total
               FROM study_sessions WHERE started_at >= ? AND started_at < ?
               GROUP BY day""",
            _range_params(start, end),
        ).fetchall()
    by_day = {r["day"]: r["total"] for r in rows}
    days = (end - start).days + 1
    return [
        (d, by_day.get(d.isoformat(), 0))
        for d in (start + timedelta(days=i) for i in range(days))
    ]


def week_start(d: date) -> date:
    """その日を含む週の月曜日。"""
    return d - timedelta(days=d.weekday())


def get_weekly_totals(weeks: int = 8, today: Optional[date] = None) -> list[tuple[date, int]]:
    """直近 weeks 週の週ごとの合計。(週の月曜日, 秒数) のリストで古い順。"""
    today = today or date.today()
    first_monday = week_start(today) - timedelta(weeks=weeks - 1)
    daily = get_daily_totals(first_monday, week_start(today) + timedelta(days=6))
    totals = [0] * weeks
    for d, seconds in daily:
        totals[(d - first_monday).days // 7] += seconds
    return [(first_monday + timedelta(weeks=i), totals[i]) for i in range(weeks)]


def list_recent_sessions(limit: int = 20) -> list[SessionRecord]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ss.id, s.name, s.color, ss.started_at, ss.planned_minutes,
                      ss.actual_seconds, ss.status
               FROM study_sessions ss JOIN subjects s ON s.id = ss.subject_id
               ORDER BY ss.started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        SessionRecord(
            r["id"], r["name"], r["color"],
            datetime.strptime(r["started_at"], _DT_FORMAT),
            r["planned_minutes"], r["actual_seconds"], r["status"] == "completed",
        )
        for r in rows
    ]
