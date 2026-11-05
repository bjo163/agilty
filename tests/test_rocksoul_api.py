from __future__ import annotations

import os
import tempfile
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


if __name__ == "__main__":
    unittest.main()
