from __future__ import annotations

"""Durable WorkItem contracts and append-only lifecycle events."""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from .rocksoul_contracts import ContractValidationError, WorkItem, WorkStatus, validate_status_transition
from .rocksoul_db import RocksoulDB
from .rocksoul_verification import EvidenceRecord, VerificationOutcome, VerificationProfileError, VerificationResult
from .rocksoul_verification_store import VerificationProfileStore


WORK_SCHEMA = """
CREATE TABLE IF NOT EXISTS rocksoul_work_items (
    work_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    contract_json TEXT NOT NULL,
    contract_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rocksoul_work_events (
    event_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(work_id, sequence),
    FOREIGN KEY(work_id) REFERENCES rocksoul_work_items(work_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_rocksoul_work_events_work ON rocksoul_work_events(work_id, sequence);
"""


class WorkItemStoreError(ValueError):
    """WorkItem persistence or lifecycle conflict."""


class WorkItemStore:
    def __init__(self, db: RocksoulDB) -> None:
        self.db = db
        self.profiles = VerificationProfileStore(db)
        with self.db.connect() as conn:
            conn.executescript(WORK_SCHEMA)

    @staticmethod
    def _canonical(value: Mapping[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _event_hash(event: Mapping[str, Any]) -> str:
        raw = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _append_event(self, conn: sqlite3.Connection, work_id: str, event_type: str,
                      from_status: str | None, to_status: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        last = conn.execute(
            "SELECT sequence,event_hash FROM rocksoul_work_events WHERE work_id=? ORDER BY sequence DESC LIMIT 1",
            (work_id,),
        ).fetchone()
        sequence = int(last["sequence"]) + 1 if last else 1
        previous_hash = str(last["event_hash"]) if last else None
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        event = {
            "event_id": uuid.uuid4().hex, "work_id": work_id, "sequence": sequence,
            "event_type": event_type, "from_status": from_status, "to_status": to_status,
            "payload": dict(payload), "previous_hash": previous_hash, "created_at": created_at,
        }
        event_hash = self._event_hash(event)
        conn.execute(
            """INSERT INTO rocksoul_work_events
               (event_id,work_id,sequence,event_type,from_status,to_status,payload_json,previous_hash,event_hash,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (event["event_id"], work_id, sequence, event_type, from_status, to_status,
             self._canonical(dict(payload)), previous_hash, event_hash, created_at),
        )
        return {**event, "event_hash": event_hash}

    def create(self, item: WorkItem) -> dict[str, Any]:
        if not isinstance(item, WorkItem):
            raise WorkItemStoreError("create requires a validated WorkItem")
        payload = self._canonical(item.to_dict())
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT contract_digest,status FROM rocksoul_work_items WHERE work_id=?", (item.work_id,)).fetchone()
            if existing:
                if existing["contract_digest"] != item.contract_digest:
                    raise WorkItemStoreError("work_id already exists with a different immutable contract")
                return self.get(item.work_id, connection=conn)  # idempotent retry
            conn.execute(
                """INSERT INTO rocksoul_work_items(work_id,schema_version,contract_json,contract_digest,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (item.work_id, item.schema_version, payload, item.contract_digest, WorkStatus.PENDING.value, now, now),
            )
            self._append_event(conn, item.work_id, "work.created", None, WorkStatus.PENDING.value,
                               {"contract_digest": item.contract_digest, "schema_version": item.schema_version})
            return self.get(item.work_id, connection=conn)

    def transition(self, work_id: str, target: WorkStatus | str, *, expected_status: WorkStatus | str,
                   payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if payload is not None and not isinstance(payload, Mapping):
            raise WorkItemStoreError("event payload must be an object")
        event_payload = dict(payload or {})
        # Payloads are persisted as JSON; reject unserializable values before acquiring a write lock.
        try:
            self._canonical(event_payload)
        except (TypeError, ValueError) as exc:
            raise WorkItemStoreError("event payload must contain finite JSON values only") from exc
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM rocksoul_work_items WHERE work_id=?", (work_id,)).fetchone()
            if row is None:
                raise WorkItemStoreError("WorkItem not found")
            current = WorkStatus(row["status"])
            expected = expected_status if isinstance(expected_status, WorkStatus) else WorkStatus(expected_status)
            if current is not expected:
                raise WorkItemStoreError(f"stale WorkItem status: expected {expected.value}, found {current.value}")
            next_status = validate_status_transition(current, target)
            if next_status is WorkStatus.ACCEPTED:
                contract = WorkItem.from_dict(json.loads(row["contract_json"]))
                results = event_payload.get("verification_results")
                if not isinstance(results, dict):
                    raise WorkItemStoreError("acceptance requires evidence-backed verification_results")
                required = {criterion.criterion_id: criterion for criterion in contract.acceptance_criteria if criterion.required}
                known = {criterion.criterion_id for criterion in contract.acceptance_criteria}
                if not set(results).issubset(known) or not set(required).issubset(results):
                    raise WorkItemStoreError("acceptance has missing or unknown criterion verification results")
                registry = self.profiles.registry()
                for criterion_id in required:
                    result = results[criterion_id]
                    if not isinstance(result, dict):
                        raise WorkItemStoreError("each verification result must be an object")
                    if set(result) - {"outcome", "profile_id", "profile_version", "verifier_id", "verifier_version", "independence_group", "evidence", "findings"}:
                        raise WorkItemStoreError("verification result contains unknown fields")
                    try:
                        profile = registry.resolve(result.get("profile_id"), result.get("profile_version"))
                        if profile.adapter_id != required[criterion_id].verification_method:
                            raise WorkItemStoreError("verification profile adapter does not match acceptance criterion")
                        if result.get("outcome") != VerificationOutcome.PASS.value:
                            raise WorkItemStoreError("only PASS verification outcomes can satisfy required criteria")
                        if result.get("independence_group") != profile.independence_group:
                            raise WorkItemStoreError("verification independence group does not match registered profile")
                        raw_evidence = result.get("evidence")
                        if not isinstance(raw_evidence, list):
                            raise WorkItemStoreError("verification evidence must be an array")
                        evidence = tuple(EvidenceRecord(**entry) for entry in raw_evidence if isinstance(entry, dict))
                        if len(evidence) != len(raw_evidence):
                            raise WorkItemStoreError("verification evidence contains invalid entries")
                        registry.validate_evidence(profile, evidence)
                        if len({entry.evidence_id for entry in evidence}) != len(evidence):
                            raise WorkItemStoreError("evidence IDs must be unique within a criterion result")
                        if any(entry.verifier_id != result.get("verifier_id") or entry.verifier_version != result.get("verifier_version") for entry in evidence):
                            raise WorkItemStoreError("evidence verifier identity must match the verification result")
                        findings = result.get("findings", [])
                        if not isinstance(findings, list):
                            raise WorkItemStoreError("verification findings must be an array")
                        VerificationResult(
                            outcome=VerificationOutcome.PASS, profile_id=profile.profile_id,
                            profile_version=profile.version, verifier_id=result.get("verifier_id"),
                            verifier_version=result.get("verifier_version"),
                            independence_group=result.get("independence_group"),
                            findings=tuple(findings),
                        )
                    except (VerificationProfileError, TypeError, ValueError) as exc:
                        raise WorkItemStoreError(f"required criterion verification is invalid: {exc}") from exc
            now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            conn.execute("UPDATE rocksoul_work_items SET status=?,updated_at=? WHERE work_id=?",
                         (next_status.value, now, work_id))
            self._append_event(conn, work_id, "work.status_changed", current.value, next_status.value, event_payload)
            return self.get(work_id, connection=conn)

    def get(self, work_id: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        if connection is None:
            with self.db.connect() as conn:
                return self.get(work_id, connection=conn)
        row = connection.execute("SELECT * FROM rocksoul_work_items WHERE work_id=?", (work_id,)).fetchone()
        if row is None:
            return None
        events = connection.execute(
            """SELECT event_id,sequence,event_type,from_status,to_status,payload_json,previous_hash,event_hash,created_at
               FROM rocksoul_work_events WHERE work_id=? ORDER BY sequence""", (work_id,)
        ).fetchall()
        return {
            "work_id": row["work_id"], "status": row["status"], "contract": json.loads(row["contract_json"]),
            "contract_digest": row["contract_digest"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "events": [{**{key: event[key] for key in ("event_id","sequence","event_type","from_status","to_status","previous_hash","event_hash","created_at")},
                        "payload": json.loads(event["payload_json"])} for event in events],
        }

    def list(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, min(int(offset), 100000))
        with self.db.connect() as conn:
            rows = conn.execute("SELECT work_id FROM rocksoul_work_items ORDER BY created_at DESC,work_id LIMIT ? OFFSET ?",
                                (limit, offset)).fetchall()
            total = int(conn.execute("SELECT COUNT(*) FROM rocksoul_work_items").fetchone()[0])
            items = [self.get(str(row["work_id"]), connection=conn) for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def verify_event_chain(self, work_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM rocksoul_work_events WHERE work_id=? ORDER BY sequence", (work_id,)).fetchall()
        previous = None
        for expected_sequence, row in enumerate(rows, start=1):
            event = {
                "event_id": row["event_id"], "work_id": row["work_id"], "sequence": row["sequence"],
                "event_type": row["event_type"], "from_status": row["from_status"], "to_status": row["to_status"],
                "payload": json.loads(row["payload_json"]), "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            if row["sequence"] != expected_sequence or row["previous_hash"] != previous or self._event_hash(event) != row["event_hash"]:
                return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence}
            previous = row["event_hash"]
        return {"ok": True, "verified_events": len(rows), "head_hash": previous}
