"""Login throttling: a sliding-window failure counter per (email, client address).

In-memory and per process, which suits the single-instance deployment; behind several API
instances this would move to a shared store such as Redis.
"""
import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock

from .errors import AppError


class TooManyAttemptsError(AppError):
    status_code = 429
    code = "too_many_attempts"


class LoginThrottle:
    def __init__(self, max_failures: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def key(email: str, client: str | None) -> str:
        return f"{email.strip().lower()}|{client or 'unknown'}"

    def check(self, key: str) -> None:
        """Raise if this key has used up its failures inside the window."""
        with self._lock:
            recent = self._prune(key)
            if len(recent) >= self._max:
                wait = int(recent[0] + self._window - self._clock()) + 1
                raise TooManyAttemptsError(
                    f"Too many failed sign-in attempts. Try again in {max(1, wait // 60)} minute(s).",
                    details={"retry_after_seconds": wait})

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key).append(self._clock())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _prune(self, key: str) -> deque[float]:
        recent = self._failures[key]
        cutoff = self._clock() - self._window
        while recent and recent[0] <= cutoff:
            recent.popleft()
        return recent
