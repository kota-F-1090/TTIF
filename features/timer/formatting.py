"""秒数を画面表示用の文字列に変換する小さな関数たち。"""


def format_clock(seconds: int) -> str:
    """タイマー表示用。 1500 -> '25:00', 3725 -> '1:02:05'"""
    seconds = max(0, int(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_duration(seconds: int) -> str:
    """記録表示用。 1500 -> '25分', 3900 -> '1時間5分', 3600 -> '1時間'"""
    minutes = max(0, int(seconds)) // 60
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}時間{m}分"
    if h:
        return f"{h}時間"
    return f"{m}分"
