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
"""


class WorkGraphStoreError(ValueError):
    """Graph persistence, immutability, or integrity conflict."""


class WorkGraphStore:
    MAX_LIST_LIMIT = 100

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
        return {
            "graph": json.loads(row["graph_json"]),
            "graph_digest": row["graph_digest"],
            "created_at": row["created_at"],
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

    def list(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.MAX_LIST_LIMIT:
            raise WorkGraphStoreError(f"limit must be an integer in [1, {self.MAX_LIST_LIMIT}]")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise WorkGraphStoreError("offset must be a non-negative integer")
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
