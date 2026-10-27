"""Per-day counts use the clinic's time zone (Africa/Kigali, UTC+2), not the server's or the phone's clock."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.services.daily_counts import count_by_day, local_day, start_of_window

KIGALI = ZoneInfo("Africa/Kigali")


def test_2359_and_0001_local_fall_on_different_days():
    late = datetime(2026, 10, 27, 23, 59, tzinfo=KIGALI).astimezone(timezone.utc)   # 21:59 UTC
    early = datetime(2026, 10, 28, 0, 1, tzinfo=KIGALI).astimezone(timezone.utc)    # 22:01 UTC, same UTC day
    assert late.date() == early.date()                       # one day in UTC ...
    assert local_day(late, KIGALI).isoformat() == "2026-10-27"  # ... two days locally
    assert local_day(early, KIGALI).isoformat() == "2026-10-28"
    now = datetime(2026, 10, 28, 9, 0, tzinfo=KIGALI)
    counts = count_by_day([late, early, early], KIGALI, 3, now)
    assert [(c.day, c.count) for c in counts] == [("2026-10-26", 0), ("2026-10-27", 1), ("2026-10-28", 2)]


def test_naive_timestamps_are_read_as_utc_and_the_window_starts_at_local_midnight():
    assert local_day(datetime(2026, 10, 27, 22, 30), KIGALI).isoformat() == "2026-10-28"
    start = start_of_window(KIGALI, 2, datetime(2026, 10, 28, 9, 0, tzinfo=KIGALI))
    assert start == datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)  # 27 Oct 00:00 in Kigali
