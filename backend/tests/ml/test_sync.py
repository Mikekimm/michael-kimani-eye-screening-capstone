"""SyncService behaviour against a fake remote (no network)."""
from app.ml.domain import SyncStatus
from app.ml.exceptions import RemoteAuthError, RemoteRejectedError, RemoteUnavailableError
from app.ml.sync import RemoteClient, SyncService
from tests.conftest import save_one


class FakeRemote(RemoteClient):
    def __init__(self):
        self.uploaded = {}
        self.reviews = []
        self.mode = "online"           # online | offline | auth
        self.reject_ids = set()
        self.drop_after = None         # go offline after N successful uploads
        self.push_calls = 0

    def push_screening(self, payload):
        self.push_calls += 1
        if self.mode == "offline":
            raise RemoteUnavailableError("no route")
        if self.mode == "auth":
            raise RemoteAuthError("bad token")
        if self.drop_after is not None and len(self.uploaded) >= self.drop_after:
            raise RemoteUnavailableError("connection dropped")
        if payload["id"] in self.reject_ids:
            raise RemoteRejectedError("invalid record")
        self.uploaded[payload["id"]] = payload

    def fetch_reviews(self, since):
        if self.mode == "offline":
            raise RemoteUnavailableError("no route")
        if self.mode == "auth":
            raise RemoteAuthError("bad token")
        return [r for r in self.reviews if r["id"] > since]


def review(rid, screening_id, decision="approve"):
    return {"id": rid, "screening_id": screening_id, "reviewer": "dr-x",
            "decision": decision, "notes": "", "reviewed_at": "2026-01-01T00:00:00+00:00"}


def test_offline_keeps_records_pending_without_counting_attempts(repo):
    record = save_one(repo)
    remote = FakeRemote()
    remote.mode = "offline"
    report = SyncService(repo, remote).sync()
    assert report.offline and report.pushed == 0
    stored = repo.get(record.id)
    assert stored.sync_status is SyncStatus.PENDING and stored.sync_attempts == 0


def test_online_uploads_everything_then_is_idempotent(repo):
    for n in range(3):
        save_one(repo, patient=f"PT-00{n}")
    remote = FakeRemote()
    service = SyncService(repo, remote)
    assert service.sync().pushed == 3
    assert service.sync().pushed == 0
    assert len(remote.uploaded) == 3 and repo.pending() == []


def test_connection_drop_mid_cycle_resumes_where_it_stopped(repo):
    for n in range(4):
        save_one(repo, patient=f"PT-00{n}")
    remote = FakeRemote()
    remote.drop_after = 2
    first = SyncService(repo, remote).sync()
    assert (first.pushed, first.offline) == (2, True)
    assert len(repo.pending()) == 2
    remote.drop_after = None
    second = SyncService(repo, remote).sync()
    assert second.pushed == 2 and not second.offline
    assert len(remote.uploaded) == 4


def test_auth_failure_stops_cycle_and_keeps_records_pending(repo):
    save_one(repo)
    remote = FakeRemote()
    remote.mode = "auth"
    report = SyncService(repo, remote).sync()
    assert report.auth_error and report.pushed == 0
    assert len(repo.pending()) == 1


def test_rejected_record_is_marked_failed_and_does_not_block_others(repo):
    bad = save_one(repo, patient="PT-BAD")
    good = save_one(repo, patient="PT-GOOD")
    remote = FakeRemote()
    remote.reject_ids.add(bad.id)
    report = SyncService(repo, remote).sync()
    assert (report.pushed, report.failed) == (1, 1)
    assert repo.get(bad.id).sync_status is SyncStatus.FAILED
    assert repo.get(bad.id).last_sync_error == "invalid record"
    assert repo.get(good.id).sync_status is SyncStatus.SYNCED


def test_reviews_are_pulled_once_using_a_cursor(repo):
    record = save_one(repo)
    remote = FakeRemote()
    remote.reviews = [review(1, record.id), review(2, record.id, "override_no_dr")]
    service = SyncService(repo, remote)
    assert service.sync().reviews_pulled == 2
    assert service.sync().reviews_pulled == 0
    remote.reviews.append(review(3, record.id, "ungradable"))
    assert service.sync().reviews_pulled == 1
    assert [r.decision.value for r in repo.reviews_for(record.id)] == [
        "approve", "override_no_dr", "ungradable"]


def test_reviews_for_other_clinics_are_skipped_but_cursor_advances(repo):
    remote = FakeRemote()
    remote.reviews = [review(5, "11111111-1111-1111-1111-111111111111")]
    service = SyncService(repo, remote)
    assert service.sync().reviews_pulled == 0
    assert repo.get_meta("review_cursor") == "5"


def test_summary_text_covers_each_outcome(repo):
    remote = FakeRemote()
    assert "Uploaded 0" in SyncService(repo, remote).sync().summary
    remote.mode = "offline"
    assert "Offline" in SyncService(repo, remote).sync().summary
    remote.mode = "auth"
    save_one(repo)
    assert "token" in SyncService(repo, remote).sync().summary


def test_offline_cycle_stops_after_the_first_failed_attempt(repo):
    """A dead connection must cost one attempt per cycle, not one per queued record."""
    for n in range(5):
        save_one(repo, patient=f"PT-00{n}")
    remote = FakeRemote()
    remote.mode = "offline"
    SyncService(repo, remote).sync()
    assert remote.push_calls == 1


def test_auth_failure_also_stops_after_one_attempt(repo):
    for n in range(3):
        save_one(repo, patient=f"PT-00{n}")
    remote = FakeRemote()
    remote.mode = "auth"
    SyncService(repo, remote).sync()
    assert remote.push_calls == 1
