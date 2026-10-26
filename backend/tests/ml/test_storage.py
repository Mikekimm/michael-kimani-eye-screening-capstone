"""Local store: validation, retained fields, review history, sync bookkeeping."""
import hashlib
import sqlite3
import uuid

import pytest

from app.ml.domain import ReviewDecision, SyncStatus
from app.ml.exceptions import RecordNotFoundError, RecordValidationError
from tests.conftest import encode, make_fundus_like, make_result, save_one


def test_screening_keeps_laterality_model_version_and_threshold(repo):
    record = save_one(repo, probability=0.8, side="right")
    assert record.laterality.value == "right"
    assert record.model_version == "test-model-1"
    assert record.threshold == 0.5 and record.probability == 0.8
    assert record.sync_status is SyncStatus.PENDING and record.needs_review


def test_image_is_stored_with_matching_checksum(repo):
    image = encode(make_fundus_like(seed=9))
    record = save_one(repo, image=image)
    assert repo.image_bytes(record.id) == image
    assert record.image_sha256 == hashlib.sha256(image).hexdigest()


@pytest.mark.parametrize("bad_ref", ["", "ab", "John Smith", "a/b/c", "x" * 41, "../etc"])
def test_patient_reference_must_be_a_pseudonymous_code(repo, bad_ref):
    with pytest.raises(RecordValidationError):
        save_one(repo, patient=bad_ref)


def test_invalid_laterality_is_rejected(repo):
    with pytest.raises(RecordValidationError):
        save_one(repo, side="both")


def test_empty_image_is_rejected_and_nothing_saved(repo):
    with pytest.raises(RecordValidationError):
        repo.add_screening(make_result(), b"", "PT-001", "left", "nurse", "stub")
    assert repo.stats()["screenings"] == 0


def test_unknown_screening_raises_not_found(repo):
    with pytest.raises(RecordNotFoundError):
        repo.get(str(uuid.uuid4()))


def test_sync_payload_round_trips_through_server_import(repo, tmp_path):
    from app.ml.storage import ScreeningRepository
    record = save_one(repo, side="left")
    server_repo = ScreeningRepository(tmp_path / "srv.db", tmp_path / "srv_img")
    stored, created = server_repo.import_screening(repo.build_sync_payload(record.id))
    assert created and stored.id == record.id
    assert (stored.laterality, stored.model_version, stored.threshold) == (
        record.laterality, record.model_version, record.threshold)
    assert server_repo.image_bytes(record.id) == repo.image_bytes(record.id)


def test_import_is_idempotent(repo, tmp_path):
    from app.ml.storage import ScreeningRepository
    record = save_one(repo)
    server_repo = ScreeningRepository(tmp_path / "srv.db", tmp_path / "srv_img")
    payload = repo.build_sync_payload(record.id)
    assert server_repo.import_screening(payload)[1] is True
    assert server_repo.import_screening(payload)[1] is False
    assert server_repo.stats()["screenings"] == 1


def test_import_rejects_tampered_image(repo, tmp_path):
    from app.ml.storage import ScreeningRepository
    server_repo = ScreeningRepository(tmp_path / "srv.db", tmp_path / "srv_img")
    payload = repo.build_sync_payload(save_one(repo).id)
    payload["image_sha256"] = "0" * 64
    with pytest.raises(RecordValidationError):
        server_repo.import_screening(payload)
    assert server_repo.stats()["screenings"] == 0


@pytest.mark.parametrize("field,value", [("probability", 1.5), ("threshold", 0.0),
                                         ("laterality", "up"), ("patient_ref", "Jane Doe"),
                                         ("image_b64", "***not-base64***"), ("id", "nope")])
def test_import_rejects_malformed_fields(repo, tmp_path, field, value):
    from app.ml.storage import ScreeningRepository
    server_repo = ScreeningRepository(tmp_path / "srv.db", tmp_path / "srv_img")
    payload = repo.build_sync_payload(save_one(repo).id)
    payload[field] = value
    with pytest.raises(RecordValidationError):
        server_repo.import_screening(payload)


