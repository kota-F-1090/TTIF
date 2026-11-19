"""タイマーの「動き」だけを担当する部分。画面やデータベースには一切触らない。

ポイント:
- 1秒ごとに「残り-1」と数えるのではなく、時計(time.monotonic)で経過時間を計算する。
  画面の更新が遅れても、時間がずれない。
- clock を外から渡せるので、テストでは偽の時計を使って一瞬で検証できる。
"""
import time
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

PRESET_MINUTES = (25, 50, 60)
MIN_MINUTES = 1
MAX_MINUTES = 300


class TimerState(Enum):
    IDLE = "idle"          # 待機中
    RUNNING = "running"    # 計測中
    PAUSED = "paused"      # 一時停止中
    FINISHED = "finished"  # 設定時間に到達


class TimerError(Exception):
    """今の状態ではできない操作をしたときのエラー(例: 待機中に一時停止)。"""


class StudyTimer:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = datetime.now,
    ):
        self._clock = clock
        self._now = now
        self.reset()

    def reset(self) -> None:
        self.state = TimerState.IDLE
        self.planned_seconds = 0
        self.started_at: Optional[datetime] = None  # 記録用の実際の開始日時
        self._accumulated = 0.0                       # 一時停止までに経過した秒数
        self._running_since: Optional[float] = None   # 今回の計測を始めた時計の値

    # ---- 操作 ----
    def start(self, minutes: int) -> None:
        if self.state is not TimerState.IDLE:
            raise TimerError("タイマーはすでに動いています")
        if not MIN_MINUTES <= minutes <= MAX_MINUTES:
            raise ValueError(f"時間は{MIN_MINUTES}〜{MAX_MINUTES}分で設定してください")
        self.planned_seconds = minutes * 60
        self.started_at = self._now()
        self._running_since = self._clock()
        self.state = TimerState.RUNNING

    def pause(self) -> None:
        if self.state is not TimerState.RUNNING:
            raise TimerError("計測中ではありません")
        self._accumulated += self._clock() - self._running_since
        self._running_since = None
        self.state = TimerState.PAUSED

    def resume(self) -> None:
        if self.state is not TimerState.PAUSED:
            raise TimerError("一時停止中ではありません")
        self._running_since = self._clock()
        self.state = TimerState.RUNNING

    def check_finished(self) -> bool:
        """設定時間に達していたら FINISHED にして True を返す。画面側が定期的に呼ぶ。"""
        if self.state is TimerState.RUNNING and self.remaining_seconds <= 0:
            self._accumulated = float(self.planned_seconds)
            self._running_since = None
            self.state = TimerState.FINISHED
            return True
        return False

    # ---- 状態の読み取り ----
    @property
    def elapsed_seconds(self) -> int:
        """実際に勉強した秒数(一時停止中の時間は含まない)。設定時間を超えない。"""
        elapsed = self._accumulated
        if self._running_since is not None:
            elapsed += self._clock() - self._running_since
        return int(min(elapsed, self.planned_seconds))

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.planned_seconds - self.elapsed_seconds)

    @property
    def progress(self) -> float:
        """0.0〜1.0 の進み具合。円形のゲージ表示に使う。"""
        if self.planned_seconds == 0:
            return 0.0
        return self.elapsed_seconds / self.planned_seconds

    @property
    def is_active(self) -> bool:
        return self.state in (TimerState.RUNNING, TimerState.PAUSED)
