"""LoginThrottle: sliding-window failure counting with an injectable clock."""
import pytest

from app.core.throttle import LoginThrottle, TooManyAttemptsError


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_blocks_after_max_failures_and_recovers_after_the_window():
    clock = FakeClock()
    throttle = LoginThrottle(max_failures=3, window_seconds=60, clock=clock)
    key = LoginThrottle.key("Nurse@Example.org ", "10.0.0.1")
    for _ in range(3):
        throttle.check(key)
        throttle.record_failure(key)
    with pytest.raises(TooManyAttemptsError) as blocked:
        throttle.check(key)
    assert blocked.value.details["retry_after_seconds"] == 61
    clock.now += 61
    throttle.check(key)  # oldest failures have left the window


def test_window_slides_rather_than_resetting_all_at_once():
    clock = FakeClock()
    throttle = LoginThrottle(max_failures=2, window_seconds=60, clock=clock)
    throttle.record_failure("k")
    clock.now += 50
    throttle.record_failure("k")
    clock.now += 11  # first failure expired, second still counts
    throttle.check("k")
    throttle.record_failure("k")
    with pytest.raises(TooManyAttemptsError):
        throttle.check("k")


def test_reset_clears_and_keys_are_independent():
    throttle = LoginThrottle(max_failures=1, window_seconds=60, clock=FakeClock())
    throttle.record_failure(LoginThrottle.key("a@example.org", "1.1.1.1"))
    throttle.check(LoginThrottle.key("a@example.org", "2.2.2.2"))  # other address
    throttle.check(LoginThrottle.key("b@example.org", "1.1.1.1"))  # other account
    throttle.reset(LoginThrottle.key("a@example.org", "1.1.1.1"))
    throttle.check(LoginThrottle.key("A@EXAMPLE.ORG", "1.1.1.1"))  # email normalised
