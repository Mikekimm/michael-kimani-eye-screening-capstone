"""Local, offline-first persistence (SQLite) for screenings and specialist reviews.

The same repository class backs both the on-device store and the cloud backend, so
the schema is defined once. Every screening keeps its image, laterality, model
version and threshold; reviews are append-only so the full review history is kept.
"""
import base64
import binascii
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .domain import (
    MAX_NOTES_LENGTH,
    Laterality,
    ReviewDecision,
    ReviewRecord,
    ScreeningRecord,
    SyncStatus,
    parse_enum,
    validate_patient_ref,
)
from .exceptions import RecordNotFoundError, RecordValidationError
from .result import ScreeningResult

MAX_IMAGE_BYTES = 8 * 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screenings (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    patient_ref TEXT NOT NULL,
    laterality TEXT NOT NULL CHECK (laterality IN ('left','right','unknown')),
    image_sha256 TEXT NOT NULL,
    image_path TEXT NOT NULL,
    model_version TEXT NOT NULL,
    classifier_name TEXT NOT NULL,
    threshold REAL NOT NULL,
    probability REAL NOT NULL,
    dr_detected INTEGER NOT NULL,
    needs_review INTEGER NOT NULL,
    quality_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    sync_status TEXT NOT NULL CHECK (sync_status IN ('pending','synced','failed')),
    sync_attempts INTEGER NOT NULL DEFAULT 0,
    last_sync_error TEXT,
    synced_at TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id TEXT NOT NULL REFERENCES screenings(id),
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL,
    remote_id TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_screenings_status ON screenings(sync_status);
CREATE INDEX IF NOT EXISTS idx_reviews_screening ON reviews(screening_id);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_screening(row: sqlite3.Row) -> ScreeningRecord:
    return ScreeningRecord(
        id=row["id"],
        created_at=row["created_at"],
        patient_ref=row["patient_ref"],
        laterality=Laterality(row["laterality"]),
        image_sha256=row["image_sha256"],
        image_path=row["image_path"],
        model_version=row["model_version"],
        classifier_name=row["classifier_name"],
        threshold=row["threshold"],
        probability=row["probability"],
        dr_detected=bool(row["dr_detected"]),
        needs_review=bool(row["needs_review"]),
        quality_json=row["quality_json"],
        created_by=row["created_by"],
        sync_status=SyncStatus(row["sync_status"]),
        sync_attempts=row["sync_attempts"],
        last_sync_error=row["last_sync_error"],
        synced_at=row["synced_at"],
    )


def _row_to_review(row: sqlite3.Row) -> ReviewRecord:
    return ReviewRecord(
        id=row["id"],
        screening_id=row["screening_id"],
        reviewer=row["reviewer"],
        decision=ReviewDecision(row["decision"]),
        notes=row["notes"],
        reviewed_at=row["reviewed_at"],
    )


class ScreeningRepository:
    """SQLite-backed store. A new connection per operation keeps it thread-safe."""

    def __init__(self, db_path, image_dir):
        self._db_path = Path(db_path)
        self._image_dir = Path(image_dir)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._image_dir.mkdir(parents=True, exist_ok=True)
        with self._transaction() as conn:
            conn.executescript(_SCHEMA)

    # ---- plumbing -------------------------------------------------------------
    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _image_file(self, screening_id: str) -> Path:
        return self._image_dir / f"{screening_id}.img"

    # ---- writing screenings ---------------------------------------------------
    def add_screening(
        self,
        result: ScreeningResult,
        image_bytes: bytes,
        patient_ref: str,
        laterality: str,
        created_by: str,
        classifier_name: str,
    ) -> ScreeningRecord:
        """Save a fresh on-device screening as PENDING (waiting to sync)."""
        validate_patient_ref(patient_ref)
        side = parse_enum(Laterality, laterality, "laterality")
        if not created_by or not created_by.strip():
            raise RecordValidationError("created_by must not be empty.")
        quality = {
            "warnings": list(result.quality.warnings),
            "sharpness": round(result.quality.sharpness, 2),
            "brightness": round(result.quality.brightness, 2),
            "contrast": round(result.quality.contrast, 2),
        }
        return self._insert_screening(
            record_id=str(uuid.uuid4()),
            created_at=utc_now(),
            patient_ref=patient_ref,
            laterality=side,
            image_bytes=image_bytes,
            model_version=result.model_version,
            classifier_name=classifier_name,
            threshold=result.threshold,
            probability=result.probability,
            dr_detected=result.dr_detected,
            needs_review=result.needs_review,
            quality=quality,
            created_by=created_by.strip(),
            sync_status=SyncStatus.PENDING,
        )

    def import_screening(self, payload: Dict[str, Any]) -> Tuple[ScreeningRecord, bool]:
        """Server side: accept an uploaded record. Idempotent; returns (record, created)."""
        try:
            record_id = str(uuid.UUID(str(payload["id"])))
            image_bytes = base64.b64decode(payload["image_b64"], validate=True)
            probability = float(payload["probability"])
            threshold = float(payload["threshold"])
            if not (0.0 <= probability <= 1.0 and 0.0 < threshold < 1.0):
                raise ValueError("score out of range")
            existing = self._get_or_none(record_id)
            if existing is not None:
                return existing, False
            side = parse_enum(Laterality, payload["laterality"], "laterality")
            validate_patient_ref(payload["patient_ref"])
            declared = payload["image_sha256"]
            if hashlib.sha256(image_bytes).hexdigest() != declared:
                raise RecordValidationError("Image checksum does not match the upload.")
            record = self._insert_screening(
                record_id=record_id,
                created_at=str(payload["created_at"]),
                patient_ref=payload["patient_ref"],
                laterality=side,
                image_bytes=image_bytes,
                model_version=str(payload["model_version"]),
                classifier_name=str(payload["classifier_name"]),
                threshold=threshold,
                probability=probability,
                dr_detected=bool(payload["dr_detected"]),
                needs_review=bool(payload["needs_review"]),
                quality=payload.get("quality", {}),
                created_by=str(payload["created_by"]),
                sync_status=SyncStatus.SYNCED,
            )
            return record, True
        except RecordValidationError:
            raise
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise RecordValidationError(f"Malformed screening upload: {exc}") from exc

    def _insert_screening(self, *, record_id, created_at, patient_ref, laterality,
                          image_bytes, model_version, classifier_name, threshold,
                          probability, dr_detected, needs_review, quality, created_by,
                          sync_status) -> ScreeningRecord:
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise RecordValidationError("Image is empty or larger than the 8 MB limit.")
        digest = hashlib.sha256(image_bytes).hexdigest()
        path = self._image_file(record_id)
        # Write to a unique temp file and move it into place only once the row is
        # inserted, so a duplicate id can never overwrite or delete an existing image.
        temp = path.with_name(f"{record_id}.{uuid.uuid4().hex}.tmp")
        temp.write_bytes(image_bytes)
        try:
            with self._transaction() as conn:
                conn.execute(
                    "INSERT INTO screenings (id, created_at, patient_ref, laterality, "
                    "image_sha256, image_path, model_version, classifier_name, threshold, "
                    "probability, dr_detected, needs_review, quality_json, created_by, "
                    "sync_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (record_id, created_at, patient_ref, laterality.value, digest, path.name,
                     model_version, classifier_name, threshold, probability,
                     int(dr_detected), int(needs_review), json.dumps(quality),
                     created_by, sync_status.value),
                )
                os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)  # no-op after a successful replace
        return self.get(record_id)

    # ---- reading screenings ---------------------------------------------------
    def _get_or_none(self, screening_id: str) -> Optional[ScreeningRecord]:
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM screenings WHERE id = ?", (screening_id,)).fetchone()
        return _row_to_screening(row) if row else None

    def get(self, screening_id: str) -> ScreeningRecord:
        record = self._get_or_none(screening_id)
        if record is None:
            raise RecordNotFoundError(f"No screening with id {screening_id}.")
        return record

    def list_screenings(self, *, status: Optional[SyncStatus] = None,
                        needs_review: Optional[bool] = None,
                        unreviewed: Optional[bool] = None,
                        limit: int = 200) -> List[ScreeningRecord]:
        clauses, params = [], []
        if status is not None:
            clauses.append("s.sync_status = ?")
            params.append(status.value)
        if needs_review is not None:
            clauses.append("s.needs_review = ?")
            params.append(int(needs_review))
        if unreviewed is not None:
            exists = "EXISTS (SELECT 1 FROM reviews r WHERE r.screening_id = s.id)"
            clauses.append(("NOT " if unreviewed else "") + exists)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT s.* FROM screenings s {where} ORDER BY s.created_at, s.id LIMIT ?"
        with self._transaction() as conn:
            rows = conn.execute(query, (*params, max(1, min(int(limit), 1000)))).fetchall()
        return [_row_to_screening(r) for r in rows]

    def pending(self) -> List[ScreeningRecord]:
        return self.list_screenings(status=SyncStatus.PENDING, limit=1000)

    def image_bytes(self, screening_id: str) -> bytes:
        record = self.get(screening_id)
        return (self._image_dir / record.image_path).read_bytes()

    def build_sync_payload(self, screening_id: str) -> Dict[str, Any]:
        record = self.get(screening_id)
        data = record.to_dict()
        payload = {key: data[key] for key in (
            "id", "created_at", "patient_ref", "laterality", "image_sha256", "model_version",
            "classifier_name", "threshold", "probability", "dr_detected", "needs_review",
            "created_by")}
        payload["quality"] = json.loads(record.quality_json)
        payload["image_b64"] = base64.b64encode(self.image_bytes(screening_id)).decode("ascii")
        return payload

    # ---- sync bookkeeping -----------------------------------------------------
    def mark_synced(self, screening_id: str) -> None:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE screenings SET sync_status='synced', synced_at=?, last_sync_error=NULL "
                "WHERE id=?", (utc_now(), screening_id))

    def record_failure(self, screening_id: str, error: str, permanent: bool) -> None:
        status = SyncStatus.FAILED if permanent else SyncStatus.PENDING
        with self._transaction() as conn:
            conn.execute(
                "UPDATE screenings SET sync_status=?, sync_attempts=sync_attempts+1, "
                "last_sync_error=? WHERE id=?", (status.value, error[:500], screening_id))

    def reset_failed(self) -> int:
        with self._transaction() as conn:
            cur = conn.execute(
                "UPDATE screenings SET sync_status='pending' WHERE sync_status='failed'")
            return cur.rowcount

    def get_meta(self, key: str, default: str = "") -> str:
        with self._transaction() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._transaction() as conn:
            conn.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    # ---- reviews (append-only history) ---------------------------------------
    def add_review(self, screening_id: str, reviewer: str, decision: str,
                   notes: str = "") -> ReviewRecord:
        """Server side: a specialist records a decision. Earlier reviews are kept."""
        choice = parse_enum(ReviewDecision, decision, "decision")
        if not reviewer or not reviewer.strip():
            raise RecordValidationError("reviewer must not be empty.")
        if len(notes or "") > MAX_NOTES_LENGTH:
            raise RecordValidationError(f"Notes must be at most {MAX_NOTES_LENGTH} characters.")
        self.get(screening_id)  # raises RecordNotFoundError for unknown ids
        with self._transaction() as conn:
            cur = conn.execute(
                "INSERT INTO reviews (screening_id, reviewer, decision, notes, reviewed_at) "
                "VALUES (?,?,?,?,?)",
                (screening_id, reviewer.strip(), choice.value, notes or "", utc_now()))
            row = conn.execute("SELECT * FROM reviews WHERE id=?", (cur.lastrowid,)).fetchone()
        return _row_to_review(row)

    def import_remote_review(self, payload: Dict[str, Any]) -> bool:
        """Client side: store a review pulled from the server. Idempotent."""
        try:
            remote_id = str(int(payload["id"]))
            screening_id = str(payload["screening_id"])
            choice = parse_enum(ReviewDecision, payload["decision"], "decision")
            reviewer, notes, when = str(payload["reviewer"]), str(payload.get("notes", "")), str(payload["reviewed_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RecordValidationError(f"Malformed review: {exc}") from exc
        if self._get_or_none(screening_id) is None:
            return False  # a review for another clinic's patient: nothing to attach it to
        with self._transaction() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO reviews (screening_id, reviewer, decision, notes, "
                "reviewed_at, remote_id) VALUES (?,?,?,?,?,?)",
                (screening_id, reviewer, choice.value, notes, when, remote_id))
            return cur.rowcount == 1

    def reviews_for(self, screening_id: str) -> List[ReviewRecord]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM reviews WHERE screening_id=? ORDER BY id", (screening_id,)).fetchall()
        return [_row_to_review(r) for r in rows]

    def latest_review(self, screening_id: str) -> Optional[ReviewRecord]:
        history = self.reviews_for(screening_id)
        return history[-1] if history else None

    def reviews_since(self, cursor: int, limit: int = 500) -> List[ReviewRecord]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM reviews WHERE id > ? ORDER BY id LIMIT ?",
                (int(cursor), max(1, min(int(limit), 1000)))).fetchall()
        return [_row_to_review(r) for r in rows]

    # ---- aggregates -----------------------------------------------------------
    def stats(self) -> Dict[str, int]:
        with self._transaction() as conn:
            one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
            return {
                "screenings": one("SELECT COUNT(*) FROM screenings"),
                "pending_sync": one("SELECT COUNT(*) FROM screenings WHERE sync_status='pending'"),
                "failed_sync": one("SELECT COUNT(*) FROM screenings WHERE sync_status='failed'"),
                "dr_flagged": one("SELECT COUNT(*) FROM screenings WHERE dr_detected=1"),
                "needs_review": one("SELECT COUNT(*) FROM screenings WHERE needs_review=1"),
                "reviewed": one("SELECT COUNT(DISTINCT screening_id) FROM reviews"),
            }
