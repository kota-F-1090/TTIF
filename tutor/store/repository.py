"""DB の読み書きをまとめた窓口。SQL はこのファイルの外に出さない。"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Learner:
    id: int
    name: str
    level: str
    style: str


@dataclass(frozen=True)
class StoredMessage:
    id: int
    role: str
    content: str
    mode: str
    created_at: str


@dataclass(frozen=True)
class SessionInfo:
    id: int
    mode: str
    subject: str
    unit: str
    started_at: str
    updated_at: str
    message_count: int
    title: str  # 最初の発言の冒頭


@dataclass(frozen=True)
class Mastery:
    subject: str
    unit: str
    score: float
    attempts: int
    updated_at: str


@dataclass(frozen=True)
class Weakness:
    subject: str
    unit: str
    note: str
    count: int
    last_seen: str


class Repository:
    def __init__(self, conn: sqlite3.Connection, now: Callable[[], str] = _utc_now):
        self.conn = conn
        self.now = now

    # --- 学習者 -------------------------------------------------------
    def get_or_create_learner(self, name: str) -> Learner:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO learners (name, created_at) VALUES (?, ?)", (name, self.now())
            )
        row = self.conn.execute(
            "SELECT id, name, level, style FROM learners WHERE name = ?", (name,)
        ).fetchone()
        return Learner(**dict(row))

    def update_learner(self, learner_id: int, *, level: str | None = None, style: str | None = None) -> Learner:
        with self.conn:
            if level is not None:
                self.conn.execute("UPDATE learners SET level = ? WHERE id = ?", (level, learner_id))
            if style is not None:
                self.conn.execute("UPDATE learners SET style = ? WHERE id = ?", (style, learner_id))
        row = self.conn.execute(
            "SELECT id, name, level, style FROM learners WHERE id = ?", (learner_id,)
        ).fetchone()
        return Learner(**dict(row))

    # --- セッションと会話 ---------------------------------------------
    def create_session(self, learner_id: int, mode: str) -> int:
        now = self.now()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions (learner_id, mode, started_at, updated_at) VALUES (?, ?, ?, ?)",
                (learner_id, mode, now, now),
            )
        return cur.lastrowid

    def session_belongs_to(self, session_id: int, learner_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sessions WHERE id = ? AND learner_id = ?", (session_id, learner_id)
        ).fetchone()
        return row is not None

    def latest_session_id(self, learner_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM sessions WHERE learner_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
            (learner_id,),
        ).fetchone()
        return row["id"] if row else None

    def add_turn(self, session_id: int, mode: str, user: str, assistant: str) -> None:
        """学習者の発言と AI の返答を1組で保存する(片方だけ残ることはない)。"""
        now = self.now()
        with self.conn:
            self.conn.executemany(
                "INSERT INTO messages (session_id, role, content, mode, created_at) VALUES (?, ?, ?, ?, ?)",
                [(session_id, "user", user, mode, now), (session_id, "assistant", assistant, mode, now)],
            )
            self.conn.execute(
                "UPDATE sessions SET mode = ?, updated_at = ? WHERE id = ?", (mode, now, session_id)
            )

    def get_messages(self, session_id: int) -> list[StoredMessage]:
        rows = self.conn.execute(
            "SELECT id, role, content, mode, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [StoredMessage(**dict(r)) for r in rows]

    def set_session_topic(self, session_id: int, subject: str, unit: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET subject = ?, unit = ? WHERE id = ?", (subject, unit, session_id)
            )

    def list_sessions(self, learner_id: int, limit: int = 10) -> list[SessionInfo]:
        rows = self.conn.execute(
            """
            SELECT s.id, s.mode, s.subject, s.unit, s.started_at, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count,
                   COALESCE((SELECT substr(m.content, 1, 30) FROM messages m
                             WHERE m.session_id = s.id AND m.role = 'user'
                             ORDER BY m.id LIMIT 1), '') AS title
            FROM sessions s
            WHERE s.learner_id = ?
            ORDER BY s.updated_at DESC, s.id DESC
            LIMIT ?
            """,
            (learner_id, limit),
        ).fetchall()
        return [SessionInfo(**dict(r)) for r in rows]

    # --- 理解度・苦手分野 ---------------------------------------------
    def get_mastery(self, learner_id: int, subject: str | None = None, unit: str | None = None) -> list[Mastery]:
        sql = "SELECT subject, unit, score, attempts, updated_at FROM mastery WHERE learner_id = ?"
        args: list = [learner_id]
        if subject is not None:
            sql += " AND subject = ?"
            args.append(subject)
        if unit is not None:
            sql += " AND unit = ?"
            args.append(unit)
        sql += " ORDER BY score ASC, subject, unit"
        return [Mastery(**dict(r)) for r in self.conn.execute(sql, args).fetchall()]

    def get_weaknesses(self, learner_id: int, limit: int = 5) -> list[Weakness]:
        rows = self.conn.execute(
            """
            SELECT subject, unit, note, count, last_seen FROM weaknesses
            WHERE learner_id = ? ORDER BY count DESC, last_seen DESC LIMIT ?
            """,
            (learner_id, limit),
        ).fetchall()
        return [Weakness(**dict(r)) for r in rows]

    def save_assessment(
        self,
        *,
        learner_id: int,
        session_id: int,
        subject: str,
        unit: str,
        score: float,
        new_mastery_score: float,
        weaknesses: list[str],
        rationale: str,
        raw_json: str,
    ) -> None:
        """評価1件を保存し、理解度と苦手分野を同じトランザクションで更新する。"""
        now = self.now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO assessments (session_id, subject, unit, score, rationale, raw_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, subject, unit, score, rationale, raw_json, now),
            )
            self.conn.execute(
                """INSERT INTO mastery (learner_id, subject, unit, score, attempts, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?)
                   ON CONFLICT (learner_id, subject, unit)
                   DO UPDATE SET score = excluded.score, attempts = attempts + 1,
                                 updated_at = excluded.updated_at""",
                (learner_id, subject, unit, new_mastery_score, now),
            )
            self.conn.executemany(
                """INSERT INTO weaknesses (learner_id, subject, unit, note, last_seen)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (learner_id, subject, unit, note)
                   DO UPDATE SET count = count + 1, last_seen = excluded.last_seen""",
                [(learner_id, subject, unit, note, now) for note in weaknesses],
            )
            self.conn.execute(
                "UPDATE sessions SET subject = ?, unit = ? WHERE id = ?", (subject, unit, session_id)
            )
