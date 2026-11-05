from __future__ import annotations

import hmac
import json
import os
import secrets
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from g4f.rocksoul_api import create_app
    from g4f.rocksoul_db import RocksoulDB
except ImportError:
    TestClient = None
    create_app = None
    RocksoulDB = None


@unittest.skipIf(TestClient is None, "FastAPI API extra is not installed")
class RocksoulApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = RocksoulDB(Path(self.temp.name) / "api.db")
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.temp.cleanup()

    def test_healthz_is_available_without_operator_key(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_status_and_providers_are_read_only(self):
        self.db.upsert_provider("fixture-provider")
        status = self.client.get("/api/v1/status")
        providers = self.client.get("/api/v1/providers")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["providers"], 1)
        self.assertEqual(providers.status_code, 200)
        self.assertEqual(providers.json()["total"], 1)

    def test_mesh_arena_and_trace_read_models(self):
        mesh = self.client.get("/api/v1/mesh")
        arena = self.client.get("/api/v1/arena")
        traces = self.client.get("/api/v1/traces")
        self.assertEqual(mesh.status_code, 200)
        self.assertIn("nodes", mesh.json())
        self.assertEqual(arena.status_code, 200)
        self.assertIn("production", arena.json())
        self.assertEqual(traces.status_code, 200)
        self.assertEqual(traces.json()["total"], 0)

    def test_provider_control_requires_operator_key(self):
        response = self.client.post("/api/v1/providers/fixture/control", json={"action": "quarantine"})
        self.assertEqual(response.status_code, 503)

    def test_provider_control_rejects_unknown_action(self):
        with patch.dict(os.environ, {"ROCKSOUL_API_KEY": "expected"}, clear=True):
            response = self.client.post(
                "/api/v1/providers/fixture/control",
                headers={"X-ROCKSOUL-API-Key": "expected"},
                json={"action": "delete"},
            )
        self.assertEqual(response.status_code, 422)

    def test_execute_requires_configured_operator_key(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/v1/execute", json={
                "model": "fixture-model",
                "messages": [{"role": "user", "content": "hello"}],
            })
        self.assertEqual(response.status_code, 503)

    def test_execute_rejects_invalid_key(self):
        with patch.dict(os.environ, {"ROCKSOUL_API_KEY": "expected"}, clear=True):
            response = self.client.post(
                "/api/v1/execute",
                headers={"X-ROCKSOUL-API-Key": "wrong"},
                json={"model": "fixture-model", "messages": [{"role": "user", "content": "hello"}]},
            )
        self.assertEqual(response.status_code, 401)

    def test_execute_rejects_oversized_message_payload(self):
        response = self.client.post("/api/v1/execute", json={
            "model": "fixture-model",
            "messages": [{"role": "user", "content": "x" * 1_000_001}],
        })
        self.assertEqual(response.status_code, 422)

    def test_execute_rejects_unknown_fields(self):
        response = self.client.post("/api/v1/execute", json={
            "model": "fixture-model",
            "messages": [{"role": "user", "content": "hello"}],
            "provider_override": "unsafe",
        })
        self.assertEqual(response.status_code, 422)


    def test_verification_profile_registry_requires_operator_key(self):
        with patch.dict(os.environ, {"ROCKSOUL_API_KEY": "expected"}, clear=True):
            missing = self.client.get("/api/v1/verification-profiles")
            wrong = self.client.get("/api/v1/verification-profiles", headers={"X-ROCKSOUL-API-Key": "wrong"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_verification_profile_register_list_and_read_are_immutable(self):
        profile = {
            "schema_version": 1,
            "profile_id": "api.artifact",
            "version": 1,
            "adapter_id": "artifact_digest",
            "evidence_requirements": [{
                "evidence_type": "artifact_digest",
                "minimum_count": 1,
                "require_digest": True,
                "require_source": True,
            }],
            "severity": "error",
            "independence_group": "api-tests",
            "deterministic": True,
            "side_effect_free": True,
            "timeout_seconds": 5,
        }
        headers = {"X-ROCKSOUL-API-Key": "expected"}
        with patch.dict(os.environ, {"ROCKSOUL_API_KEY": "expected"}, clear=True):
            created = self.client.post("/api/v1/verification-profiles", headers=headers, json=profile)
            repeated = self.client.post("/api/v1/verification-profiles", headers=headers, json=profile)
            listed = self.client.get("/api/v1/verification-profiles", headers=headers)
            fetched = self.client.get("/api/v1/verification-profiles/api.artifact/1", headers=headers)
            changed = {**profile, "independence_group": "changed"}
            conflict = self.client.post("/api/v1/verification-profiles", headers=headers, json=changed)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(created.json()["digest"], fetched.json()["digest"])
        self.assertEqual(conflict.status_code, 422)

    def test_verification_profile_rejects_non_allowlisted_adapter(self):
        profile = {
            "schema_version": 1,
            "profile_id": "api.unsafe",
            "version": 1,
            "adapter_id": "python_eval",
            "evidence_requirements": [{
                "evidence_type": "artifact_digest",
                "minimum_count": 1,
                "require_digest": True,
                "require_source": True,
            }],
        }
        with patch.dict(os.environ, {"ROCKSOUL_API_KEY": "expected"}, clear=True):
            response = self.client.post(
                "/api/v1/verification-profiles",
                headers={"X-ROCKSOUL-API-Key": "expected"},
                json=profile,
            )
        self.assertEqual(response.status_code, 422)


    def test_high_risk_work_item_requires_signed_admin_approval_before_running(self):
        headers = {"X-ROCKSOUL-API-Key": "expected"}
        contract = {
            "schema_version": 1,
            "work_id": "approval-api-work",
            "goal": "Run a governed high-risk task",
            "acceptance_criteria": [{
                "criterion_id": "result",
                "description": "A verified result exists",
                "verification_method": "artifact_digest",
                "required": True,
            }],
            "risk": "high",
            "budget": {
                "max_wall_time_seconds": 90,
                "max_attempts": 3,
                "max_repairs": 0,
                "max_tokens": None,
                "max_cost_usd": None,
            },
            "permissions": ["model.execute"],
            "created_at": "2026-11-06T00:00:00+07:00",
            "deadline_at": None,
            "human_approval_required": True,
        }
        secret = "test-approval-signing-secret-at-least-32"
        with patch.dict(os.environ, {
            "ROCKSOUL_API_KEY": "expected",
            "ROCKSOUL_APPROVAL_SIGNING_SECRET": secret,
        }, clear=True):
            created = self.client.post("/api/v1/work-items", headers=headers, json=contract)
            self.assertEqual(created.status_code, 200, created.text)
            for current, target in (("pending", "planning"), ("planning", "ready")):
                moved = self.client.post(
                    "/api/v1/work-items/approval-api-work/transitions",
                    headers=headers,
                    json={"expected_status": current, "target_status": target},
                )
                self.assertEqual(moved.status_code, 200, moved.text)
            blocked = self.client.post(
                "/api/v1/work-items/approval-api-work/transitions",
                headers=headers,
                json={"expected_status": "ready", "target_status": "running"},
            )
            self.assertEqual(blocked.status_code, 409)
            body = {
                "decision": "approved",
                "approver_id": "test-admin",
                "approver_role": "admin",
                "contract_digest": created.json()["contract_digest"],
                "issued_at": int(time.time()),
                "nonce": secrets.token_hex(16),
            }
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            signature = hmac.new(secret.encode(), canonical.encode(), "sha256").hexdigest()
            bad = self.client.post(
                "/api/v1/work-items/approval-api-work/approval",
                headers={**headers, "X-ROCKSOUL-Approval-Signature": "0" * 64},
                json=body,
            )
            self.assertEqual(bad.status_code, 401)
            approved = self.client.post(
                "/api/v1/work-items/approval-api-work/approval",
                headers={**headers, "X-ROCKSOUL-Approval-Signature": signature},
                json=body,
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            self.assertEqual(approved.json()["latest_approval"]["approver_id"], "test-admin")
            replay = self.client.post(
                "/api/v1/work-items/approval-api-work/approval",
                headers={**headers, "X-ROCKSOUL-Approval-Signature": signature},
                json=body,
            )
            self.assertEqual(replay.status_code, 409)
            running = self.client.post(
                "/api/v1/work-items/approval-api-work/transitions",
                headers=headers,
                json={"expected_status": "ready", "target_status": "running"},
            )
            self.assertEqual(running.status_code, 200, running.text)
            detail = self.client.get("/api/v1/work-items/approval-api-work", headers=headers)
            self.assertTrue(any(event["event_type"] == "work.approval_recorded" for event in detail.json()["events"]))
            chain = self.client.get("/api/v1/work-items/approval-api-work/verify-chain", headers=headers)
            self.assertTrue(chain.json()["ok"])

    def test_work_item_list_exposes_risk_and_approval_state(self):
        contract = {
            "schema_version": 1,
            "work_id": "approval-list-work",
            "goal": "Require approval",
            "acceptance_criteria": [{
                "criterion_id": "result",
                "description": "A result",
                "verification_method": "artifact_digest",
                "required": True,
            }],
            "risk": "critical",
            "budget": {"max_wall_time_seconds": 90, "max_attempts": 3, "max_repairs": 0,
                       "max_tokens": None, "max_cost_usd": None},
            "permissions": [],
            "created_at": "2026-11-06T00:00:00+07:00",
            "deadline_at": None,
            "human_approval_required": True,
        }
        with patch.dict(os.environ, {"ROCKSOUL_API_KEY": "expected"}, clear=True):
            self.client.post("/api/v1/work-items", headers={"X-ROCKSOUL-API-Key": "expected"}, json=contract)
            response = self.client.get("/api/v1/work-items", headers={"X-ROCKSOUL-API-Key": "expected"})
        self.assertEqual(response.status_code, 200)
        listed = next(item for item in response.json()["items"] if item["work_id"] == "approval-list-work")
        self.assertEqual(listed["risk"], "critical")
        self.assertTrue(listed["human_approval_required"])
        self.assertIsNone(listed["latest_approval"])


if __name__ == "__main__":
    unittest.main()
