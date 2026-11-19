"""タイマー画面(教科選択・時間設定・カウントダウン・操作ボタン)。

動きは timer_logic.StudyTimer、保存は repository に任せ、
このファイルは「画面に表示する」「ボタンの操作を受け取る」ことだけを担当する。
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional

import flet as ft

from core import theme
from core.subjects import add_subject, list_subjects
from features.timer import repository
from features.timer.formatting import format_clock, format_duration
from features.timer.timer_logic import MAX_MINUTES, MIN_MINUTES, PRESET_MINUTES, StudyTimer, TimerState

RING_SIZE = 230
TICK_INTERVAL = 0.25  # 画面を更新する間隔(秒)


def _notify_sound() -> None:
    """終了音。Windows 以外や音が出せない環境では何もしない。"""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


class TimerPanel:
    def __init__(self, page: ft.Page, on_saved: Callable[[], None]):
        self.page = page
        self.on_saved = on_saved  # 記録を保存したら呼ぶ(記録画面の更新用)
        self.timer = StudyTimer()
        self.selected_minutes: Optional[int] = PRESET_MINUTES[0]
        self.subject_id: Optional[int] = None
        self._loop_id = 0  # 古い更新ループを止めるための番号

        self._build()
        self._load_subjects()
        self._render()

    # ------------------------------------------------------------------ 画面の組み立て
    def _build(self) -> None:
        self.subject_dropdown = ft.Dropdown(
            label="教科",
            expand=True,
            border=theme.input_border(),
            on_select=self._on_subject_select,
        )
        add_subject_btn = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=theme.LAVENDER_DEEP,
            tooltip="教科を追加",
            on_click=self._open_add_subject_dialog,
        )
        delete_subject_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_color=theme.TEXT_SUB,
            tooltip="選んでいる教科を削除",
            on_click=self._open_delete_subject_dialog,
        )

        self.preset_chips = {m: self._chip(f"{m}分", m) for m in PRESET_MINUTES}
        self.custom_field = ft.TextField(
            label="自由設定(分)",
            width=130,
            dense=True,
            border=theme.input_border(),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            on_change=self._on_custom_change,
        )

        self.ring = ft.ProgressRing(
            value=0,
            width=RING_SIZE,
            height=RING_SIZE,
            stroke_width=14,
            color=theme.PINK_DEEP,
            bgcolor=theme.LAVENDER,
            stroke_cap=ft.StrokeCap.ROUND,
        )
        self.time_text = ft.Text("25:00", size=48, weight=ft.FontWeight.W_600, color=theme.TEXT)
        self.status_text = ft.Text("準備OK", size=14, color=theme.TEXT_SUB)
        self.elapsed_text = ft.Text("", size=12, color=theme.TEXT_SUB)
        ring_stack = ft.Stack(
            [
                self.ring,
                ft.Container(
                    content=ft.Column(
                        [self.status_text, self.time_text, self.elapsed_text],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    width=RING_SIZE,
                    height=RING_SIZE,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            width=RING_SIZE,
            height=RING_SIZE,
        )

        self.start_btn = self._button("スタート", ft.Icons.PLAY_ARROW_ROUNDED, self._on_start, primary=True)
        self.pause_btn = self._button("一時停止", ft.Icons.PAUSE_ROUNDED, self._on_pause, primary=True)
        self.resume_btn = self._button("再開", ft.Icons.PLAY_ARROW_ROUNDED, self._on_resume, primary=True)
        self.stop_btn = self._button("終了", ft.Icons.STOP_ROUNDED, self._on_stop, primary=False)

        self.settings = ft.Column(
            [
                ft.Row([self.subject_dropdown, add_subject_btn, delete_subject_btn], spacing=0),
                ft.Text("時間", size=13, color=theme.TEXT_SUB),
                ft.Row(
                    [*self.preset_chips.values(), self.custom_field],
                    wrap=True,
                    spacing=8,
                    run_spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=10,
        )

        self.root = ft.Column(
            [
                theme.card(self.settings),
                theme.card(
                    ft.Column(
                        [
                            ring_stack,
                            ft.Row(
                                [self.start_btn, self.pause_btn, self.resume_btn, self.stop_btn],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=12,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=24,
                    ),
                    padding=28,
                ),
            ],
            spacing=16,
        )

    def _chip(self, label: str, minutes: int) -> ft.Container:
        return ft.Container(
            content=ft.Text(label, size=14, weight=ft.FontWeight.W_500),
            padding=ft.Padding.symmetric(horizontal=18, vertical=10),
            border_radius=24,
            on_click=lambda e: self._on_preset(minutes),
        )

    def _button(self, label: str, icon, handler, primary: bool) -> ft.Button:
        return ft.Button(
            content=ft.Text(label, size=15, weight=ft.FontWeight.W_600),
            icon=icon,
            on_click=handler,
            bgcolor=theme.PINK_DEEP if primary else theme.WHITE,
            color=theme.WHITE if primary else theme.PINK_DEEP,
            icon_color=theme.WHITE if primary else theme.PINK_DEEP,
            elevation=0,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=26),
                padding=ft.Padding.symmetric(horizontal=22, vertical=14),
                side=None if primary else ft.BorderSide(1.5, theme.PINK),
            ),
        )

    # ------------------------------------------------------------------ 表示の更新
    def _load_subjects(self, select_id: Optional[int] = None) -> None:
        subjects = list_subjects()
        if self.subject_id not in {s.id for s in subjects}:
            self.subject_id = None  # 削除された教科を選んだままにしない
        self.subject_dropdown.options = [ft.DropdownOption(key=str(s.id), text=s.name) for s in subjects]
        if select_id is not None:
            self.subject_id = select_id
        elif self.subject_id is None and subjects:
            self.subject_id = subjects[0].id
        self.subject_dropdown.value = str(self.subject_id) if self.subject_id else None

    def _render(self) -> None:
        """今のタイマーの状態に合わせて、表示とボタンを切り替える。"""
        t = self.timer
        state = t.state

        if t.is_active:
            self.time_text.value = format_clock(t.remaining_seconds)
            self.ring.value = t.progress
            self.elapsed_text.value = f"勉強した時間 {format_duration(t.elapsed_seconds)}"
        else:
            self.time_text.value = format_clock((self.selected_minutes or 0) * 60)
            self.ring.value = 0
            self.elapsed_text.value = ""

        self.status_text.value = {
            TimerState.IDLE: "準備OK",
            TimerState.RUNNING: "集中しています",
            TimerState.PAUSED: "一時停止中",
            TimerState.FINISHED: "おつかれさま！",
        }[state]
        self.ring.color = theme.LAVENDER_DEEP if state is TimerState.PAUSED else theme.PINK_DEEP

        self.start_btn.visible = state is TimerState.IDLE
        self.pause_btn.visible = state is TimerState.RUNNING
        self.resume_btn.visible = state is TimerState.PAUSED
        self.stop_btn.visible = t.is_active
        self.start_btn.disabled = not (self.selected_minutes and self.subject_id)
        # 計測中は設定を変えられないようにする
        self.settings.disabled = t.is_active

        for minutes, chip in self.preset_chips.items():
            selected = minutes == self.selected_minutes and not self.custom_field.value
            chip.bgcolor = theme.PINK if selected else theme.GRAY_BG
            chip.content.color = theme.TEXT if selected else theme.TEXT_SUB

    def _refresh(self) -> None:
        self._render()
        self.page.update()

    def _snack(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(message), bgcolor=theme.LAVENDER_DEEP))

    # ------------------------------------------------------------------ 設定の操作
    def _on_subject_select(self, e) -> None:
        self.subject_id = int(e.control.value) if e.control.value else None
        self._refresh()

    def _on_preset(self, minutes: int) -> None:
        if self.timer.is_active:
            return
        self.selected_minutes = minutes
        self.custom_field.value = ""
        self.custom_field.error_text = None
        self._refresh()

    def _on_custom_change(self, e) -> None:
        text = (self.custom_field.value or "").strip()
        self.custom_field.error_text = None
        if not text:
            self.selected_minutes = PRESET_MINUTES[0]
        else:
            minutes = int(text)
            if MIN_MINUTES <= minutes <= MAX_MINUTES:
                self.selected_minutes = minutes
            else:
                self.selected_minutes = None
                self.custom_field.error_text = f"{MIN_MINUTES}〜{MAX_MINUTES}分"
        self._refresh()

    def _open_add_subject_dialog(self, e) -> None:
        name_field = ft.TextField(label="教科名", autofocus=True, max_length=20)

        def save(_):
            try:
                subject = add_subject(name_field.value or "")
            except ValueError as err:
                name_field.error_text = str(err)
                self.page.update()
                return
            self.page.pop_dialog()
            self._load_subjects(select_id=subject.id)
            self._refresh()
            self._snack(f"「{subject.name}」を追加しました")

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("教科を追加"),
                content=name_field,
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda _: self.page.pop_dialog()),
                    ft.TextButton("追加", on_click=save),
                ],
            )
        )

    def _open_delete_subject_dialog(self, e) -> None:
        subject = next((s for s in list_subjects() if s.id == self.subject_id), None)
        if subject is None:
            self._snack("削除する教科を選んでください")
            return
        try:
            count = repository.count_sessions_for_subject(subject.id)
        except Exception as err:
            self._snack(f"記録を確認できませんでした: {err}")
            return
        message = f"「{subject.name}」を削除します。"
        if count:
            message += f"\nこの教科の勉強記録 {count} 件も削除され、元に戻せません。"

        def delete(_):
            self.page.pop_dialog()
            try:
                repository.delete_subject_with_sessions(subject.id)
            except ValueError as err:
                self._snack(str(err))
                return
            self._load_subjects()
            self._refresh()
            self.on_saved()  # 記録画面も更新する
            self._snack(f"「{subject.name}」を削除しました")

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("教科を削除しますか？"),
                content=ft.Text(message),
                actions=[
                    ft.TextButton("キャンセル", on_click=lambda _: self.page.pop_dialog()),
                    ft.TextButton(
                        "削除",
                        on_click=delete,
                        style=ft.ButtonStyle(color=theme.PINK_DEEP),
                    ),
                ],
            )
        )

    # ------------------------------------------------------------------ タイマーの操作
    def _on_start(self, e) -> None:
        if not self.subject_id or not self.selected_minutes:
            self._snack("教科と時間を選んでください")
            return
        try:
            self.timer.start(self.selected_minutes)
        except ValueError as err:
            self._snack(str(err))
            return
        self._start_loop()
        self._refresh()

    def _on_pause(self, e) -> None:
        self.timer.pause()
        self._refresh()

    def _on_resume(self, e) -> None:
        self.timer.resume()
        self._refresh()

    def _on_stop(self, e) -> None:
        self._finish(completed=False)

    def _start_loop(self) -> None:
        self._loop_id += 1
        self.page.run_task(self._tick_loop, self._loop_id)

    async def _tick_loop(self, loop_id: int) -> None:
        """計測中、定期的に表示を更新し、時間になったら終了処理をする。"""
        while loop_id == self._loop_id and self.timer.is_active:
            if self.timer.check_finished():
                self._finish(completed=True)
                await self._bring_to_front()
                return
            if self.timer.state is TimerState.RUNNING:
                self._refresh()
            await asyncio.sleep(TICK_INTERVAL)

    async def _bring_to_front(self) -> None:
        try:
            await self.page.window.to_front()
        except Exception:
            pass  # ブラウザで動かしている場合などは前面化できない

    def _finish(self, completed: bool) -> None:
        """計測を終えて記録を保存し、タイマーを待機状態に戻す。"""
        t = self.timer
        if t.state is TimerState.RUNNING:
            t.pause()  # 経過時間を確定させる
        elapsed = t.elapsed_seconds
        self._loop_id += 1  # 更新ループを止める

        try:
            saved_id = repository.save_session(
                subject_id=self.subject_id,
                started_at=t.started_at,
                ended_at=datetime.now(),
                planned_minutes=t.planned_seconds // 60,
                actual_seconds=elapsed,
                completed=completed,
            )
        except Exception as err:  # DB に書けなかった場合も、アプリは止めずに知らせる
            saved_id = None
            self._snack(f"記録の保存に失敗しました: {err}")
        else:
            if saved_id is None:
                self._snack("1分未満のため記録しませんでした")

        t.reset()
        self._refresh()

        if saved_id is not None:
            self.on_saved()
            if completed:
                _notify_sound()
                self._show_finished_dialog(elapsed)
            else:
                self._snack(f"{format_duration(elapsed)} を記録しました")

    def _show_finished_dialog(self, elapsed: int) -> None:
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("おつかれさま！", color=theme.PINK_DEEP, weight=ft.FontWeight.BOLD),
                content=ft.Text(f"{format_duration(elapsed)} の勉強を記録しました。\n少し休憩しましょう。"),
                actions=[ft.TextButton("OK", on_click=lambda _: self.page.pop_dialog())],
            )
        )
