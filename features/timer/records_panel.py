"""学習記録画面(今日・今週の合計、日別/週別グラフ、教科別、最近の記録)。

グラフは色付きの Container の高さで棒を表現している(追加ライブラリ不要)。
"""
from datetime import date, timedelta

import flet as ft

from core import theme
from features.timer import repository
from features.timer.formatting import format_duration

CHART_HEIGHT = 140
WEEKDAYS = "月火水木金土日"


def bar_chart(items: list[tuple[str, int]], highlight_last: bool = True) -> ft.Control:
    """(ラベル, 秒数) のリストから縦棒グラフを作る。"""
    peak = max((s for _, s in items), default=0)
    bars = []
    for i, (label, seconds) in enumerate(items):
        ratio = seconds / peak if peak else 0
        is_last = highlight_last and i == len(items) - 1
        bars.append(
            ft.Column(
                [
                    ft.Text(f"{seconds // 60}" if seconds else "", size=10, color=theme.TEXT_SUB),
                    ft.Container(
                        height=max(4, ratio * CHART_HEIGHT),
                        width=22,
                        border_radius=8,
                        bgcolor=theme.PINK_DEEP if is_last else (theme.LAVENDER if seconds else theme.GRAY_LINE),
                        tooltip=format_duration(seconds),
                    ),
                    ft.Text(label, size=11, color=theme.TEXT if is_last else theme.TEXT_SUB),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.END,
                expand=True,
            )
        )
    return ft.Container(
        content=ft.Row(bars, vertical_alignment=ft.CrossAxisAlignment.END, spacing=4),
        height=CHART_HEIGHT + 44,
    )


def _summary_tile(title: str, value: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(title, size=12, color=theme.TEXT_SUB),
                ft.Text(value, size=22, weight=ft.FontWeight.W_600, color=theme.TEXT),
            ],
            spacing=4,
            tight=True,
        ),
        bgcolor=color,
        border_radius=16,
        padding=16,
        expand=True,
    )


def _section_title(text: str) -> ft.Text:
    return ft.Text(text, size=15, weight=ft.FontWeight.W_600, color=theme.TEXT)


class RecordsPanel:
    def __init__(self, page: ft.Page):
        self.page = page
        self.mode = "daily"  # "daily"(日別) または "weekly"(週別)
        self.root = ft.Column(spacing=16)

    def refresh(self) -> None:
        """DB から最新の記録を読み直して画面を作り直す。"""
        try:
            self.root.controls = self._build_contents()
        except Exception as err:
            self.root.controls = [theme.card(ft.Text(f"記録を読み込めませんでした: {err}", color=theme.PINK_DEEP))]

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.refresh()
        self.page.update()

    def _build_contents(self) -> list[ft.Control]:
        today = date.today()
        monday = repository.week_start(today)
        today_total = repository.get_today_total_seconds(today)
        week_total = repository.get_total_seconds(monday, today)

        summary = ft.Row(
            [
                _summary_tile("今日", format_duration(today_total), theme.PINK),
                _summary_tile("今週", format_duration(week_total), theme.LAVENDER),
            ],
            spacing=12,
        )

        if self.mode == "daily":
            daily = repository.get_daily_totals(today - timedelta(days=6), today)
            chart_items = [(f"{d.day}({WEEKDAYS[d.weekday()]})", s) for d, s in daily]
            chart_note = "直近7日間(分)"
            subject_start = today - timedelta(days=6)
        else:
            weekly = repository.get_weekly_totals(8, today)
            chart_items = [(f"{d.month}/{d.day}~", s) for d, s in weekly]
            chart_note = "直近8週間(分)・週の始まりは月曜"
            subject_start = repository.week_start(today) - timedelta(weeks=7)

        chart_card = theme.card(
            ft.Column(
                [
                    ft.Row(
                        [_section_title("勉強時間"), self._mode_toggle()],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(chart_note, size=11, color=theme.TEXT_SUB),
                    bar_chart(chart_items),
                ],
                spacing=8,
            )
        )

        return [
            summary,
            chart_card,
            theme.card(self._subject_breakdown(subject_start, today)),
            theme.card(self._recent_list()),
        ]

    def _mode_toggle(self) -> ft.Control:
        def pill(label: str, mode: str) -> ft.Container:
            active = self.mode == mode
            return ft.Container(
                content=ft.Text(label, size=12, color=theme.WHITE if active else theme.TEXT_SUB),
                bgcolor=theme.LAVENDER_DEEP if active else None,
                border_radius=14,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                on_click=lambda _: self._set_mode(mode),
            )

        return ft.Container(
            content=ft.Row([pill("日別", "daily"), pill("週別", "weekly")], spacing=0, tight=True),
            bgcolor=theme.GRAY_BG,
            border_radius=16,
            padding=3,
        )

    def _subject_breakdown(self, start: date, end: date) -> ft.Control:
        totals = repository.get_totals_by_subject(start, end)
        period = "直近7日間" if self.mode == "daily" else "直近8週間"
        rows: list[ft.Control] = [_section_title("教科別"), ft.Text(period, size=11, color=theme.TEXT_SUB)]
        if not totals:
            rows.append(ft.Text("まだ記録がありません", color=theme.TEXT_SUB))
        peak = max((t.seconds for t in totals), default=1)
        for t in totals:
            rows.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(t.name, size=13, color=theme.TEXT),
                                ft.Text(format_duration(t.seconds), size=13, color=theme.TEXT_SUB),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ProgressBar(
                            value=t.seconds / peak,
                            color=t.color,
                            bgcolor=theme.GRAY_BG,
                            bar_height=10,
                            border_radius=5,
                        ),
                    ],
                    spacing=4,
                )
            )
        return ft.Column(rows, spacing=10)

    def _recent_list(self) -> ft.Control:
        sessions = repository.list_recent_sessions(limit=15)
        rows: list[ft.Control] = [_section_title("最近の記録")]
        if not sessions:
            rows.append(ft.Text("タイマーで勉強すると、ここに記録が表示されます", color=theme.TEXT_SUB))
        for s in sessions:
            rows.append(
                ft.Row(
                    [
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=s.subject_color),
                        ft.Text(s.started_at.strftime("%m/%d %H:%M"), size=12, color=theme.TEXT_SUB, width=80),
                        ft.Text(s.subject_name, size=13, color=theme.TEXT, expand=True),
                        ft.Text(format_duration(s.actual_seconds), size=13, color=theme.TEXT),
                        ft.Text(
                            "完了" if s.completed else "途中",
                            size=11,
                            color=theme.PINK_DEEP if s.completed else theme.TEXT_SUB,
                            width=32,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_size=18,
                            icon_color=theme.TEXT_SUB,
                            tooltip="この記録を削除",
                            on_click=lambda _, sid=s.id: self._confirm_delete(sid),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        return ft.Column(rows, spacing=6)

    def _confirm_delete(self, session_id: int) -> None:
        def delete(_):
            self.page.pop_dialog()
            repository.delete_session(session_id)
            self.refresh()
            self.page.update()

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("記録を削除しますか？"),
                content=ft.Text("削除した記録は元に戻せません。"),
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda _: self.page.pop_dialog()),
                    ft.TextButton("削除", on_click=delete),
                ],
            )
        )
