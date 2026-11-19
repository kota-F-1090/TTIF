"""TTIF 全体で共有する SQLite データベースの接続と初期化。

各機能は get_connection() を使ってデータを読み書きします。
データは data/ttif.db という1つのファイルに保存されるので、
アプリを閉じても記録は消えません。
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ttif.db"

# 班全員で共有する表。教科は全機能で同じものを使う。
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL
);
"""

DEFAULT_SUBJECTS = [
    ("国語", "#F4A7B9"),
    ("数学", "#B9A7F4"),
    ("英語", "#A7D3F4"),
    ("理科", "#A7F4C8"),
    ("社会", "#F4D9A7"),
]


def db_path() -> Path:
    """DB ファイルの場所。テスト時は環境変数 TTIF_DB_PATH で差し替えられる。"""
    return Path(os.environ.get("TTIF_DB_PATH", DEFAULT_DB_PATH))


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """with 文で使う接続。正常終了なら保存(commit)、エラーなら取り消し(rollback)する。

    使い方:
        with get_connection() as conn:
            conn.execute("SELECT ...")
    """
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # 結果を row["name"] のように列名で読めるようにする
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """共有の表を作り、教科が空なら初期教科を入れる。何度呼んでも安全。"""
    with get_connection() as conn:
        conn.executescript(SHARED_SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0:
            conn.executemany("INSERT INTO subjects (name, color) VALUES (?, ?)", DEFAULT_SUBJECTS)
