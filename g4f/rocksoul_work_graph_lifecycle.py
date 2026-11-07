from __future__ import annotations

"""Atomic WorkGraph node lifecycle with append-only, hash-chained events."""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from .rocksoul_work_graph import WorkGraph, WorkGraphValidationError
from .rocksoul_work_graph_store import WorkGraphStore, WorkGraphStoreError
from .rocksoul_work_store import WorkItemStore


class WorkGraphLifecycleError(ValueError):
    """Invalid lifecycle transition or graph state conflict."""


_NODE_TRANSITIONS = {
    "pending": {"ready", "blocked", "cancelled", "expired"},
    "ready": {"running", "blocked", "cancelled", "expired"},
    "running": {"accepted", "failed", "rejected", "cancelled", "expired", "uncertain"},
    "accepted": set(),
    "failed": set(),
    "rejected": set(),
    "cancelled": set(),
    "expired": set(),
    "uncertain": set(),
    "blocked": set(),
}
_TERMINAL = {"accepted", "failed", "rejected", "cancelled", "expired", "uncertain", "blocked"}

LIFECYCLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS rocksoul_work_graph_node_state (
    graph_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    work_id TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(graph_id,node_id),
    UNIQUE(graph_id,work_id),
    FOREIGN KEY(graph_id) REFERENCES rocksoul_work_graphs(graph_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rocksoul_work_graph_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    expected_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(graph_id,node_id,sequence),
    FOREIGN KEY(graph_id,node_id) REFERENCES rocksoul_work_graph_node_state(graph_id,node_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_graph_lifecycle_events
    ON rocksoul_work_graph_lifecycle_events(graph_id,node_id,sequence);
"""


class WorkGraphLifecycleStore:
    def __init__(self, graph_store: WorkGraphStore, work_items: WorkItemStore) -> None:
        if graph_store.db is not work_items.db:
            raise WorkGraphLifecycleError("graph and WorkItem stores must share one database")
        self.graph_store = graph_store
        self.work_items = work_items
        self.db = graph_store.db
        with self.db.connect() as conn:
            conn.executescript(LIFECYCLE_SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(rocksoul_work_graph_node_state)")}
            if "required" not in columns:
                conn.execute("ALTER TABLE rocksoul_work_graph_node_state ADD COLUMN required INTEGER NOT NULL DEFAULT 1")

    @staticmethod
    def _canonical(value: Mapping[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    @classmethod
    def _hash(cls, value: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls._canonical(value).encode("utf-8")).hexdigest()

    def initialize(self, graph_id: str) -> dict[str, Any]:
        integrity = self.graph_store.verify_event_chain(graph_id)
        if not integrity.get("ok"):
            raise WorkGraphLifecycleError("WorkGraph integrity verification failed")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            lifecycle_integrity = self.verify_event_chain(graph_id, connection=conn)
            if not lifecycle_integrity.get("ok"):
                raise WorkGraphLifecycleError("WorkGraph lifecycle integrity verification failed")
            graph_row = conn.execute(
                "SELECT graph_json,graph_digest FROM rocksoul_work_graphs WHERE graph_id=?",
                (graph_id,),
            ).fetchone()
            if graph_row is None:
                raise WorkGraphLifecycleError("WorkGraph not found")
            graph = WorkGraph.from_dict(json.loads(graph_row["graph_json"]))
            if graph.digest != graph_row["graph_digest"]:
                raise WorkGraphLifecycleError("WorkGraph contract changed during initialization")
            for node in graph.nodes:
                conn.execute(
                    """INSERT OR IGNORE INTO rocksoul_work_graph_node_state
                       (graph_id,node_id,work_id,status,version,required,reason,updated_at)
                       VALUES(?,?,?,'pending',0,?,NULL,?)""",
                    (graph_id,node.node_id,node.work_id,int(node.required),datetime.now(timezone.utc).isoformat(timespec="microseconds")),
                )
            rows = conn.execute(
                "SELECT node_id,work_id,status,version,required,reason,updated_at FROM rocksoul_work_graph_node_state WHERE graph_id=? ORDER BY node_id",
                (graph_id,),
            ).fetchall()
            if len(rows) != len(graph.nodes) or any(
                row["work_id"] != next(n.work_id for n in graph.nodes if n.node_id == row["node_id"])
                for row in rows
            ):
                raise WorkGraphLifecycleError("existing lifecycle state does not match immutable graph")
            return {"graph_id": graph_id, "nodes": [dict(row) for row in rows]}

    def get(self, graph_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT node_id,work_id,status,version,required,reason,updated_at FROM rocksoul_work_graph_node_state WHERE graph_id=? ORDER BY node_id",
                (graph_id,),
            ).fetchall()
            if not rows:
                raise WorkGraphLifecycleError("WorkGraph lifecycle is not initialized")
            events = conn.execute(
                "SELECT * FROM rocksoul_work_graph_lifecycle_events WHERE graph_id=? ORDER BY node_id,sequence",
                (graph_id,),
            ).fetchall()
            return {
                "graph_id": graph_id,
                "nodes": [dict(row) for row in rows],
                "events": [{
                    "event_id": row["event_id"], "node_id": row["node_id"],
                    "sequence": row["sequence"], "from_status": row["from_status"],
                    "to_status": row["to_status"], "expected_version": row["expected_version"],
                    "payload": json.loads(row["payload_json"]),
                    "previous_hash": row["previous_hash"], "event_hash": row["event_hash"],
                    "created_at": row["created_at"],
                } for row in events],
                "summary": self._summary(rows),
            }

    @staticmethod
    def _summary(rows) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for row in rows:
            status = row["status"]
            counts[status] = counts.get(status, 0) + 1
        required_rows = [row for row in rows if bool(row["required"])]
        required_open = sum(1 for row in required_rows if row["status"] not in _TERMINAL)
        required_failed = any(row["status"] in {"failed", "rejected", "expired", "uncertain", "blocked"} for row in required_rows)
        required_cancelled = any(row["status"] == "cancelled" for row in required_rows)
        if required_open:
            graph_status = "running" if counts.get("running") or counts.get("ready") else "pending"
        elif required_failed:
            graph_status = "failed"
        elif required_cancelled:
            graph_status = "cancelled"
        else:
            graph_status = "accepted"
        return {"status": graph_status, "counts": counts, "open_nodes": required_open}

    def transition(
        self,
        graph_id: str,
        node_id: str,
        target: str,
        *,
        expected_status: str,
        expected_version: int,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if target not in _NODE_TRANSITIONS or expected_status not in _NODE_TRANSITIONS:
            raise WorkGraphLifecycleError("unknown lifecycle status")
        if not isinstance(payload or {}, Mapping):
            raise WorkGraphLifecycleError("event payload must be an object")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
            raise WorkGraphLifecycleError("expected_version must be a non-negative integer")
        encoded_payload = self._canonical(dict(payload or {}))
        if len(encoded_payload.encode("utf-8")) > 65536:
            raise WorkGraphLifecycleError("lifecycle event payload exceeds 64 KiB")
        if target == "cancelled":
            try:
                snapshot = self.get(graph_id)
                current_node = next((item for item in snapshot["nodes"] if item["node_id"] == node_id), None)
                if current_node is not None and current_node["status"] == "cancelled":
                    return snapshot
            except WorkGraphLifecycleError:
                pass
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            graph_row = conn.execute(
                "SELECT graph_json,graph_digest FROM rocksoul_work_graphs WHERE graph_id=?",
                (graph_id,),
            ).fetchone()
            if graph_row is None:
                raise WorkGraphLifecycleError("WorkGraph not found")
            try:
                graph = WorkGraph.from_dict(json.loads(graph_row["graph_json"]))
            except (TypeError, ValueError, WorkGraphValidationError) as exc:
                raise WorkGraphLifecycleError("WorkGraph contract is invalid") from exc
            if graph.digest != graph_row["graph_digest"]:
                raise WorkGraphLifecycleError("WorkGraph integrity check failed")
            node = next((item for item in graph.nodes if item.node_id == node_id), None)
            if node is None:
                raise WorkGraphLifecycleError("WorkGraph node not found")
            row = conn.execute(
                "SELECT * FROM rocksoul_work_graph_node_state WHERE graph_id=? AND node_id=?",
                (graph_id,node_id),
            ).fetchone()
            if row is None:
                raise WorkGraphLifecycleError("WorkGraph lifecycle is not initialized")
            current = row["status"]
            if current != expected_status or int(row["version"]) != expected_version:
                raise WorkGraphLifecycleError("stale lifecycle state; expected status/version does not match")
            if target not in _NODE_TRANSITIONS[current]:
                raise WorkGraphLifecycleError(f"illegal lifecycle transition: {current} -> {target}")
            # A node can become ready only after every dependency's WorkItem has
            # been accepted and its evidence chain verifies in this same transaction.
            if target == "ready":
                states = {
                    item["node_id"]: item["status"]
                    for item in conn.execute(
                        "SELECT node_id,status FROM rocksoul_work_graph_node_state WHERE graph_id=?",
                        (graph_id,),
                    ).fetchall()
                }
                for dependency in node.depends_on:
                    if states.get(dependency) != "accepted":
                        raise WorkGraphLifecycleError(f"dependency {dependency} is not accepted")
            # Child state is authoritative: graph lifecycle never substitutes
            # graph-level assertions for WorkItem approval or verifier acceptance.
            child_integrity = self.work_items.verify_event_chain(node.work_id, connection=conn)
            if not child_integrity.get("ok"):
                raise WorkGraphLifecycleError(f"WorkItem integrity check failed: {child_integrity.get('reason')}")
            child = self.work_items.get(node.work_id, connection=conn)
            if target == "running" and child["status"] != "running":
                raise WorkGraphLifecycleError("WorkItem must enter RUNNING through its own approval gate first")
            if target == "accepted" and child["status"] != "accepted":
                raise WorkGraphLifecycleError("WorkItem must be verifier-accepted before graph node acceptance")
            now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            sequence_row = conn.execute(
                "SELECT sequence,event_hash FROM rocksoul_work_graph_lifecycle_events WHERE graph_id=? AND node_id=? ORDER BY sequence DESC LIMIT 1",
                (graph_id,node_id),
            ).fetchone()
            sequence = int(sequence_row["sequence"]) + 1 if sequence_row else 1
            event = {
                "event_id": uuid.uuid4().hex,
                "graph_id": graph_id,
                "node_id": node_id,
                "sequence": sequence,
                "from_status": current,
                "to_status": target,
                "expected_version": expected_version,
                "payload": json.loads(encoded_payload),
                "previous_hash": sequence_row["event_hash"] if sequence_row else None,
                "created_at": now,
            }
            digest = self._hash(event)
            updated = conn.execute(
                """UPDATE rocksoul_work_graph_node_state
                   SET status=?,version=version+1,reason=?,updated_at=?
                   WHERE graph_id=? AND node_id=? AND status=? AND version=?""",
                (target, (payload or {}).get("reason"), now, graph_id,node_id,current,expected_version),
            )
            if updated.rowcount != 1:
                raise WorkGraphLifecycleError("concurrent lifecycle transition conflict")
            conn.execute(
                """INSERT INTO rocksoul_work_graph_lifecycle_events
                   (event_id,graph_id,node_id,sequence,from_status,to_status,expected_version,payload_json,previous_hash,event_hash,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (event["event_id"],graph_id,node_id,sequence,current,target,expected_version,
                 encoded_payload,event["previous_hash"],digest,now),
            )
        return self.get(graph_id)

    def verify_event_chain(
        self, graph_id: str, *, connection: sqlite3.Connection | None = None
    ) -> dict[str, Any]:
        if connection is None:
            with self.db.connect() as conn:
                return self.verify_event_chain(graph_id, connection=conn)
        conn = connection
    with self.db.connect() as conn:
        states = conn.execute(
            "SELECT node_id,status,version FROM rocksoul_work_graph_node_state WHERE graph_id=? ORDER BY node_id",
            (graph_id,),
        ).fetchall()
        if not states:
            return {"ok": False, "reason": "lifecycle_not_initialized", "verified_events": 0}
        rows = conn.execute(
            "SELECT * FROM rocksoul_work_graph_lifecycle_events WHERE graph_id=? ORDER BY node_id,sequence",
            (graph_id,),
        ).fetchall()
        previous: dict[str, str | None] = {}
        previous_status: dict[str, str] = {}
        counts: dict[str, int] = {}
        for row in rows:
            node_id = row["node_id"]
            expected_sequence = counts.get(node_id, 0) + 1
            expected_from = previous_status.get(node_id, "pending")
            if (row["sequence"] != expected_sequence or row["previous_hash"] != previous.get(node_id)
                    or row["from_status"] != expected_from or row["to_status"] not in _NODE_TRANSITIONS.get(expected_from, set())):
                return {"ok": False, "reason": "lifecycle_chain_discontinuous", "node_id": node_id}
            try:
                payload = json.loads(row["payload_json"])
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                event = {
                    "event_id": row["event_id"], "graph_id": graph_id, "node_id": node_id,
                    "sequence": row["sequence"], "from_status": row["from_status"],
                    "to_status": row["to_status"], "expected_version": row["expected_version"],
                    "payload": payload,
                    "previous_hash": row["previous_hash"], "created_at": row["created_at"],
                }
            except (TypeError, ValueError):
                return {"ok": False, "reason": "lifecycle_payload_invalid", "node_id": node_id}
            if self._hash(event) != row["event_hash"]:
                return {"ok": False, "reason": "lifecycle_event_tampered", "node_id": node_id}
            previous[node_id] = row["event_hash"]
            previous_status[node_id] = row["to_status"]
            counts[node_id] = expected_sequence
        for state in states:
            if counts.get(state["node_id"], 0) != int(state["version"]):
                return {"ok": False, "reason": "lifecycle_state_version_mismatch", "node_id": state["node_id"]}
            node_events = [row for row in rows if row["node_id"] == state["node_id"]]
            if node_events and node_events[-1]["to_status"] != state["status"]:
                return {"ok": False, "reason": "lifecycle_state_mismatch", "node_id": state["node_id"]}
            if not node_events and state["status"] != "pending":
                return {"ok": False, "reason": "lifecycle_initial_state_invalid", "node_id": state["node_id"]}
        return {"ok": True, "verified_events": len(rows), "nodes": len(states)}
