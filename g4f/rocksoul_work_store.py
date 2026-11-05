from __future__ import annotations

"""Durable WorkItem contracts and append-only lifecycle events."""

import hashlib
import json
import math
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Mapping

from .rocksoul_contracts import WorkItem, WorkStatus, validate_status_transition
from .rocksoul_db import RocksoulDB
from .rocksoul_verification import EvidenceRecord, VerificationOutcome, VerificationProfileError, VerificationProfileRegistry
from .rocksoul_verification_store import VerificationProfileStore
from .rocksoul_verifier_engine import VerificationEngine, VerificationExecution


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
CREATE INDEX IF NOT EXISTS idx_rocksoul_work_events_type ON rocksoul_work_events(event_type);
CREATE TABLE IF NOT EXISTS rocksoul_work_verifications (
    verification_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL,
    criterion_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    verifier_id TEXT NOT NULL,
    verifier_version TEXT NOT NULL,
    independence_group TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    result_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(work_id) REFERENCES rocksoul_work_items(work_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_rocksoul_work_verifications_latest
    ON rocksoul_work_verifications(work_id, criterion_id, created_at DESC);
"""


class WorkItemStoreError(ValueError):
    """WorkItem persistence or lifecycle conflict."""


class WorkItemStore:
    MAX_VERIFICATIONS_PER_CRITERION = 100

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
        prior_chain = self.verify_event_chain(item.work_id)
        if not prior_chain["ok"] and prior_chain.get("reason") != "work_item_not_found":
            raise WorkItemStoreError("existing WorkItem integrity check failed; idempotent create is blocked")
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
        accepting = target is WorkStatus.ACCEPTED or target == WorkStatus.ACCEPTED.value
        chain = self.verify_event_chain(work_id)
        if chain.get("reason") == "work_item_not_found":
            raise WorkItemStoreError("WorkItem not found")
        if not chain["ok"]:
            raise WorkItemStoreError("WorkItem evidence chain is invalid; lifecycle transition is blocked")
        registry = self.profiles.registry() if accepting else None
        try:
            encoded_payload = self._canonical(event_payload)
            if len(encoded_payload.encode("utf-8")) > 1_000_000:
                raise WorkItemStoreError("event payload must not exceed 1 MiB")
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
            if next_status is WorkStatus.RUNNING:
                contract_for_gate = WorkItem.from_dict(json.loads(row["contract_json"]))
                if contract_for_gate.human_approval_required:
                    approval = conn.execute(
                        "SELECT payload_json FROM rocksoul_work_events WHERE work_id=? AND event_type='work.approval_recorded' ORDER BY sequence DESC LIMIT 1",
                        (work_id,),
                    ).fetchone()
                    decision = json.loads(approval["payload_json"]).get("decision") if approval else None
                    if decision != "approved":
                        raise WorkItemStoreError("human approval is required before WorkItem can enter RUNNING")
            if next_status is WorkStatus.ACCEPTED:
                if "verification_results" in event_payload:
                    raise WorkItemStoreError("caller-supplied PASS values are forbidden; record verifier executions first")
                contract = WorkItem.from_dict(json.loads(row["contract_json"]))
                required = [criterion for criterion in contract.acceptance_criteria if criterion.required]
                verification_ids = []
                for criterion in required:
                    verified = conn.execute(
                        """SELECT verification_id,profile_id,profile_version,outcome,evidence_json
                           FROM rocksoul_work_verifications
                           WHERE work_id=? AND criterion_id=?
                           ORDER BY created_at DESC,rowid DESC LIMIT 1""",
                        (work_id, criterion.criterion_id),
                    ).fetchone()
                    if verified is None or verified["outcome"] != VerificationOutcome.PASS.value:
                        raise WorkItemStoreError(f"required criterion has no latest PASS verifier execution: {criterion.criterion_id}")
                    try:
                        profile = registry.resolve(verified["profile_id"], verified["profile_version"])
                        if profile.adapter_id != criterion.verification_method:
                            raise WorkItemStoreError("verification profile adapter does not match acceptance criterion")
                        evidence = tuple(EvidenceRecord(**entry) for entry in json.loads(verified["evidence_json"]))
                        registry.validate_evidence(profile, evidence)
                    except (VerificationProfileError, TypeError, ValueError) as exc:
                        raise WorkItemStoreError(f"persisted verification evidence is invalid: {exc}") from exc
                    verification_ids.append(verified["verification_id"])
                event_payload["verification_ids"] = verification_ids
            now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            conn.execute("UPDATE rocksoul_work_items SET status=?,updated_at=? WHERE work_id=?",
                         (next_status.value, now, work_id))
            self._append_event(conn, work_id, "work.status_changed", current.value, next_status.value, event_payload)
            return self.get(work_id, connection=conn)


    def record_approval(self, work_id: str, *, decision: str, approver_id: str,
                        approver_role: str, issued_at: int, nonce: str,
                        signed_payload_digest: str, signature_digest: str) -> dict[str, Any]:
        if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
            raise WorkItemStoreError("approval decision must be approved or rejected")
        if not isinstance(approver_id, str) or not approver_id.strip() or len(approver_id) > 128:
            raise WorkItemStoreError("approver identity is invalid")
        if approver_role != "admin":
            raise WorkItemStoreError("only an administrator may approve governed WorkItems")
        if isinstance(issued_at, bool) or not isinstance(issued_at, int):
            raise WorkItemStoreError("approval timestamp is invalid")
        if not isinstance(nonce, str) or len(nonce) != 32 or any(ch not in "0123456789abcdef" for ch in nonce):
            raise WorkItemStoreError("approval nonce is invalid")
        for value in (signed_payload_digest, signature_digest):
            if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise WorkItemStoreError("approval signature digest is invalid")
        chain = self.verify_event_chain(work_id)
        if chain.get("reason") == "work_item_not_found":
            raise WorkItemStoreError("WorkItem not found")
        if not chain["ok"]:
            raise WorkItemStoreError("WorkItem evidence chain is invalid; approval is blocked")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT contract_json,status FROM rocksoul_work_items WHERE work_id=?", (work_id,)).fetchone()
            if row is None:
                raise WorkItemStoreError("WorkItem not found")
            contract = WorkItem.from_dict(json.loads(row["contract_json"]))
            if not contract.human_approval_required:
                raise WorkItemStoreError("WorkItem does not require human approval")
            if row["status"] not in {
                WorkStatus.PENDING.value, WorkStatus.PLANNING.value,
                WorkStatus.READY.value, WorkStatus.BLOCKED.value,
            }:
                raise WorkItemStoreError("approval must be recorded before execution starts")
            events = conn.execute(
                "SELECT payload_json FROM rocksoul_work_events WHERE work_id=? AND event_type='work.approval_recorded' ORDER BY sequence ASC",
                (work_id,),
            ).fetchall()
            if len(events) >= 20:
                raise WorkItemStoreError("approval decision limit reached for this WorkItem")
            if any(json.loads(entry["payload_json"]).get("nonce") == nonce for entry in events):
                raise WorkItemStoreError("approval nonce has already been used")
            previous = json.loads(events[-1]["payload_json"]) if events else None
            if previous and previous.get("decision") == decision and previous.get("approver_id") == approver_id:
                raise WorkItemStoreError("identical approval decision is already recorded")
            payload = {
                "decision": decision, "approver_id": approver_id, "approver_role": approver_role,
                "issued_at": issued_at, "nonce": nonce,
                "signed_payload_digest": signed_payload_digest, "signature_digest": signature_digest,
            }
            self._append_event(conn, work_id, "work.approval_recorded", row["status"], row["status"], payload)
            return self.get(work_id, connection=conn)

    def record_verification(self, work_id: str, criterion_id: str, execution: VerificationExecution) -> dict[str, Any]:
        if not isinstance(execution, VerificationExecution):
            raise WorkItemStoreError("record_verification requires a VerificationEngine execution result")
        result = execution.result
        chain = self.verify_event_chain(work_id)
        if chain.get("reason") == "work_item_not_found":
            raise WorkItemStoreError("WorkItem not found")
        if not chain["ok"]:
            raise WorkItemStoreError("WorkItem evidence chain is invalid; verification is blocked")
        profile = self.profiles.resolve(result.profile_id, result.profile_version)
        registry = VerificationProfileRegistry((profile,))
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT contract_json,status FROM rocksoul_work_items WHERE work_id=?", (work_id,)).fetchone()
            if row is None:
                raise WorkItemStoreError("WorkItem not found")
            if row["status"] != WorkStatus.VERIFYING.value:
                raise WorkItemStoreError("verification can only be recorded while WorkItem is VERIFYING")
            contract = WorkItem.from_dict(json.loads(row["contract_json"]))
            criterion = next((item for item in contract.acceptance_criteria if item.criterion_id == criterion_id), None)
            if criterion is None:
                raise WorkItemStoreError("acceptance criterion not found")
            verification_count = int(conn.execute(
                "SELECT COUNT(*) FROM rocksoul_work_verifications WHERE work_id=? AND criterion_id=?",
                (work_id, criterion_id),
            ).fetchone()[0])
            if verification_count >= self.MAX_VERIFICATIONS_PER_CRITERION:
                raise WorkItemStoreError("verification attempt limit reached for this criterion")
            if profile.adapter_id != criterion.verification_method:
                raise WorkItemStoreError("verification profile adapter does not match acceptance criterion")
            if result.independence_group != profile.independence_group:
                raise WorkItemStoreError("verification result independence group does not match profile")
            if result.verifier_id != f"rocksoul.{profile.adapter_id}" or result.verifier_version != VerificationEngine.VERSION:
                raise WorkItemStoreError("verification result does not match the built-in verifier identity")
            if not isinstance(execution.artifact_digest, str) or len(execution.artifact_digest) != 64 or any(char not in "0123456789abcdef" for char in execution.artifact_digest):
                raise WorkItemStoreError("verifier artifact digest is invalid")
            if isinstance(execution.duration_ms, bool) or not isinstance(execution.duration_ms, (int, float)) or not math.isfinite(execution.duration_ms) or execution.duration_ms < 0:
                raise WorkItemStoreError("verifier duration must be finite and non-negative")
            if len({entry.evidence_id for entry in execution.evidence}) != len(execution.evidence):
                raise WorkItemStoreError("evidence IDs must be unique within a verifier execution")
            if any(entry.digest != execution.artifact_digest for entry in execution.evidence):
                raise WorkItemStoreError("evidence digest must match the verified artifact bytes")
            if any(entry.verifier_id != result.verifier_id or entry.verifier_version != result.verifier_version for entry in execution.evidence):
                raise WorkItemStoreError("evidence verifier identity must match the verifier result")
            if result.outcome is VerificationOutcome.PASS:
                registry.validate_evidence(profile, execution.evidence)
            elif execution.evidence:
                registry.validate_evidence(profile, execution.evidence)
            verification_id = uuid.uuid4().hex
            created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            result_payload = {
                "outcome": result.outcome.value, "profile_id": result.profile_id,
                "profile_version": result.profile_version, "verifier_id": result.verifier_id,
                "verifier_version": result.verifier_version, "independence_group": result.independence_group,
                "findings": list(result.findings),
            }
            evidence_payload = [asdict(item) for item in execution.evidence]
            verification_digest = hashlib.sha256(self._canonical({
                "verification_id": verification_id, "work_id": work_id, "criterion_id": criterion_id,
                "profile_id": profile.profile_id, "profile_version": profile.version,
                "outcome": result.outcome.value, "verifier_id": result.verifier_id,
                "verifier_version": result.verifier_version, "independence_group": result.independence_group,
                "artifact_digest": execution.artifact_digest, "duration_ms": execution.duration_ms,
                "result": result_payload, "evidence": evidence_payload, "created_at": created_at,
            }).encode("utf-8")).hexdigest()
            conn.execute(
                """INSERT INTO rocksoul_work_verifications
                   (verification_id,work_id,criterion_id,profile_id,profile_version,outcome,verifier_id,
                    verifier_version,independence_group,artifact_digest,duration_ms,result_json,evidence_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (verification_id, work_id, criterion_id, profile.profile_id, profile.version, result.outcome.value,
                 result.verifier_id, result.verifier_version, result.independence_group, execution.artifact_digest,
                 execution.duration_ms, self._canonical(result_payload), self._canonical(evidence_payload), created_at),
            )
            self._append_event(
                conn, work_id, "work.verification_recorded", row["status"], row["status"],
                {"verification_id": verification_id, "criterion_id": criterion_id,
                 "profile_id": profile.profile_id, "profile_version": profile.version,
                 "outcome": result.outcome.value, "artifact_digest": execution.artifact_digest,
                 "verification_digest": verification_digest},
            )
            return {
                "verification_id": verification_id, "work_id": work_id, "criterion_id": criterion_id,
                **result_payload, "artifact_digest": execution.artifact_digest,
                "duration_ms": execution.duration_ms, "evidence": evidence_payload, "created_at": created_at,
            }

    def attach_execution(self, work_id: str, request_id: str, transport_outcome: str, *, applied_budget: Mapping[str, Any] | None = None, attempt_count: int = 0, duration_ms: float = 0.0) -> dict[str, Any]:
        chain = self.verify_event_chain(work_id)
        if chain.get("reason") == "work_item_not_found":
            raise WorkItemStoreError("WorkItem not found")
        if not chain["ok"]:
            raise WorkItemStoreError("WorkItem evidence chain is invalid; execution linkage is blocked")
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
            raise WorkItemStoreError("request_id must be a non-empty identifier")
        if not isinstance(transport_outcome, str) or not transport_outcome.strip() or len(transport_outcome) > 64:
            raise WorkItemStoreError("transport_outcome must be a non-empty identifier")
        if applied_budget is not None and not isinstance(applied_budget, Mapping):
            raise WorkItemStoreError("applied_budget must be an object")
        if isinstance(attempt_count, bool) or not isinstance(attempt_count, int) or not 0 <= attempt_count <= 100:
            raise WorkItemStoreError("attempt_count must be an integer in [0, 100]")
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)) or not math.isfinite(duration_ms) or duration_ms < 0:
            raise WorkItemStoreError("duration_ms must be finite and non-negative")
        budget_payload = dict(applied_budget or {})
        try:
            if len(self._canonical(budget_payload).encode("utf-8")) > 4096:
                raise WorkItemStoreError("applied_budget must not exceed 4 KiB")
        except (TypeError, ValueError) as exc:
            raise WorkItemStoreError("applied_budget must contain finite JSON values") from exc
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM rocksoul_work_items WHERE work_id=?", (work_id,)).fetchone()
            if row is None:
                raise WorkItemStoreError("WorkItem not found")
            trace = conn.execute("SELECT request_id,work_id FROM execution_runs WHERE request_id=?", (request_id,)).fetchone()
            if trace is None:
                raise WorkItemStoreError("execution trace must exist before it can be linked")
            if trace["work_id"] not in (None, work_id):
                raise WorkItemStoreError("execution request is already natively linked to another WorkItem")
            conn.execute("UPDATE execution_runs SET work_id=? WHERE request_id=? AND work_id IS NULL", (work_id, request_id))
            existing_links = conn.execute(
                "SELECT work_id,payload_json FROM rocksoul_work_events WHERE event_type='work.execution_linked'",
            ).fetchall()
            for event in existing_links:
                linked = json.loads(event["payload_json"])
                if linked.get("request_id") != request_id:
                    continue
                if event["work_id"] != work_id:
                    raise WorkItemStoreError("execution request is already linked to another WorkItem")
                if (linked.get("transport_outcome") != transport_outcome
                        or linked.get("applied_budget", {}) != budget_payload
                        or linked.get("attempt_count", 0) != attempt_count
                        or linked.get("duration_ms", 0.0) != duration_ms):
                    raise WorkItemStoreError("execution request was already linked with different outcome or budget")
                return self.get(work_id, connection=conn)
            self._append_event(
                conn, work_id, "work.execution_linked", row["status"], row["status"],
                {"request_id": request_id, "transport_outcome": transport_outcome, "applied_budget": budget_payload, "attempt_count": attempt_count, "duration_ms": duration_ms},
            )
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
        verifications = connection.execute(
            """SELECT verification_id,criterion_id,profile_id,profile_version,outcome,verifier_id,
                      verifier_version,independence_group,artifact_digest,duration_ms,result_json,evidence_json,created_at
               FROM rocksoul_work_verifications WHERE work_id=? ORDER BY created_at,verification_id""", (work_id,)
        ).fetchall()
        return {
            "work_id": row["work_id"], "status": row["status"], "contract": json.loads(row["contract_json"]),
            "contract_digest": row["contract_digest"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "events": [{**{key: event[key] for key in ("event_id","sequence","event_type","from_status","to_status","previous_hash","event_hash","created_at")},
                        "payload": json.loads(event["payload_json"])} for event in events],
            "verifications": [{**{key: verification[key] for key in ("verification_id","criterion_id","profile_id","profile_version","outcome","verifier_id","verifier_version","independence_group","artifact_digest","duration_ms","created_at")},
                               "result": json.loads(verification["result_json"]), "evidence": json.loads(verification["evidence_json"])} for verification in verifications],
            "execution_links": [json.loads(event["payload_json"]) for event in events if event["event_type"] == "work.execution_linked"],
            "approvals": [json.loads(event["payload_json"]) for event in events if event["event_type"] == "work.approval_recorded"],
            "latest_approval": next((json.loads(event["payload_json"]) for event in reversed(events) if event["event_type"] == "work.approval_recorded"), None),
        }

    def list(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, min(int(offset), 100000))
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT work_id,status,contract_digest,created_at,updated_at,contract_json
                   FROM rocksoul_work_items ORDER BY created_at DESC,work_id LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            total = int(conn.execute("SELECT COUNT(*) FROM rocksoul_work_items").fetchone()[0])
            items = []
            for row in rows:
                contract = json.loads(row["contract_json"])
                approval = conn.execute(
                    "SELECT payload_json FROM rocksoul_work_events WHERE work_id=? AND event_type='work.approval_recorded' ORDER BY sequence DESC LIMIT 1",
                    (row["work_id"],),
                ).fetchone()
                items.append({
                    "work_id": row["work_id"], "status": row["status"],
                    "contract_digest": row["contract_digest"], "created_at": row["created_at"],
                    "updated_at": row["updated_at"], "risk": contract.get("risk"),
                    "human_approval_required": contract.get("human_approval_required", False),
                    "latest_approval": json.loads(approval["payload_json"]) if approval else None,
                })
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def verify_event_chain(self, work_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            item = conn.execute("SELECT status,contract_json,contract_digest,schema_version FROM rocksoul_work_items WHERE work_id=?", (work_id,)).fetchone()
            if item is None:
                return {"ok": False, "verified_events": 0, "failed_sequence": 1, "reason": "work_item_not_found"}
            rows = conn.execute("SELECT * FROM rocksoul_work_events WHERE work_id=? ORDER BY sequence", (work_id,)).fetchall()
            verification_rows = conn.execute("SELECT * FROM rocksoul_work_verifications WHERE work_id=?", (work_id,)).fetchall()
        verification_map = {entry["verification_id"]: entry for entry in verification_rows}
        try:
            contract = WorkItem.from_dict(json.loads(item["contract_json"]))
        except (TypeError, ValueError, KeyError, RecursionError):
            return {"ok": False, "verified_events": 0, "failed_sequence": 0, "reason": "contract_invalid"}
        if contract.contract_digest != item["contract_digest"] or contract.schema_version != item["schema_version"]:
            return {"ok": False, "verified_events": 0, "failed_sequence": 0, "reason": "contract_tampered"}
        previous = None
        previous_status = None
        referenced_verification_ids = set()
        created_event_seen = False
        for expected_sequence, row in enumerate(rows, start=1):
            try:
                event_payload = json.loads(row["payload_json"])
            except (TypeError, ValueError, RecursionError):
                return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "event_payload_invalid"}
            if not isinstance(event_payload, dict):
                return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "event_payload_invalid"}
            event = {
                "event_id": row["event_id"], "work_id": row["work_id"], "sequence": row["sequence"],
                "event_type": row["event_type"], "from_status": row["from_status"], "to_status": row["to_status"],
                "payload": event_payload, "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            if expected_sequence == 1 and (
                row["event_type"] != "work.created" or row["from_status"] is not None
                or row["to_status"] != WorkStatus.PENDING.value
            ):
                return {"ok": False, "verified_events": 0, "failed_sequence": 1, "reason": "creation_event_invalid"}
            if row["event_type"] == "work.created":
                if expected_sequence != 1 or event_payload.get("contract_digest") != item["contract_digest"] or event_payload.get("schema_version") != item["schema_version"]:
                    return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "creation_contract_mismatch"}
                created_event_seen = True
            status_discontinuous = expected_sequence > 1 and row["from_status"] != previous_status
            try:
                computed_event_hash = self._event_hash(event)
            except (TypeError, ValueError):
                return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "event_payload_invalid"}
            if row["sequence"] != expected_sequence or row["previous_hash"] != previous or status_discontinuous or computed_event_hash != row["event_hash"]:
                return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence}
            if row["event_type"] == "work.verification_recorded":
                payload = event["payload"]
                verification_id = payload.get("verification_id")
                referenced_verification_ids.add(verification_id)
                record = verification_map.get(verification_id)
                if record is None:
                    return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "verification_record_missing"}
                try:
                    result_payload = json.loads(record["result_json"])
                    evidence_payload = json.loads(record["evidence_json"])
                    if not isinstance(result_payload, dict) or not isinstance(evidence_payload, list):
                        raise ValueError("invalid verifier receipt shape")
                    expected_columns = {
                        "profile_id": record["profile_id"], "profile_version": record["profile_version"],
                        "outcome": record["outcome"], "verifier_id": record["verifier_id"],
                        "verifier_version": record["verifier_version"],
                        "independence_group": record["independence_group"],
                    }
                    if any(result_payload.get(key) != value for key, value in expected_columns.items()):
                        raise ValueError("verifier receipt columns do not match canonical result")
                    if (record["work_id"] != work_id or record["criterion_id"] != payload.get("criterion_id")
                            or record["profile_id"] != payload.get("profile_id")
                            or record["profile_version"] != payload.get("profile_version")
                            or record["outcome"] != payload.get("outcome")
                            or record["artifact_digest"] != payload.get("artifact_digest")):
                        raise ValueError("verifier receipt does not match lifecycle event")
                    verification_digest = hashlib.sha256(self._canonical({
                        "verification_id": record["verification_id"], "work_id": record["work_id"],
                        "criterion_id": record["criterion_id"], "profile_id": record["profile_id"],
                        "profile_version": record["profile_version"], "outcome": record["outcome"],
                        "verifier_id": record["verifier_id"], "verifier_version": record["verifier_version"],
                        "independence_group": record["independence_group"],
                        "artifact_digest": record["artifact_digest"], "duration_ms": record["duration_ms"],
                        "result": result_payload, "evidence": evidence_payload, "created_at": record["created_at"],
                    }).encode("utf-8")).hexdigest()
                except (TypeError, ValueError, RecursionError):
                    return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "verification_record_invalid"}
                if verification_digest != payload.get("verification_digest"):
                    return {"ok": False, "verified_events": expected_sequence - 1, "failed_sequence": expected_sequence, "reason": "verification_record_tampered"}
            previous = row["event_hash"]
            previous_status = row["to_status"]
        if not created_event_seen:
            return {"ok": False, "verified_events": len(rows), "failed_sequence": 1, "reason": "creation_event_missing"}
        if referenced_verification_ids != set(verification_map):
            return {"ok": False, "verified_events": len(rows), "failed_sequence": len(rows) + 1, "reason": "orphaned_verification_record"}
        if not rows or previous_status != item["status"]:
            return {"ok": False, "verified_events": len(rows), "failed_sequence": len(rows) + 1, "reason": "lifecycle_head_mismatch"}
        return {"ok": True, "verified_events": len(rows), "head_hash": previous}
