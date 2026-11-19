# タイマー・学習時間管理機能（担当: taniuchi）

## 起動方法

```
py -3.11 -m venv %USERPROFILE%\.venvs\ttif
%USERPROFILE%\.venvs\ttif\Scripts\python -m pip install -r requirements.txt
%USERPROFILE%\.venvs\ttif\Scripts\python main.py
```

テスト: `python -m unittest discover tests`

## できること

- 25・50・60分のプリセットと自由設定（1〜300分）
- 開始・一時停止・再開・終了
- 設定時間になったら終了音とダイアログで通知
- 教科別の学習時間を SQLite（`data/ttif.db`）に保存（1分未満は記録しない）
- 日別（直近7日）・週別（直近8週）のグラフ、教科別の合計、最近の記録（削除可）

## ファイル構成

| ファイル | 役割 |
|---|---|
| `timer_logic.py` | タイマーの動き（画面・DBに依存しない） |
| `repository.py` | 勉強記録の保存と集計（SQL はここだけ） |
| `formatting.py` | 秒数 → `25:00` / `1時間5分` の変換 |
| `timer_panel.py` | タイマー画面 |
| `records_panel.py` | 学習記録画面（グラフ） |
| `view.py` | 2つの画面の切り替え。`build_timer_view(page)` を main.py から呼ぶ |

## 他の機能から勉強時間を使う方法

```python
from datetime import date
from features.timer import repository

repository.get_today_total_seconds()                       # 今日の合計（秒）→ ホーム画面
repository.get_totals_by_subject(date(2026, 11, 1), date.today())  # 教科別合計
repository.get_daily_totals(start, end)                    # [(日付, 秒), ...]
repository.get_weekly_totals(weeks=8)                      # [(週の月曜日, 秒), ...]
```

## DB の表

`study_sessions`: `id`, `subject_id`(→ `subjects.id`), `started_at`, `ended_at`,
`planned_minutes`, `actual_seconds`, `status`(`completed` / `stopped`)

教科表 `subjects` は `core/database.py` で全機能共通として定義しています。
