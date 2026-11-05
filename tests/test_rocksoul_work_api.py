from __future__ import annotations

import base64
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from g4f.rocksoul_api import create_app
from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_execution_store import ExecutionTraceStore


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

    def test_work_item_execution_enforces_permissions_and_caps_budget(self):
        contract = {
            "schema_version": 1,
            "work_id": "api-exec-1",
            "goal": "Execute one bounded model request.",
            "acceptance_criteria": [{
                "criterion_id": "artifact",
                "description": "Artifact digest is verified.",
                "verification_method": "artifact_digest",
                "required": True,
            }],
            "risk": "low",
            "budget": {
                "max_wall_time_seconds": 5,
                "max_attempts": 2,
                "max_repairs": 0,
                "max_tokens": None,
                "max_cost_usd": None,
            },
            "permissions": ["model.execute"],
            "created_at": "2026-11-06T10:00:00+07:00",
            "deadline_at": None,
            "human_approval_required": False,
        }
        created = self.client.post("/api/v1/work-items", json=contract, headers=self.headers)
        self.assertEqual(created.status_code, 200, created.text)
        for expected, target in (
            ("pending", "planning"), ("planning", "ready"), ("ready", "running"),
        ):
            response = self.client.post(
                "/api/v1/work-items/api-exec-1/transitions",
                json={"expected_status": expected, "target_status": target},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 200, response.text)

        class FakeEngine:
            def __init__(self, database):
                self.database = database

            def execute(self, request):
                ExecutionTraceStore(self.database).record_execution_run(
                    "request-work-1", request.model, 1.0, 2.0, "success", None, 1, None,
                )
                return SimpleNamespace(
                    request_id="request-work-1", ok=True, model=request.model,
                    provider=None, outcome="success", error_class=None, error=None,
                    response=None, attempts=[],
                )

        with patch("g4f.rocksoul_api.ExecutionEngine", FakeEngine):
            executed = self.client.post(
                "/api/v1/execute",
                json={"model": "test-model", "messages": [{"role": "user", "content": "hello"}],
                      "max_attempts": 3, "max_total_time": 90, "timeout": 30, "work_id": "api-exec-1"},
                headers=self.headers,
            )
        self.assertEqual(executed.status_code, 200, executed.text)
        body = executed.json()
        self.assertEqual(body["task_outcome"], "unverified")
        self.assertEqual(body["transport_outcome"], "success")
        self.assertEqual(body["applied_budget"], {"max_attempts": 2, "max_total_time": 5.0, "timeout": 5.0})
        readback = self.client.get("/api/v1/work-items/api-exec-1", headers=self.headers).json()
        self.assertEqual(readback["status"], "running")
        self.assertEqual(readback["execution_links"][0]["request_id"], "request-work-1")

    def test_work_item_execution_denies_missing_capability(self):
        contract = {
            "schema_version": 1,
            "work_id": "api-denied-1",
            "goal": "Must not execute without permission.",
            "acceptance_criteria": [{
                "criterion_id": "artifact",
                "description": "Artifact digest is verified.",
                "verification_method": "artifact_digest",
                "required": True,
            }],
            "risk": "low",
            "budget": {"max_wall_time_seconds": 10, "max_attempts": 1, "max_repairs": 0,
                       "max_tokens": None, "max_cost_usd": None},
            "permissions": [],
            "created_at": "2026-11-06T10:00:00+07:00",
            "deadline_at": None,
            "human_approval_required": False,
        }
        self.client.post("/api/v1/work-items", json=contract, headers=self.headers)
        for expected, target in (
            ("pending", "planning"), ("planning", "ready"), ("ready", "running"),
        ):
            self.client.post(
                "/api/v1/work-items/api-denied-1/transitions",
                json={"expected_status": expected, "target_status": target},
                headers=self.headers,
            )
        denied = self.client.post(
            "/api/v1/execute",
            json={"model": "test-model", "messages": [{"role": "user", "content": "hello"}],
                  "work_id": "api-denied-1"},
            headers=self.headers,
        )
        self.assertEqual(denied.status_code, 403)

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

        artifact = b"real artifact bytes from the API test"
        verified = self.client.post(
            "/api/v1/work-items/api-work-1/criteria/artifact/verify",
            json={
                "profile_id": "artifact.check",
                "profile_version": 1,
                "artifact_base64": base64.b64encode(artifact).decode("ascii"),
                "source": "test://api/artifact-1",
                "expected_sha256": hashlib.sha256(artifact).hexdigest(),
            },
            headers=self.headers,
        )
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertEqual(verified.json()["outcome"], "pass")

        accepted = self.client.post(
            "/api/v1/work-items/api-work-1/transitions",
            json={"expected_status": "verifying", "target_status": "accepted"},
            headers=self.headers,
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["status"], "accepted")
        chain = self.client.get("/api/v1/work-items/api-work-1/verify-chain", headers=self.headers)
        self.assertEqual(chain.status_code, 200, chain.text)
        self.assertTrue(chain.json()["ok"])


if __name__ == "__main__":
    unittest.main()
