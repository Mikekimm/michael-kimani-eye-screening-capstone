"""Admin analytics: aggregate counts only (no images, patient codes or names)."""
from datetime import datetime, timezone
from statistics import median
from zoneinfo import ZoneInfo

from ..models import User
from ..models.enums import Role
from ..repositories import AnalyticsRepository, ScreeningRepository, UserRepository
from ..schemas import AnalyticsOut
from .access import AccessPolicy
from .daily_counts import count_by_day, start_of_window
from .review_targets import ReviewTargets

PER_DAY_WINDOW = 30


class AnalyticsService:
    def __init__(self, analytics: AnalyticsRepository, users: UserRepository, screenings: ScreeningRepository,
                 targets: ReviewTargets | None = None, zone: ZoneInfo | None = None):
        self._analytics = analytics
        self._users = users
        self._screenings = screenings
        self._targets = targets or ReviewTargets()
        self._zone = zone or ZoneInfo("UTC")

    def summary(self, user: User) -> AnalyticsOut:
        AccessPolicy.require_role(user, Role.ADMIN)
        total = self._analytics.total_screenings()
        now = datetime.now(timezone.utc)
        delays = [(reviewed - referred).total_seconds() / 3600
                  for referred, reviewed in self._analytics.first_review_delays()]
        return AnalyticsOut(
            total_screenings=total,
            screenings_per_day=count_by_day(
                self._screenings.created_times(None, start_of_window(self._zone, PER_DAY_WINDOW, now)),
                self._zone, PER_DAY_WINDOW, now),
            time_zone=self._zone.key,
            positives_per_condition=self._analytics.positives_per_condition(),
            referral_rate=round(self._analytics.referral_count() / total, 4) if total else None,
            open_referrals=self._analytics.open_referral_count(),
            overdue_referrals=sum(self._targets.is_overdue(at, reason, now)
                                  for at, reason in self._analytics.open_referrals()),
            review_targets_hours={"urgent": self._targets.urgent_hours, "routine": self._targets.routine_hours},
            median_review_turnaround_hours=round(median(delays), 2) if delays else None,
            model_versions_in_use=self._analytics.model_versions_in_use(),
            users_by_role=self._users.count_by_role(),
        )
