from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_work_graph import WorkGraph, WorkGraphNode
from g4f.rocksoul_work_graph_store import WorkGraphStore, WorkGraphStoreError
from g4f.rocksoul_contracts import AcceptanceCriterion, ExecutionBudget, WorkItem
from g4f.rocksoul_work_graph_budget import WorkGraphBudget
from g4f.rocksoul_work_store import WorkItemStore
from g4f.rocksoul_verification import VerificationProfile
from g4f.rocksoul_verifier_engine import VerificationEngine


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
        with self.assertRaises(WorkGraphStoreError):
            self.store.list(offset=1_000_001)

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


    def test_budget_authority_decision_is_persisted_and_idempotent(self):
        work_store = WorkItemStore(self.db)
        for work_id in ("work-build", "work-test"):
            work_store.create(WorkItem(
                work_id=work_id,
                goal="Bounded graph work",
                acceptance_criteria=(AcceptanceCriterion(
                    criterion_id="done", description="Complete", verification_method="manual",
                ),),
                budget=ExecutionBudget(
                    max_wall_time_seconds=30, max_attempts=1, max_repairs=0,
                    max_tokens=1000, max_cost_usd=1.0,
                ),
                permissions=("files.read", "network.fetch"),
            ))
        budget = WorkGraphBudget(
            max_wall_time_seconds=120, max_attempts=4, max_repairs=2,
            max_tokens=5000, max_cost_usd=5.0,
        )
        first = self.store.resolve_budget_and_authority(
            "pipeline", budget, ("files.read",), work_store
        )
        second = self.store.resolve_budget_and_authority(
            "pipeline", budget, ("files.read",), work_store
        )
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["decision"]["decision_digest"], second["decision"]["decision_digest"])
        record = self.store.get("pipeline")
        self.assertEqual(len(record["decisions"]), 1)
        self.assertEqual(record["decisions"][0]["decision_digest"], first["decision"]["decision_digest"])
        self.assertEqual(record["decisions"][0]["decision"]["nodes"][0]["permissions"], ["files.read"])

    def test_missing_graph_has_stable_failure(self):
        result = self.store.verify_event_chain("missing")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "work_graph_not_found")

    def test_readiness_uses_authoritative_work_item_state(self):
        self.store.create(self.graph)
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

    def test_only_accepted_verified_dependency_unblocks_downstream(self):
        self.store.create(self.graph)
        work_store = WorkItemStore(self.db)
        for work_id, criterion_id, method in (
            ("work-build", "artifact", "artifact_digest"),
            ("work-test", "tests", "pytest"),
        ):
            work_store.create(WorkItem(
                work_id=work_id,
                goal="Complete " + work_id,
                acceptance_criteria=(AcceptanceCriterion(
                    criterion_id=criterion_id, description="Verified output",
                    verification_method=method,
                ),),
            ))
        profile = VerificationProfile.from_dict({
            "schema_version": 1, "profile_id": "graph.artifact", "version": 1,
            "adapter_id": "artifact_digest",
            "evidence_requirements": [{
                "evidence_type": "artifact_digest", "minimum_count": 1,
                "require_digest": True, "require_source": True,
            }],
            "severity": "error", "independence_group": "graph-tests",
            "deterministic": True, "side_effect_free": True, "timeout_seconds": 5,
        })
        work_store.profiles.register(profile)
        for current, target in (
            ("pending", "planning"), ("planning", "ready"),
            ("ready", "running"), ("running", "verifying"),
        ):
            work_store.transition("work-build", target, expected_status=current)
        artifact = b"verified-build-output"
        execution = VerificationEngine().verify(
            profile, artifact, source="artifact://graph-tests/build",
            expected_sha256=hashlib.sha256(artifact).hexdigest(),
        )
        work_store.record_verification("work-build", "artifact", execution)
        work_store.transition("work-build", "accepted", expected_status="verifying")

        result = self.store.resolve_readiness("pipeline", work_store)
        states = {item["node_id"]: item for item in result["nodes"]}
        self.assertEqual(states["build"]["state"], "accepted")
        self.assertEqual(states["test"]["state"], "ready")
        self.assertEqual(result["ready_nodes"], ["test"])

    def test_readiness_blocks_missing_work_items(self):
        self.store.create(self.graph)
        result = self.store.resolve_readiness("pipeline", WorkItemStore(self.db))
        self.assertEqual(result["blocked_nodes"], ["build", "test"])
        self.assertEqual(result["blocked_nodes"][0], "build")
        self.assertEqual(result["nodes"][0]["reason"], "work_item_not_found")

    def test_readiness_fails_closed_on_malformed_work_item_contract_json(self):
        self.store.create(self.graph)
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
            conn.execute("UPDATE rocksoul_work_items SET contract_json=? WHERE work_id=?",
                         ("{malformed", "work-build"))
        result = self.store.resolve_readiness("pipeline", work_store)
        self.assertEqual(result["integrity_error_nodes"], ["build"])
        states = {item["node_id"]: item for item in result["nodes"]}
        self.assertEqual(states["build"]["state"], "integrity_error")
        self.assertEqual(states["test"]["state"], "blocked")

    def test_readiness_fails_closed_on_invalid_work_item_chain(self):
        self.store.create(self.graph)
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
        self.assertEqual({n["node_id"]: n for n in result["nodes"]}["test"]["state"], "blocked")


if __name__ == "__main__":
    unittest.main()
