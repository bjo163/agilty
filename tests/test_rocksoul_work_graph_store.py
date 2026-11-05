from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_work_graph import WorkGraph, WorkGraphNode
from g4f.rocksoul_work_graph_store import WorkGraphStore, WorkGraphStoreError
from g4f.rocksoul_contracts import AcceptanceCriterion, WorkItem
from g4f.rocksoul_work_store import WorkItemStore


class WorkGraphStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = RocksoulDB(Path(self.temp.name) / "rocksoul.sqlite3")
        self.store = WorkGraphStore(self.db)
        self.graph = WorkGraph("pipeline", (
            WorkGraphNode("build", "work-build"),
            WorkGraphNode("test", "work-test", ("build",)),
        ))

    def tearDown(self):
        self.temp.cleanup()

    def test_create_is_idempotent_and_persists_integrity_event(self):
        first = self.store.create(self.graph)
        second = self.store.create(self.graph)
        self.assertEqual(first["graph_digest"], second["graph_digest"])
        self.assertEqual(len(second["events"]), 1)
        self.assertTrue(self.store.verify_event_chain("pipeline")["ok"])

    def test_graph_id_is_immutable(self):
        self.store.create(self.graph)
        changed = WorkGraph("pipeline", (
            WorkGraphNode("build", "work-build"),
            WorkGraphNode("test", "work-test", ("build",)),
            WorkGraphNode("docs", "work-docs"),
        ))
        with self.assertRaises(WorkGraphStoreError):
            self.store.create(changed)

    def test_get_and_bounded_pagination(self):
        self.store.create(self.graph)
        fetched = self.store.get("pipeline")
        self.assertEqual(fetched["graph"]["graph_id"], "pipeline")
        listed = self.store.list(limit=1, offset=0)
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["items"][0]["graph_id"], "pipeline")
        with self.assertRaises(WorkGraphStoreError):
            self.store.list(limit=101)
        with self.assertRaises(WorkGraphStoreError):
            self.store.list(offset=-1)

    def test_detects_event_payload_tampering(self):
        self.store.create(self.graph)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE rocksoul_work_graph_events SET payload_json=? WHERE graph_id=? AND sequence=1",
                (json.dumps({"graph_digest": "0" * 64}), "pipeline"),
            )
        result = self.store.verify_event_chain("pipeline")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "event_tampered")

    def test_detects_graph_contract_mutation(self):
        self.store.create(self.graph)
        changed = WorkGraph("pipeline", (WorkGraphNode("different", "work-different"),))
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE rocksoul_work_graphs SET graph_json=? WHERE graph_id=?",
                (json.dumps(changed.to_dict()), "pipeline"),
            )
        result = self.store.verify_event_chain("pipeline")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "graph_contract_tampered")

    def test_missing_graph_has_stable_failure(self):
        result = self.store.verify_event_chain("missing")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "work_graph_not_found")

    def test_readiness_uses_authoritative_work_item_state(self):
        work_store = WorkItemStore(self.db)
        work_store.create(WorkItem(
            work_id="work-build",
            goal="Build the artifact",
            acceptance_criteria=(AcceptanceCriterion(
                criterion_id="artifact", description="Artifact digest is recorded",
                verification_method="artifact_digest",
            ),),
        ))
        work_store.create(WorkItem(
            work_id="work-test",
            goal="Test the artifact",
            acceptance_criteria=(AcceptanceCriterion(
                criterion_id="tests", description="Tests pass",
                verification_method="pytest",
            ),),
        ))
        result = self.store.resolve_readiness("pipeline", work_store)
        self.assertEqual(result["ready_nodes"], ["build"])
        self.assertEqual(result["waiting_nodes"], ["test"])
        states = {item["node_id"]: item for item in result["nodes"]}
        self.assertEqual(states["build"]["state"], "ready")
        self.assertEqual(states["test"]["waiting_for"], ["build"])

    def test_readiness_blocks_missing_work_items(self):
        result = self.store.resolve_readiness("pipeline", WorkItemStore(self.db))
        self.assertEqual(result["blocked_nodes"], ["build"])
        self.assertEqual(result["blocked_nodes"][0], "build")
        self.assertEqual(result["nodes"][0]["reason"], "work_item_not_found")

    def test_readiness_fails_closed_on_invalid_work_item_chain(self):
        work_store = WorkItemStore(self.db)
        work_store.create(WorkItem(
            work_id="work-build",
            goal="Build the artifact",
            acceptance_criteria=(AcceptanceCriterion(
                criterion_id="artifact", description="Artifact digest is recorded",
                verification_method="artifact_digest",
            ),),
        ))
        work_store.create(WorkItem(
            work_id="work-test",
            goal="Test the artifact",
            acceptance_criteria=(AcceptanceCriterion(
                criterion_id="tests", description="Tests pass",
                verification_method="pytest",
            ),),
        ))
        with self.db.connect() as conn:
            conn.execute("UPDATE rocksoul_work_events SET payload_json=? WHERE work_id=? AND sequence=1",
                         (json.dumps({"contract_digest": "0" * 64, "schema_version": 1}), "work-build"))
        result = self.store.resolve_readiness("pipeline", work_store)
        self.assertEqual(result["integrity_error_nodes"], ["build"])
        self.assertEqual(result["integrity_error_nodes"], ["build"])
        self.assertEqual({n["node_id"]: n for n in result["nodes"]}["test"]["state"], "blocked")


if __name__ == "__main__":
    unittest.main()
