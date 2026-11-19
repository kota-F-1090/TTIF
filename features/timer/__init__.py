"""タイマー・学習時間管理機能。

他の機能から使うもの:
    from features.timer import build_timer_view, init_schema
    from features.timer.repository import get_today_total_seconds, get_totals_by_subject, ...
"""
from features.timer.repository import init_schema
from features.timer.view import build_timer_view

__all__ = ["build_timer_view", "init_schema"]
