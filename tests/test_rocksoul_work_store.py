from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_contracts import AcceptanceCriterion, WorkItem, WorkStatus
from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_execution_store import ExecutionTraceStore
from g4f.rocksoul_verification import EvidenceRequirement, VerificationProfile
from g4f.rocksoul_verifier_engine import VerificationEngine
from g4f.rocksoul_work_store import WorkItemStore, WorkItemStoreError


def item(work_id="work-store-1"):
    return WorkItem(
        work_id=work_id,
        goal="Create a verified artifact.",
        acceptance_criteria=(AcceptanceCriterion("artifact", "Artifact exists", "artifact_digest"),),
        created_at="2026-11-06T00:00:00+07:00",
    )


def register_profile(store):
    return store.profiles.register(VerificationProfile(
        profile_id="artifact.check",
        version=1,
        adapter_id="artifact_digest",
        evidence_requirements=(EvidenceRequirement("artifact_digest"),),
        independence_group="artifact_integrity",
    ))


def to_verifying(store, work_id="work-store-1"):
    for current, target in (
        (WorkStatus.PENDING, WorkStatus.PLANNING),
        (WorkStatus.PLANNING, WorkStatus.READY),
        (WorkStatus.READY, WorkStatus.RUNNING),
        (WorkStatus.RUNNING, WorkStatus.VERIFYING),
    ):
        store.transition(work_id, target, expected_status=current)


class WorkItemStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = RocksoulDB(Path(self.temp.name) / "rocksoul.sqlite3")
        self.store = WorkItemStore(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_is_idempotent_for_same_immutable_contract(self):
        first = self.store.create(item())
        second = self.store.create(item())
        self.assertEqual(first["contract_digest"], second["contract_digest"])
        self.assertEqual(len(second["events"]), 1)

    def test_same_id_with_different_contract_is_rejected(self):
        self.store.create(item())
        changed = WorkItem(
            work_id="work-store-1",
            goal="Different goal",
            acceptance_criteria=(AcceptanceCriterion("artifact", "Artifact exists", "artifact_digest"),),
            created_at="2026-11-06T00:00:00+07:00",
        )
        with self.assertRaises(WorkItemStoreError):
            self.store.create(changed)

    def test_transition_uses_expected_status_and_event_chain(self):
        self.store.create(item())
        self.store.transition("work-store-1", WorkStatus.PLANNING, expected_status=WorkStatus.PENDING)
        with self.assertRaises(WorkItemStoreError):
            self.store.transition("work-store-1", WorkStatus.READY, expected_status=WorkStatus.PENDING)
        self.store.transition("work-store-1", WorkStatus.READY, expected_status=WorkStatus.PLANNING)
        result = self.store.verify_event_chain("work-store-1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["verified_events"], 3)

    def test_acceptance_requires_latest_executed_pass_and_evidence(self):
        self.store.create(item())
        profile = VerificationProfile(
            profile_id="artifact.check", version=1, adapter_id="artifact_digest",
            evidence_requirements=(EvidenceRequirement("artifact_digest"),),
            independence_group="artifact_integrity",
        )
        self.store.profiles.register(profile)
        to_verifying(self.store)
        engine = VerificationEngine()
        artifact = b"the exact artifact bytes"
        failed = engine.verify(
            profile, artifact, source="artifact://test/1", expected_sha256="0" * 64,
        )
        self.store.record_verification("work-store-1", "artifact", failed)
        with self.assertRaises(WorkItemStoreError):
            self.store.transition("work-store-1", WorkStatus.ACCEPTED, expected_status=WorkStatus.VERIFYING)
        passed = engine.verify(
            profile, artifact, source="artifact://test/1", expected_sha256=hashlib.sha256(artifact).hexdigest(),
        )
        self.store.record_verification("work-store-1", "artifact", passed)
        accepted = self.store.transition("work-store-1", WorkStatus.ACCEPTED, expected_status=WorkStatus.VERIFYING)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(len(accepted["verifications"]), 2)
        self.assertTrue(self.store.verify_event_chain("work-store-1")["ok"])

    def test_execution_trace_is_linked_without_auto_acceptance(self):
        self.store.create(item())
        for current, target in (
            (WorkStatus.PENDING, WorkStatus.PLANNING),
            (WorkStatus.PLANNING, WorkStatus.READY),
            (WorkStatus.READY, WorkStatus.RUNNING),
        ):
            self.store.transition("work-store-1", target, expected_status=current)
        traces = ExecutionTraceStore(self.db)
        traces.record_execution_run("request-1", "test-model", 1.0, 2.0, "success", None, 1, None)
        linked = self.store.attach_execution("work-store-1", "request-1", "success")
        self.assertEqual(linked["status"], "running")
        self.assertEqual(linked["execution_links"][0]["transport_outcome"], "success")
        again = self.store.attach_execution("work-store-1", "request-1", "success")
        self.assertEqual(len(again["execution_links"]), 1)
        with self.assertRaises(WorkItemStoreError):
            self.store.attach_execution("work-store-1", "request-1", "failure")
        self.assertTrue(self.store.verify_event_chain("work-store-1")["ok"])
    def test_acceptance_rejects_missing_profile_or_verifier_execution(self):
        self.store.create(item())
        to_verifying(self.store)
        with self.assertRaises(WorkItemStoreError):
            self.store.transition("work-store-1", WorkStatus.ACCEPTED, expected_status=WorkStatus.VERIFYING)

    def test_verification_cannot_be_recorded_before_verifying(self):
        self.store.create(item())
        profile = register_profile(self.store)
        artifact = b"artifact"
        result = VerificationEngine().verify(
            VerificationProfile.from_dict(profile["profile"]), artifact,
            source="artifact://test/2", expected_sha256=hashlib.sha256(artifact).hexdigest(),
        )
        with self.assertRaises(WorkItemStoreError):
            self.store.record_verification("work-store-1", "artifact", result)

    def test_event_chain_detects_verification_receipt_tampering(self):
        self.store.create(item())
        profile = VerificationProfile(
            profile_id="artifact.check", version=1, adapter_id="artifact_digest",
            evidence_requirements=(EvidenceRequirement("artifact_digest"),),
            independence_group="artifact_integrity",
        )
        self.store.profiles.register(profile)
        to_verifying(self.store)
        artifact = b"tamper-evident artifact"
        execution = VerificationEngine().verify(
            profile, artifact, source="artifact://test/receipt",
            expected_sha256=hashlib.sha256(artifact).hexdigest(),
        )
        recorded = self.store.record_verification("work-store-1", "artifact", execution)
        with self.db.connect() as conn:
            conn.execute("UPDATE rocksoul_work_verifications SET evidence_json='[]' WHERE verification_id=?",
                         (recorded["verification_id"],))
        result = self.store.verify_event_chain("work-store-1")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "verification_record_tampered")
    def test_event_chain_detects_immutable_contract_mutation(self):
        self.store.create(item())
        changed = item().to_dict()
        changed["goal"] = "tampered but schema-valid"
        with self.db.connect() as conn:
            conn.execute("UPDATE rocksoul_work_items SET contract_json=? WHERE work_id=?",
                         (json.dumps(changed), "work-store-1"))
        result = self.store.verify_event_chain("work-store-1")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "contract_tampered")
    def test_event_chain_detects_tampering(self):
        self.store.create(item())
        self.store.transition("work-store-1", WorkStatus.PLANNING, expected_status=WorkStatus.PENDING)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE rocksoul_work_events SET payload_json=? WHERE work_id=? AND sequence=1",
                ('{"contract_digest":"tampered","schema_version":1}', "work-store-1"),
            )
        result = self.store.verify_event_chain("work-store-1")
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_sequence"], 1)

    def test_event_payload_must_be_json_safe(self):
        self.store.create(item())
        with self.assertRaises(WorkItemStoreError):
            self.store.transition(
                "work-store-1", WorkStatus.PLANNING, expected_status=WorkStatus.PENDING,
                payload={"bad": float("nan")},
            )

    def test_terminal_state_cannot_be_restarted(self):
        self.store.create(item())
        self.store.transition("work-store-1", WorkStatus.CANCELLED, expected_status=WorkStatus.PENDING)
        with self.assertRaises(Exception):
            self.store.transition("work-store-1", WorkStatus.PLANNING, expected_status=WorkStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
