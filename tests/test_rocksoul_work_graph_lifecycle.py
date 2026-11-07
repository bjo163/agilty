from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_contracts import AcceptanceCriterion, WorkItem
from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_verification import VerificationProfile
from g4f.rocksoul_verifier_engine import VerificationEngine
from g4f.rocksoul_work_graph import WorkGraph, WorkGraphNode
from g4f.rocksoul_work_graph_store import WorkGraphStore
from g4f.rocksoul_work_graph_lifecycle import WorkGraphLifecycleError, WorkGraphLifecycleStore
from g4f.rocksoul_work_store import WorkItemStore


class WorkGraphLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = RocksoulDB(Path(self.temp.name) / "lifecycle.sqlite3")
        self.graph_store = WorkGraphStore(self.db)
        self.work_store = WorkItemStore(self.db)
        self.graph = WorkGraph("lifecycle", (
            WorkGraphNode("build", "work-build"),
            WorkGraphNode("test", "work-test", ("build",)),
        ))
        self.graph_store.create(self.graph)
        for work_id in ("work-build", "work-test"):
            self.work_store.create(WorkItem(
                work_id=work_id,
                goal="Complete " + work_id,
                acceptance_criteria=(AcceptanceCriterion(
                    criterion_id="done", description="Verified artifact", verification_method="artifact_digest"
                ),),
            ))
        self.lifecycle = WorkGraphLifecycleStore(self.graph_store, self.work_store)

    def tearDown(self):
        self.temp.cleanup()

    def _accept_build_work_item(self):
        self.work_store.transition("work-build", "verifying", expected_status="running")
        profile = VerificationProfile.from_dict({
            "schema_version": 1, "profile_id": "graph.lifecycle", "version": 1,
            "adapter_id": "artifact_digest",
            "evidence_requirements": [{
                "evidence_type": "artifact_digest", "minimum_count": 1,
                "require_digest": True, "require_source": True,
            }],
            "severity": "error", "independence_group": "graph-lifecycle",
            "deterministic": True, "side_effect_free": True, "timeout_seconds": 5,
        })
        self.work_store.profiles.register(profile)
        artifact = b"build artifact"
        receipt = VerificationEngine().verify(
            profile, artifact, source="artifact://build",
            expected_sha256=hashlib.sha256(artifact).hexdigest(),
        )
        self.work_store.record_verification("work-build", "done", receipt)
        self.work_store.transition("work-build", "accepted", expected_status="verifying")

    def test_dependency_gate_and_authoritative_acceptance(self):
        initialized = self.lifecycle.initialize("lifecycle")
        self.assertEqual(len(initialized["nodes"]), 2)
        with self.assertRaisesRegex(WorkGraphLifecycleError, "dependency build is not accepted"):
            self.lifecycle.transition(
                "lifecycle", "test", "ready", expected_status="pending", expected_version=0
            )
        self.lifecycle.transition(
            "lifecycle", "build", "ready", expected_status="pending", expected_version=0
        )
        for current, target in (
            ("pending", "planning"), ("planning", "ready"), ("ready", "running"),
        ):
            self.work_store.transition("work-build", target, expected_status=current)
        self.lifecycle.transition(
            "lifecycle", "build", "running", expected_status="ready", expected_version=1
        )
        self._accept_build_work_item()
        result = self.lifecycle.transition(
            "lifecycle", "build", "accepted", expected_status="running", expected_version=2
        )
        self.assertEqual(result["summary"]["counts"]["accepted"], 1)
        result = self.lifecycle.transition(
            "lifecycle", "test", "ready", expected_status="pending", expected_version=0
        )
        self.assertEqual({n["node_id"]: n["status"] for n in result["nodes"]},
                         {"build": "accepted", "test": "ready"})
        self.assertTrue(self.lifecycle.verify_event_chain("lifecycle")["ok"])

    def test_stale_transition_is_rejected(self):
        self.lifecycle.initialize("lifecycle")
        self.lifecycle.transition(
            "lifecycle", "build", "ready", expected_status="pending", expected_version=0
        )
        with self.assertRaisesRegex(WorkGraphLifecycleError, "stale"):
            self.lifecycle.transition(
                "lifecycle", "build", "running", expected_status="pending", expected_version=0
            )

    def test_cancellation_is_idempotent(self):
        self.lifecycle.initialize("lifecycle")
        first = self.lifecycle.transition(
            "lifecycle", "build", "cancelled", expected_status="pending", expected_version=0
        )
        second = self.lifecycle.transition(
            "lifecycle", "build", "cancelled", expected_status="pending", expected_version=0
        )
        self.assertEqual(len(first["events"]), len(second["events"]))
        self.assertEqual(second["nodes"][0]["status"], "cancelled")

    def test_optional_failure_does_not_fail_required_graph_completion(self):
        summary = self.lifecycle._summary([
            {"node_id": "required", "status": "accepted", "required": 1},
            {"node_id": "optional", "status": "failed", "required": 0},
        ])
        self.assertEqual(summary["status"], "accepted")
        self.assertEqual(summary["open_nodes"], 0)

    def test_terminal_node_cannot_be_restarted(self):
        self.lifecycle.initialize("lifecycle")
        self.lifecycle.transition(
            "lifecycle", "build", "cancelled", expected_status="pending", expected_version=0
        )
        with self.assertRaisesRegex(WorkGraphLifecycleError, "illegal lifecycle transition"):
            self.lifecycle.transition(
                "lifecycle", "build", "ready", expected_status="cancelled", expected_version=1
            )

    def test_lifecycle_event_tampering_is_detected(self):
        self.lifecycle.initialize("lifecycle")
        self.lifecycle.transition(
            "lifecycle", "build", "ready", expected_status="pending", expected_version=0
        )
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE rocksoul_work_graph_lifecycle_events SET payload_json=? WHERE graph_id=? AND node_id=?",
                (json.dumps({"reason": "tampered"}), "lifecycle", "build"),
            )
        result = self.lifecycle.verify_event_chain("lifecycle")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "lifecycle_event_tampered")


if __name__ == "__main__":
    unittest.main()
