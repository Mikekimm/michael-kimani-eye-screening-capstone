"""Admin analytics: aggregate counts only (no images, patient codes or names)."""
from statistics import median

from ..models import User
from ..models.enums import Role
from ..repositories import AnalyticsRepository, UserRepository
from ..schemas import AnalyticsOut, DailyCount
from .access import AccessPolicy


class AnalyticsService:
    def __init__(self, analytics: AnalyticsRepository, users: UserRepository):
        self._analytics = analytics
        self._users = users

    def summary(self, user: User) -> AnalyticsOut:
        AccessPolicy.require_role(user, Role.ADMIN)
        total = self._analytics.total_screenings()
        delays = [(reviewed - referred).total_seconds() / 3600
                  for referred, reviewed in self._analytics.first_review_delays()]
        return AnalyticsOut(
            total_screenings=total,
            screenings_per_day=[DailyCount(day=d, count=c) for d, c in self._analytics.screenings_per_day()],
            positives_per_condition=self._analytics.positives_per_condition(),
            referral_rate=round(self._analytics.referral_count() / total, 4) if total else None,
            open_referrals=self._analytics.open_referral_count(),
            median_review_turnaround_hours=round(median(delays), 2) if delays else None,
            model_versions_in_use=self._analytics.model_versions_in_use(),
            users_by_role=self._users.count_by_role(),
        )
