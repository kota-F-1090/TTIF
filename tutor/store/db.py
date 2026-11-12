"""SQLite 接続とスキーマ管理。標準ライブラリのみ。

スキーマの版は PRAGMA user_version で管理する。変更するときは MIGRATIONS の末尾に
新しい SQL を足す(既存の要素は書き換えない)。
"""
import sqlite3
from pathlib import Path

MIGRATIONS: list[str] = [
    # --- v1 ---
    """
    CREATE TABLE learners (
        id         INTEGER PRIMARY KEY,
        name       TEXT NOT NULL UNIQUE,
        level      TEXT NOT NULL DEFAULT 'standard',
        style      TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE sessions (
        id         INTEGER PRIMARY KEY,
        learner_id INTEGER NOT NULL REFERENCES learners(id),
        mode       TEXT NOT NULL,
        subject    TEXT NOT NULL DEFAULT '',
        unit       TEXT NOT NULL DEFAULT '',
        started_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE messages (
        id         INTEGER PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES sessions(id),
        role       TEXT NOT NULL,
        content    TEXT NOT NULL,
        mode       TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_messages_session ON messages(session_id, id);
    CREATE TABLE mastery (
        learner_id INTEGER NOT NULL REFERENCES learners(id),
        subject    TEXT NOT NULL,
        unit       TEXT NOT NULL,
        score      REAL NOT NULL,
        attempts   INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (learner_id, subject, unit)
    );
    CREATE TABLE weaknesses (
        id         INTEGER PRIMARY KEY,
        learner_id INTEGER NOT NULL REFERENCES learners(id),
        subject    TEXT NOT NULL,
        unit       TEXT NOT NULL,
        note       TEXT NOT NULL,
        count      INTEGER NOT NULL DEFAULT 1,
        last_seen  TEXT NOT NULL,
        UNIQUE (learner_id, subject, unit, note)
    );
    CREATE TABLE assessments (
        id         INTEGER PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES sessions(id),
        subject    TEXT NOT NULL,
        unit       TEXT NOT NULL,
        score      REAL NOT NULL,
        rationale  TEXT NOT NULL,
        raw_json   TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
]


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRATIONS):
        raise RuntimeError(
            f"データベースの版 ({version}) がこのプログラム ({len(MIGRATIONS)}) より新しいです。"
        )
    for i in range(version, len(MIGRATIONS)):
        # executescript は暗黙に COMMIT するため、版の更新と同じスクリプトの中に含める
        conn.executescript(f"BEGIN;\n{MIGRATIONS[i]}\nPRAGMA user_version = {i + 1};\nCOMMIT;")


def connect(path: str) -> sqlite3.Connection:
    """DB を開く(なければ作る)。path が ':memory:' ならメモリ上に作る(テスト用)。"""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        migrate(conn)
    except Exception:
        conn.close()
        raise
    return conn
