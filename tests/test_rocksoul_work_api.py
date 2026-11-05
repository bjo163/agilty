from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from g4f.rocksoul_api import create_app
from g4f.rocksoul_db import RocksoulDB


class RocksoulWorkApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = RocksoulDB(Path(self.temp.name) / "rocksoul-api.sqlite3")
        self.env = patch.dict(os.environ, {"ROCKSOUL_API_KEY": "test-operator-key"})
        self.env.start()
        self.client = TestClient(create_app(self.db))
        self.headers = {"X-ROCKSOUL-API-Key": "test-operator-key"}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_work_and_profile_reads_require_operator_key(self):
        self.assertEqual(self.client.get("/api/v1/work-items").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/verification-profiles").status_code, 401)

    def test_profile_and_work_item_lifecycle_api(self):
        profile = {
            "schema_version": 1,
            "profile_id": "artifact.check",
            "version": 1,
            "adapter_id": "artifact_digest",
            "evidence_requirements": [{
                "evidence_type": "artifact_digest",
                "minimum_count": 1,
                "require_digest": True,
                "require_source": True,
            }],
            "severity": "error",
            "independence_group": "artifact_integrity",
            "deterministic": True,
            "side_effect_free": True,
            "timeout_seconds": 10,
        }
        response = self.client.post("/api/v1/verification-profiles", json=profile, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/v1/verification-profiles", headers=self.headers).json()["total"], 1)

        contract = {
            "schema_version": 1,
            "work_id": "api-work-1",
            "goal": "Create an artifact.",
            "acceptance_criteria": [{
                "criterion_id": "artifact",
                "description": "Artifact exists.",
                "verification_method": "artifact_digest",
                "required": True,
            }],
            "risk": "low",
            "budget": {
                "max_wall_time_seconds": 30,
                "max_attempts": 2,
                "max_repairs": 0,
                "max_tokens": None,
                "max_cost_usd": None,
            },
            "permissions": [],
            "created_at": "2026-11-06T10:00:00+07:00",
            "deadline_at": None,
            "human_approval_required": False,
        }
        created = self.client.post("/api/v1/work-items", json=contract, headers=self.headers)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["status"], "pending")
        self.assertEqual(self.client.get("/api/v1/work-items/api-work-1", headers=self.headers).status_code, 200)

        for expected, target in (
            ("pending", "planning"),
            ("planning", "ready"),
            ("ready", "running"),
            ("running", "verifying"),
        ):
            moved = self.client.post(
                "/api/v1/work-items/api-work-1/transitions",
                json={"expected_status": expected, "target_status": target},
                headers=self.headers,
            )
            self.assertEqual(moved.status_code, 200, moved.text)

        evidence = {
            "evidence_id": "api-ev-1",
            "evidence_type": "artifact_digest",
            "source": "artifact://sha256/test",
            "digest": "b" * 64,
            "captured_at": "2026-11-06T10:05:00+07:00",
            "verifier_id": "artifact-checker",
            "verifier_version": "1.0.0",
        }
        accepted = self.client.post(
            "/api/v1/work-items/api-work-1/transitions",
            json={
                "expected_status": "verifying",
                "target_status": "accepted",
                "payload": {
                    "verification_results": {
                        "artifact": {
                            "outcome": "pass",
                            "profile_id": "artifact.check",
                            "profile_version": 1,
                            "verifier_id": "artifact-checker",
                            "verifier_version": "1.0.0",
                            "independence_group": "artifact_integrity",
                            "evidence": [evidence],
                        }
                    }
                },
            },
            headers=self.headers,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["status"], "accepted")
        chain = self.client.get("/api/v1/work-items/api-work-1/verify-chain", headers=self.headers)
        self.assertEqual(chain.status_code, 200, chain.text)
        self.assertTrue(chain.json()["ok"])


if __name__ == "__main__":
    unittest.main()