def test_duplicate_id_never_destroys_the_existing_image(repo):
    record = save_one(repo)
    original = repo.image_bytes(record.id)
    with pytest.raises(sqlite3.IntegrityError):
        repo._insert_screening(  # simulates two uploads of one id racing past the check
            record_id=record.id, created_at="2026-01-01T00:00:00+00:00",
            patient_ref="PT-001", laterality=record.laterality, image_bytes=b"different",
            model_version="m", classifier_name="c", threshold=0.5, probability=0.5,
            dr_detected=True, needs_review=True, quality={}, created_by="x",
            sync_status=SyncStatus.SYNCED)
    assert repo.image_bytes(record.id) == original
    assert not list(repo._image_dir.glob("*.tmp"))


def test_list_filters(repo):
    flagged = save_one(repo, probability=0.9, patient="PT-001")
    save_one(repo, probability=0.05, patient="PT-002")
    assert [r.id for r in repo.list_screenings(needs_review=True)] == [flagged.id]
    assert len(repo.list_screenings()) == 2
    repo.add_review(flagged.id, "dr-x", "approve")
    assert repo.list_screenings(needs_review=True, unreviewed=True) == []
    assert [r.id for r in repo.list_screenings(unreviewed=False)] == [flagged.id]


def test_review_history_is_append_only_and_ordered(repo):
    record = save_one(repo)
    repo.add_review(record.id, "dr-a", "approve", "first look")
    repo.add_review(record.id, "dr-b", "override_no_dr", "second opinion")
    history = repo.reviews_for(record.id)
    assert [(r.reviewer, r.decision) for r in history] == [
        ("dr-a", ReviewDecision.APPROVE), ("dr-b", ReviewDecision.OVERRIDE_NO_DR)]
    assert repo.latest_review(record.id).reviewer == "dr-b"


def test_review_validation(repo):
    record = save_one(repo)
    with pytest.raises(RecordValidationError):
        repo.add_review(record.id, "dr-a", "maybe")
    with pytest.raises(RecordValidationError):
        repo.add_review(record.id, "  ", "approve")
    with pytest.raises(RecordValidationError):
        repo.add_review(record.id, "dr-a", "approve", "x" * 2001)
    with pytest.raises(RecordNotFoundError):
        repo.add_review(str(uuid.uuid4()), "dr-a", "approve")
    assert repo.reviews_for(record.id) == []


def test_remote_review_import_is_idempotent_and_skips_unknown_screenings(repo):
    record = save_one(repo)
    review = {"id": 7, "screening_id": record.id, "reviewer": "dr-a",
              "decision": "approve", "notes": "", "reviewed_at": "2026-01-01T00:00:00+00:00"}
    assert repo.import_remote_review(review) is True
    assert repo.import_remote_review(review) is False
    assert len(repo.reviews_for(record.id)) == 1
    other = dict(review, id=8, screening_id=str(uuid.uuid4()))
    assert repo.import_remote_review(other) is False


def test_failure_bookkeeping(repo):
    record = save_one(repo)
    repo.record_failure(record.id, "temporary", permanent=False)
    assert repo.get(record.id).sync_status is SyncStatus.PENDING
    assert repo.get(record.id).sync_attempts == 1
    repo.record_failure(record.id, "rejected", permanent=True)
    assert repo.get(record.id).sync_status is SyncStatus.FAILED
    assert repo.pending() == []
    assert repo.reset_failed() == 1 and len(repo.pending()) == 1
    repo.mark_synced(record.id)
    synced = repo.get(record.id)
    assert synced.sync_status is SyncStatus.SYNCED and synced.synced_at


def test_stats_counts(repo):
    a = save_one(repo, probability=0.9, patient="PT-001")
    save_one(repo, probability=0.05, patient="PT-002")
    repo.add_review(a.id, "dr", "approve")
    stats = repo.stats()
    assert stats == {"screenings": 2, "pending_sync": 2, "failed_sync": 0,
                     "dr_flagged": 1, "needs_review": 1, "reviewed": 1}


def test_meta_round_trip(repo):
    assert repo.get_meta("k", "d") == "d"
    repo.set_meta("k", "1")
    repo.set_meta("k", "2")
    assert repo.get_meta("k") == "2"
