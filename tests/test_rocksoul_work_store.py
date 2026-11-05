from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_contracts import AcceptanceCriterion, WorkItem, WorkStatus
from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_verification import EvidenceRequirement, VerificationProfile
from g4f.rocksoul_work_store import WorkItemStore, WorkItemStoreError


def item(work_id="work-store-1"):
    return WorkItem(
        work_id=work_id,
        goal="Create a verified artifact.",
        acceptance_criteria=(AcceptanceCriterion("artifact", "Artifact exists", "artifact_digest"),),
        created_at="2026-11-06T00:00:00+07:00",
    )


def verified_result(outcome="pass"):
    return {
        "artifact": {
            "outcome": outcome,
            "profile_id": "artifact.check",
            "profile_version": 1,
            "verifier_id": "artifact-digest-adapter",
            "verifier_version": "1.0.0",
            "independence_group": "artifact_integrity",
            "evidence": [{
                "evidence_id": "ev-1",
                "evidence_type": "artifact_digest",
                "source": "artifact://sha256/abc",
                "digest": "a" * 64,
                "captured_at": "2026-11-06T10:00:00+07:00",
                "verifier_id": "artifact-digest-adapter",
                "verifier_version": "1.0.0",
            }],
        }
    }


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

    def test_acceptance_requires_registered_profile_and_pass_evidence(self):
        self.store.create(item())
        self.store.profiles.register(VerificationProfile(
            profile_id="artifact.check",
            version=1,
            adapter_id="artifact_digest",
            evidence_requirements=(EvidenceRequirement("artifact_digest"),),
            independence_group="artifact_integrity",
        ))
        for current, target in (
            (WorkStatus.PENDING, WorkStatus.PLANNING),
            (WorkStatus.PLANNING, WorkStatus.READY),
            (WorkStatus.READY, WorkStatus.RUNNING),
            (WorkStatus.RUNNING, WorkStatus.VERIFYING),
        ):
            self.store.transition("work-store-1", target, expected_status=current)
        with self.assertRaises(WorkItemStoreError):
            self.store.transition(
                "work-store-1", WorkStatus.ACCEPTED, expected_status=WorkStatus.VERIFYING,
                payload={"verification_results": verified_result("inconclusive")},
            )
        accepted = self.store.transition(
            "work-store-1", WorkStatus.ACCEPTED, expected_status=WorkStatus.VERIFYING,
            payload={"verification_results": verified_result()},
        )
        self.assertEqual(accepted["status"], "accepted")

    def test_acceptance_rejects_missing_profile_or_evidence(self):
        self.store.create(item())
        for current, target in (
            (WorkStatus.PENDING, WorkStatus.PLANNING),
            (WorkStatus.PLANNING, WorkStatus.READY),
            (WorkStatus.READY, WorkStatus.RUNNING),
            (WorkStatus.RUNNING, WorkStatus.VERIFYING),
        ):
            self.store.transition("work-store-1", target, expected_status=current)
        with self.assertRaises(WorkItemStoreError):
            self.store.transition(
                "work-store-1", WorkStatus.ACCEPTED, expected_status=WorkStatus.VERIFYING,
                payload={"verification_results": verified_result()},
            )

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
            self.store.transition(
                "work-store-1", WorkStatus.PLANNING, expected_status=WorkStatus.CANCELLED,
            )


if __name__ == "__main__":
    unittest.main()
