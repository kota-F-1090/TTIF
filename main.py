"""TTIF の起動ファイル。

今はタイマー機能だけを表示している。
班で合体するときは、ここに各機能の画面とナビゲーション(画面切り替え)を追加する。
"""
import flet as ft

from core import theme
from core.database import init_db
from features import timer


def main(page: ft.Page) -> None:
    page.title = "TTIF"
    page.theme = theme.app_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = theme.GRAY_BG
    page.padding = 0
    page.window.width = 460
    page.window.height = 860

    init_db()
    timer.init_schema()

    header = ft.Text("TTIF", size=26, weight=ft.FontWeight.BOLD, color=theme.LAVENDER_DEEP)
    page.add(
        ft.SafeArea(
            ft.Container(
                content=ft.Column([header, timer.build_timer_view(page)], spacing=16),
                padding=20,
                width=520,  # スマホくらいの幅に収めて読みやすくする
            ),
            expand=True,
        )
    )
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.update()


if __name__ == "__main__":
    ft.run(main)
