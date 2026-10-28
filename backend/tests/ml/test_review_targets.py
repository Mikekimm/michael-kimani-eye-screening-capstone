"""Review targets: urgent 24 h, routine 72 h by default (the default priority comes from the risk policy)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.enums import ReviewPriority
from app.services.review_targets import ReviewTargets

REFERRED = datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)  # a case referred at midnight


@pytest.mark.parametrize(("priority", "hours"), [(ReviewPriority.URGENT, 24), (ReviewPriority.ROUTINE, 72)])
def test_due_time_and_overdue(priority, hours):
    targets = ReviewTargets()
    due = targets.due_at(REFERRED, priority)
    assert due == REFERRED + timedelta(hours=hours)
    assert not targets.is_overdue(REFERRED, priority, due)
    assert targets.is_overdue(REFERRED, priority, due + timedelta(seconds=1))


def test_targets_are_configurable_and_validated():
    assert ReviewTargets(6, 48).due_at(REFERRED, ReviewPriority.URGENT) == REFERRED + timedelta(hours=6)
    for bad in ((0, 72), (48, 24)):
        with pytest.raises(ValueError):
            ReviewTargets(*bad)
