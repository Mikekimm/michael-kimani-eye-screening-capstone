"""Offline-to-online synchronisation.

Screening always works offline and writes to the local store first. ``SyncService``
later pushes pending records to the server and pulls specialist reviews back.

Rules that make it safe on a flaky network:
* No connectivity (or a 5xx) stops the cycle without counting a failed attempt.
* An authentication failure stops the cycle and is reported; records stay pending.
* A 4xx rejection marks that one record FAILED so it cannot block the queue.
* Uploads are idempotent (the server de-duplicates by id) and review import is
  idempotent (unique remote id), so repeating a cycle never duplicates data.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from .exceptions import RemoteAuthError, RemoteRejectedError, RemoteUnavailableError
from .storage import ScreeningRepository

_CURSOR_KEY = "review_cursor"


class RemoteClient(ABC):
    """What the sync service needs from the cloud, so it can be faked in tests."""

    @abstractmethod
    def push_screening(self, payload: Dict[str, Any]) -> None: ...

    @abstractmethod
    def fetch_reviews(self, since: int) -> List[Dict[str, Any]]: ...


@dataclass(frozen=True)
class SyncReport:
    pushed: int = 0
    failed: int = 0
    reviews_pulled: int = 0
    offline: bool = False
    auth_error: bool = False

    @property
    def summary(self) -> str:
        if self.auth_error:
            return "Sync stopped: the server rejected the access token."
        if self.offline:
            return (f"Offline: {self.pushed} uploaded before the connection dropped. "
                    "Remaining records stay saved on this device.")
        return (f"Uploaded {self.pushed} screening(s), {self.failed} rejected, "
                f"{self.reviews_pulled} new specialist review(s).")


class SyncService:
    def __init__(self, repository: ScreeningRepository, client: RemoteClient):
        self._repo = repository
        self._client = client

    def sync(self) -> SyncReport:
        pushed = failed = 0
        offline = auth_error = False

        for record in self._repo.pending():
            try:
                self._client.push_screening(self._repo.build_sync_payload(record.id))
            except RemoteUnavailableError:
                offline = True
                break
            except RemoteAuthError:
                auth_error = True
                break
            except RemoteRejectedError as exc:
                self._repo.record_failure(record.id, str(exc), permanent=True)
                failed += 1
            else:
                self._repo.mark_synced(record.id)
                pushed += 1

        pulled = 0
        if not (offline or auth_error):
            try:
                pulled = self._pull_reviews()
            except RemoteUnavailableError:
                offline = True
            except RemoteAuthError:
                auth_error = True
        return SyncReport(pushed, failed, pulled, offline, auth_error)

    def _pull_reviews(self) -> int:
        cursor = int(self._repo.get_meta(_CURSOR_KEY, "0"))
        imported = 0
        newest = cursor
        for payload in self._client.fetch_reviews(cursor):
            if self._repo.import_remote_review(payload):
                imported += 1
            newest = max(newest, int(payload["id"]))
        if newest != cursor:
            self._repo.set_meta(_CURSOR_KEY, str(newest))
        return imported
