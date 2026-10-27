"""Screenings per calendar day in the clinic's time zone.

Day boundaries follow the configured zone (setting TIME_ZONE, default Africa/Kigali, UTC+2), not the
server's or the phone's clock, so a screening at 23:59 and one at 00:01 local time land on different days
wherever the server runs.
"""
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..schemas import DailyCount


def local_day(moment: datetime, zone: ZoneInfo) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)  # stored timestamps are UTC
    return moment.astimezone(zone).date()


def count_by_day(times: Iterable[datetime], zone: ZoneInfo, days: int, now: datetime) -> list[DailyCount]:
    """One entry per day for the last ``days`` days ending today (local), oldest first, zero-filled."""
    today = local_day(now, zone)
    counts = Counter(local_day(t, zone) for t in times)
    return [DailyCount(day=(today - timedelta(days=offset)).isoformat(), count=counts[today - timedelta(days=offset)])
            for offset in range(days - 1, -1, -1)]


def start_of_window(zone: ZoneInfo, days: int, now: datetime) -> datetime:
    """UTC instant of local midnight at the start of the window, for the database query."""
    first = local_day(now, zone) - timedelta(days=days - 1)
    return datetime(first.year, first.month, first.day, tzinfo=zone).astimezone(timezone.utc)
