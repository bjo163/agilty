from __future__ import annotations

"""Immutable persistence and hash-chained audit history for WorkGraphs."""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from .rocksoul_db import RocksoulDB
from .rocksoul_work_graph import WorkGraph, WorkGraphValidationError


GRAPH_SCHEMA = """
CREATE TABLE IF NOT EXISTS rocksoul_work_graphs (
    graph_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    graph_json TEXT NOT NULL,
    graph_digest TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rocksoul_work_graph_events (
    event_id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(graph_id, sequence),
    FOREIGN KEY(graph_id) REFERENCES rocksoul_work_graphs(graph_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_rocksoul_work_graph_events_graph
    ON rocksoul_work_graph_events(graph_id, sequence);
CREATE TABLE IF NOT EXISTS rocksoul_work_graph_decisions (
    graph_id TEXT NOT NULL,
    decision_digest TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(graph_id, decision_digest),
    FOREIGN KEY(graph_id) REFERENCES rocksoul_work_graphs(graph_id) ON DELETE RESTRICT
);
"""


class WorkGraphStoreError(ValueError):
    """Graph persistence, immutability, or integrity conflict."""


class WorkGraphStore:
    MAX_LIST_LIMIT = 100
    MAX_LIST_OFFSET = 1_000_000

    def __init__(self, db: RocksoulDB) -> None:
        self.db = db
        with self.db.connect() as conn:
            conn.executescript(GRAPH_SCHEMA)

    @staticmethod
    def _canonical(value: Mapping[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _hash(value: Mapping[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _append_event(self, conn: sqlite3.Connection, graph_id: str, event_type: str,
                      payload: Mapping[str, Any]) -> dict[str, Any]:
        previous = conn.execute(
            "SELECT sequence,event_hash FROM rocksoul_work_graph_events WHERE graph_id=? ORDER BY sequence DESC LIMIT 1",
            (graph_id,),
        ).fetchone()
        sequence = int(previous["sequence"]) + 1 if previous else 1
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        event = {
            "event_id": uuid.uuid4().hex,
            "graph_id": graph_id,
            "sequence": sequence,
            "event_type": event_type,
            "payload": dict(payload),
            "previous_hash": str(previous["event_hash"]) if previous else None,
            "created_at": created_at,
        }
        digest = self._hash(event)
        conn.execute(
            """INSERT INTO rocksoul_work_graph_events
               (event_id,graph_id,sequence,event_type,payload_json,previous_hash,event_hash,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (event["event_id"], graph_id, sequence, event_type, self._canonical(dict(payload)),
             event["previous_hash"], digest, created_at),
        )
        return {**event, "event_hash": digest}

    def create(self, graph: WorkGraph) -> dict[str, Any]:
        if not isinstance(graph, WorkGraph):
            raise WorkGraphStoreError("create requires a validated WorkGraph")
        encoded = self._canonical(graph.to_dict())
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT graph_digest FROM rocksoul_work_graphs WHERE graph_id=?",
                (graph.graph_id,),
            ).fetchone()
            if existing:
                if existing["graph_digest"] != graph.digest:
                    raise WorkGraphStoreError("graph_id already exists with different immutable content")
                return self.get(graph.graph_id, connection=conn)
            conn.execute(
                """INSERT INTO rocksoul_work_graphs(graph_id,schema_version,graph_json,graph_digest,created_at)
                   VALUES(?,?,?,?,?)""",
                (graph.graph_id, graph.schema_version, encoded, graph.digest, now),
            )
            self._append_event(conn, graph.graph_id, "graph.created", {
                "graph_digest": graph.digest,
                "schema_version": graph.schema_version,
                "node_count": len(graph.nodes),
            })
            return self.get(graph.graph_id, connection=conn)

    def get(self, graph_id: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        if connection is None:
            with self.db.connect() as conn:
                return self.get(graph_id, connection=conn)
        row = connection.execute(
            "SELECT * FROM rocksoul_work_graphs WHERE graph_id=?",
            (graph_id,),
        ).fetchone()
        if row is None:
            raise WorkGraphStoreError("WorkGraph not found")
        events = connection.execute(
            "SELECT * FROM rocksoul_work_graph_events WHERE graph_id=? ORDER BY sequence ASC",
            (graph_id,),
        ).fetchall()
        decisions = connection.execute(
            "SELECT decision_digest,decision_json,created_at FROM rocksoul_work_graph_decisions WHERE graph_id=? ORDER BY created_at,decision_digest",
            (graph_id,),
        ).fetchall()
        return {
            "graph": json.loads(row["graph_json"]),
            "graph_digest": row["graph_digest"],
            "created_at": row["created_at"],
            "decisions": [{
                "decision_digest": item["decision_digest"],
                "decision": json.loads(item["decision_json"]),
                "created_at": item["created_at"],
            } for item in decisions],
            "events": [{
                "event_id": item["event_id"],
                "sequence": item["sequence"],
                "event_type": item["event_type"],
                "payload": json.loads(item["payload_json"]),
                "previous_hash": item["previous_hash"],
                "event_hash": item["event_hash"],
                "created_at": item["created_at"],
            } for item in events],
        }

    def resolve_budget_and_authority(
        self,
        graph_id: str,
        graph_budget: Any,
        graph_permissions: tuple[str, ...],
        work_items: Any,
    ) -> dict[str, Any]:
        """Resolve and persist a deterministic aggregate budget/authority decision."""
        from .rocksoul_contracts import WorkItem
        from .rocksoul_work_graph_budget import resolve_graph_budget_and_authority

        if work_items is None or not callable(getattr(work_items, "get", None)) or not callable(getattr(work_items, "verify_event_chain", None)):
            raise WorkGraphStoreError("budget resolution requires a WorkItemStore-compatible object")
        integrity = self.verify_event_chain(graph_id)
        if not integrity.get("ok"):
            raise WorkGraphStoreError("WorkGraph integrity verification failed")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT graph_json,graph_digest FROM rocksoul_work_graphs WHERE graph_id=?",
                (graph_id,),
            ).fetchone()
            if row is None:
                raise WorkGraphStoreError("WorkGraph not found")
            graph = WorkGraph.from_dict(json.loads(row["graph_json"]))
            if graph.digest != row["graph_digest"]:
                raise WorkGraphStoreError("WorkGraph contract changed during budget resolution")
            contracts = {}
            for node in graph.nodes:
                child_integrity = work_items.verify_event_chain(node.work_id, connection=conn)
                if not child_integrity.get("ok"):
                    raise WorkGraphStoreError(
                        f"WorkItem integrity check failed for {node.work_id}: {child_integrity.get('reason')}"
                    )
                record = work_items.get(node.work_id, connection=conn)
                contract = WorkItem.from_dict(record["contract"])
                if contract.contract_digest != record["contract_digest"]:
                    raise WorkGraphStoreError(f"WorkItem contract digest mismatch for {node.work_id}")
                contracts[node.work_id] = contract
            try:
                decision = resolve_graph_budget_and_authority(
                    graph, graph_budget, graph_permissions, contracts
                )
                encoded = self._canonical(decision)
            except (TypeError, ValueError) as exc:
                raise WorkGraphStoreError(f"WorkGraph budget/authority resolution failed: {exc}") from exc
            created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            conn.execute(
                """INSERT OR IGNORE INTO rocksoul_work_graph_decisions
                   (graph_id,decision_digest,decision_json,created_at) VALUES(?,?,?,?)""",
                (graph_id, decision["decision_digest"], encoded, created_at),
            )
            self._append_event(conn, graph_id, "graph.budget_authority_resolved", {
                "decision_digest": decision["decision_digest"],
                "graph_digest": graph.digest,
                "node_count": len(decision["nodes"]),
            })
            return {
                "graph_id": graph_id,
                "decision": decision,
                "created_at": created_at,
                "persisted": True,
            }

    def list(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.MAX_LIST_LIMIT:
            raise WorkGraphStoreError(f"limit must be an integer in [1, {self.MAX_LIST_LIMIT}]")
        if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= self.MAX_LIST_OFFSET:
            raise WorkGraphStoreError(f"offset must be an integer in [0, {self.MAX_LIST_OFFSET}]")
        with self.db.connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM rocksoul_work_graphs").fetchone()[0])
            rows = conn.execute(
                "SELECT graph_id,graph_digest,created_at FROM rocksoul_work_graphs ORDER BY created_at DESC,graph_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return {
                "total": total,
                "items": [{
                    "graph_id": row["graph_id"],
                    "graph_digest": row["graph_digest"],
                    "created_at": row["created_at"],
                } for row in rows],
                "limit": limit,
                "offset": offset,
            }

    def resolve_readiness(self, graph_id: str, work_items: Any) -> dict[str, Any]:
        """Resolve graph readiness from authoritative WorkItem state and integrity.

        Only ACCEPTED WorkItems with a valid WorkItem event/evidence chain satisfy
        dependencies. This is a read-only resolver; it never changes child state.
        """
        if work_items is None or not callable(getattr(work_items, "get", None)) or not callable(getattr(work_items, "verify_event_chain", None)):
            raise WorkGraphStoreError("resolve_readiness requires a WorkItemStore-compatible object")
        graph_integrity = self.verify_event_chain(graph_id)
        if not graph_integrity.get("ok"):
            return {
                "graph_id": graph_id, "graph_integrity": graph_integrity,
                "nodes": [], "ready_nodes": [], "blocked_nodes": [],
                "waiting_nodes": [], "integrity_error_nodes": [],
            }
        record = self.get(graph_id)
        graph = WorkGraph.from_dict(record["graph"])
        by_id = {node.node_id: node for node in graph.nodes}
        states: dict[str, dict[str, Any]] = {}
        # Use one SQLite read snapshot so status and verified event/evidence
        # history cannot be observed from different lifecycle moments.
        with self.db.connect() as conn:
            conn.execute("BEGIN")
            for node in graph.nodes:
                integrity = work_items.verify_event_chain(node.work_id, connection=conn)
                if integrity.get("reason") == "work_item_not_found":
                    states[node.node_id] = {
                        "node_id": node.node_id, "work_id": node.work_id,
                        "status": "missing", "state": "blocked",
                        "reason": "work_item_not_found", "dependencies": list(node.depends_on),
                    }
                    continue
                if not integrity.get("ok"):
                    states[node.node_id] = {
                        "node_id": node.node_id, "work_id": node.work_id,
                        "status": None, "state": "integrity_error",
                        "reason": integrity.get("reason") or "work_item_integrity_invalid",
                        "dependencies": list(node.depends_on),
                    }
                    continue
                item = work_items.get(node.work_id, connection=conn)
                if item is None or item.get("contract_digest") is None:
                    states[node.node_id] = {
                        "node_id": node.node_id, "work_id": node.work_id,
                        "status": "missing" if item is None else item.get("status"),
                        "state": "integrity_error" if item is not None else "blocked",
                        "reason": "work_item_disappeared_after_integrity_check" if item is None else "work_item_contract_missing",
                        "dependencies": list(node.depends_on),
                    }
                    continue
                states[node.node_id] = {
                    "node_id": node.node_id, "work_id": node.work_id,
                    "status": item["status"], "state": "pending",
                    "reason": None, "dependencies": list(node.depends_on),
                    "contract_digest": item["contract_digest"],
                    "required": node.required,
                }

        terminal_failures = {"rejected", "cancelled", "expired"}
        for node_id in [item for layer in graph.topological_layers() for item in layer]:
            current = states[node_id]
            if current["state"] in {"blocked", "integrity_error"}:
                continue
            failed_dependencies = [
                dependency for dependency in by_id[node_id].depends_on
                if states[dependency]["status"] in terminal_failures
                or states[dependency]["state"] in {"blocked", "integrity_error"}
            ]
            if failed_dependencies:
                current["state"] = "blocked"
                current["reason"] = "dependency_failed_or_untrusted"
                current["blocked_by"] = failed_dependencies
                continue
            waiting_dependencies = [
                dependency for dependency in by_id[node_id].depends_on
                if states[dependency]["status"] != "accepted"
                or states[dependency]["state"] == "integrity_error"
            ]
            if waiting_dependencies:
                current["state"] = "waiting"
                current["reason"] = "dependencies_not_accepted"
                current["waiting_for"] = waiting_dependencies
                continue
            if current["status"] == "accepted":
                current["state"] = "accepted"
            elif current["status"] in {"pending", "planning", "ready"}:
                current["state"] = "ready"
            elif current["status"] == "blocked":
                current["state"] = "blocked"
                current["reason"] = "work_item_blocked"
            elif current["status"] in {"running", "verifying", "unverified", "uncertain"}:
                current["state"] = "in_progress"
            else:
                current["state"] = "blocked"
                current["reason"] = "unsupported_work_item_state"

        nodes = [states[node_id] for layer in graph.topological_layers() for node_id in layer]
        return {
            "graph_id": graph_id,
            "graph_digest": record["graph_digest"],
            "graph_integrity": graph_integrity,
            "nodes": nodes,
            "ready_nodes": [item["node_id"] for item in nodes if item["state"] == "ready"],
            "blocked_nodes": [item["node_id"] for item in nodes if item["state"] == "blocked"],
            "waiting_nodes": [item["node_id"] for item in nodes if item["state"] == "waiting"],
            "integrity_error_nodes": [item["node_id"] for item in nodes if item["state"] == "integrity_error"],
        }

    def verify_event_chain(self, graph_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            graph_row = conn.execute(
                "SELECT graph_json,graph_digest FROM rocksoul_work_graphs WHERE graph_id=?",
                (graph_id,),
            ).fetchone()
            if graph_row is None:
                return {"ok": False, "reason": "work_graph_not_found", "verified_events": 0}
            try:
                graph = WorkGraph.from_dict(json.loads(graph_row["graph_json"]))
            except (TypeError, ValueError, WorkGraphValidationError):
                return {"ok": False, "reason": "graph_contract_invalid", "verified_events": 0}
            if graph.graph_id != graph_id or graph.digest != graph_row["graph_digest"]:
                return {"ok": False, "reason": "graph_contract_tampered", "verified_events": 0}
            rows = conn.execute(
                "SELECT * FROM rocksoul_work_graph_events WHERE graph_id=? ORDER BY sequence ASC",
                (graph_id,),
            ).fetchall()
            previous_hash = None
            for index, row in enumerate(rows, start=1):
                if row["sequence"] != index or row["previous_hash"] != previous_hash:
                    return {"ok": False, "reason": "event_chain_broken", "failed_sequence": index,
                            "verified_events": index - 1}
                try:
                    payload = json.loads(row["payload_json"])
                    if not isinstance(payload, dict):
                        raise ValueError("event payload must be an object")
                    event = {
                        "event_id": row["event_id"], "graph_id": graph_id, "sequence": index,
                        "event_type": row["event_type"], "payload": payload,
                        "previous_hash": row["previous_hash"], "created_at": row["created_at"],
                    }
                except (TypeError, ValueError):
                    return {"ok": False, "reason": "event_payload_invalid", "failed_sequence": index,
                            "verified_events": index - 1}
                if self._hash(event) != row["event_hash"]:
                    return {"ok": False, "reason": "event_tampered", "failed_sequence": index,
                            "verified_events": index - 1}
                previous_hash = row["event_hash"]
            if not rows:
                return {"ok": False, "reason": "graph_event_missing", "verified_events": 0}
            first_payload = json.loads(rows[0]["payload_json"])
            if rows[0]["event_type"] != "graph.created" or first_payload.get("graph_digest") != graph.digest:
                return {"ok": False, "reason": "graph_creation_event_invalid", "verified_events": 0}
            return {"ok": True, "reason": None, "verified_events": len(rows), "graph_digest": graph.digest}
