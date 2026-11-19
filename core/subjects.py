"""教科(subjects 表)の読み書き。タイマー・スケジュール・AI家庭教師で共通して使う。"""
import sqlite3
from dataclasses import dataclass

from core.database import get_connection

# 新しい教科に順番に割り当てるパステルカラー
_EXTRA_COLORS = ["#F7C6D9", "#D9C6F7", "#C6E3F7", "#C6F7DA", "#F7E6C6", "#E0E0E8"]


@dataclass(frozen=True)
class Subject:
    id: int
    name: str
    color: str


def list_subjects() -> list[Subject]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, color FROM subjects ORDER BY id").fetchall()
    return [Subject(r["id"], r["name"], r["color"]) for r in rows]


def add_subject(name: str) -> Subject:
    """教科を追加する。空の名前や重複は ValueError。"""
    name = name.strip()
    if not name:
        raise ValueError("教科名を入力してください")
    if len(name) > 20:
        raise ValueError("教科名は20文字以内にしてください")
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM subjects WHERE name = ?", (name,)).fetchone():
            raise ValueError(f"「{name}」はすでに登録されています")
        count = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        color = _EXTRA_COLORS[count % len(_EXTRA_COLORS)]
        cur = conn.execute("INSERT INTO subjects (name, color) VALUES (?, ?)", (name, color))
        return Subject(cur.lastrowid, name, color)


def delete_subject(subject_id: int) -> None:
    """教科を削除する。他の機能のデータがまだこの教科を使っている場合は ValueError。

    (各機能は、自分のデータを先に消してからこの関数を呼ぶ)
    """
    with get_connection() as conn:
        try:
            cur = conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        except sqlite3.IntegrityError:
            raise ValueError("この教科は他の機能で使われているため削除できません") from None
        if cur.rowcount == 0:
            raise ValueError("教科が見つかりません")
