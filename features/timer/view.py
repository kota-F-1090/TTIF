"""タイマー機能の画面全体。上部の切り替えで「タイマー」と「記録」を行き来する。"""
import flet as ft

from core import theme
from features.timer.records_panel import RecordsPanel
from features.timer.timer_panel import TimerPanel


def build_timer_view(page: ft.Page) -> ft.Control:
    """タイマー機能の画面を作って返す。main.py(班で合体する場所)から呼ばれる。"""
    records = RecordsPanel(page)
    timer = TimerPanel(page, on_saved=records.refresh)
    records.refresh()

    timer_area = ft.Container(content=timer.root, visible=True)
    records_area = ft.Container(content=records.root, visible=False)
    tabs: dict[str, ft.Container] = {}

    def select(name: str) -> None:
        timer_area.visible = name == "timer"
        records_area.visible = name == "records"
        if name == "records":
            records.refresh()
        for key, tab in tabs.items():
            active = key == name
            tab.bgcolor = theme.WHITE if active else None
            tab.content.color = theme.PINK_DEEP if active else theme.TEXT_SUB
        page.update()

    def tab(label: str, name: str) -> ft.Container:
        tabs[name] = ft.Container(
            content=ft.Text(label, size=14, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment.CENTER,
            border_radius=18,
            padding=ft.Padding.symmetric(vertical=10),
            expand=True,
            on_click=lambda _: select(name),
        )
        return tabs[name]

    switcher = ft.Container(
        content=ft.Row([tab("タイマー", "timer"), tab("学習記録", "records")], spacing=4),
        bgcolor=theme.PINK,
        border_radius=22,
        padding=4,
    )
    # 初期表示の見た目を整える(page.update はまだ呼べないので直接設定)
    for key, t in tabs.items():
        t.bgcolor = theme.WHITE if key == "timer" else None
        t.content.color = theme.PINK_DEEP if key == "timer" else theme.TEXT_SUB

    return ft.Column([switcher, timer_area, records_area], spacing=16)
