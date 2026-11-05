from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from g4f.rocksoul_arena_production_cli import main


class RocksoulArenaProductionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = str(self.root / "rocksoul.db")
        self.dataset = self.root / "dataset.json"
        self.dataset_bytes = b'{"cases":[1,2,3]}\n'
        self.dataset.write_bytes(self.dataset_bytes)
        self.manifest = self.root / "pack.json"
        self.write_manifest()

    def write_manifest(self, *, schema_version: int = 1, sha256: str | None = None) -> None:
        value = {
            "schema_version": schema_version,
            "pack": {
                "name": "cli-contract-pack",
                "version": "1",
                "suite": {
                    "name": "cli-contract-suite",
                    "version": "1",
                    "evaluator": "json_exact",
                    "provenance": {"source": "unit-test", "network": False},
                    "cases": [
                        {"case_id": "case-a", "input": {"x": 1}, "expected": {"x": 1}},
                        {"case_id": "case-b", "input": [2, 1], "expected": [1, 2]},
                    ],
                },
                "dataset": {
                    "source": "local-test-artifact",
                    "revision": "test-revision-1",
                    "sha256": sha256 or hashlib.sha256(self.dataset_bytes).hexdigest(),
                    "split_policy": "public_only",
                    "contamination_review": "synthetic test data; no external content",
                    "license": "test-only",
                },
                "evaluator_revision": "json-exact-v1",
                "repeat_policy": {"runs": 2, "max_score_stddev": 0.0},
                "environment_requirements": {"network": "offline", "runtime": "python"},
                "network_requirements": {"required": False, "mode": "offline"},
            },
        }
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

    def invoke(self, *args: str) -> tuple[int, object]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--db", self.db, *args])
        return code, json.loads(output.getvalue())

    def test_validate_manifest_and_verify_exact_dataset_artifact(self) -> None:
        code, unchecked = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 0)
        self.assertFalse(unchecked["artifact_verified"])
        self.assertFalse(unchecked["ready_to_register"])
        self.assertFalse(unchecked["network_calls"])

        code, checked = self.invoke(
            "validate-pack", str(self.manifest), "--dataset-file", str(self.dataset)
        )
        self.assertEqual(code, 0)
        self.assertTrue(checked["artifact_verified"])
        self.assertTrue(checked["ready_to_register"])

    def test_register_rejects_mismatched_artifact_without_persisting_pack(self) -> None:
        self.dataset.write_bytes(b"wrong dataset")
        code, payload = self.invoke(
            "register-pack", str(self.manifest), "--dataset-file", str(self.dataset)
        )
        self.assertEqual(code, 2)
        self.assertIn("SHA-256 mismatch", payload["error"])
        code, packs = self.invoke("list-packs")
        self.assertEqual(code, 0)
        self.assertEqual(packs, [])

    def test_register_list_and_campaign_readback(self) -> None:
        code, registered = self.invoke(
            "register-pack", str(self.manifest), "--dataset-file", str(self.dataset)
        )
        self.assertEqual(code, 0)
        self.assertTrue(registered["registered"])
        self.assertTrue(registered["artifact_verified"])

        code, packs = self.invoke("list-packs")
        self.assertEqual(code, 0)
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0]["manifest"]["dataset"]["sha256"], registered["dataset_sha256"])

        code, fixture = self.invoke("fixture-campaign")
        self.assertEqual(code, 0)
        self.assertTrue(fixture["variance_accepted"])
        self.assertEqual(fixture["scores"], [100.0, 100.0, 100.0])
        self.assertEqual(fixture["environment"]["network_mode"], "offline")

        code, campaigns = self.invoke("list-campaigns")
        self.assertEqual(code, 0)
        self.assertEqual(len(campaigns), 1)
        code, stored = self.invoke("show-campaign", fixture["campaign_id"])
        self.assertEqual(code, 0)
        self.assertEqual(stored["run_ids"], fixture["run_ids"])

    def test_unknown_campaign_has_stable_not_found_exit_code(self) -> None:
        code, payload = self.invoke("show-campaign", "missing")
        self.assertEqual(code, 3)
        self.assertFalse(payload["found"])

    def test_manifest_rejects_duplicate_keys_and_non_finite_case_values(self) -> None:
        self.manifest.write_text(
            '{"schema_version":1,"schema_version":1,"pack":{}}',
            encoding="utf-8",
        )
        code, payload = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("duplicate JSON key", payload["error"])

        self.write_manifest()
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["pack"]["suite"]["cases"][0]["input"] = float("nan")
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        code, payload = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("finite JSON values", payload["error"])

    def test_manifest_rejects_unrepresentable_numeric_values_as_json_errors(self) -> None:
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["pack"]["suite"]["cases"][0]["weight"] = 10**1000
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        code, payload = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("finite number", payload["error"])

        self.write_manifest()
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["pack"]["repeat_policy"]["max_score_stddev"] = 10**1000
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        code, payload = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("finite number", payload["error"])

    def test_manifest_rejects_unknown_or_unsupported_schema(self) -> None:
        self.write_manifest(schema_version=2)
        code, payload = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("schema_version", payload["error"])

        self.write_manifest()
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["pack"]["unexpected"] = "typo"
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        code, payload = self.invoke("validate-pack", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("unknown fields", payload["error"])



    def test_verify_campaign_and_campaign_report_commands(self) -> None:
        code, fixture = self.invoke("fixture-campaign")
        self.assertEqual(code, 0)
        code, audit = self.invoke("verify-campaign", fixture["campaign_id"])
        self.assertEqual(code, 0)
        self.assertTrue(audit["integrity_verified"])
        self.assertEqual(audit["quality_certification"], "NOT_CERTIFIED")

        code, report = self.invoke("campaign-report", "--pack-digest", fixture["pack_digest"])
        self.assertEqual(code, 0)
        self.assertEqual(report["report_status"], "EVIDENCE_VERIFIED")
        self.assertEqual(report["campaign_count"], 1)
        self.assertEqual(report["quality_certification"], "NOT_CERTIFIED")

    def test_verify_campaign_and_campaign_report_fail_closed(self) -> None:
        code, payload = self.invoke("verify-campaign", "missing-campaign")
        self.assertEqual(code, 3)
        self.assertFalse(payload["found"])

        code, report = self.invoke("campaign-report", "--pack-digest", "0" * 64)
        self.assertEqual(code, 3)
        self.assertEqual(report["report_status"], "NO_PACK")

        code, fixture = self.invoke("fixture-campaign")
        self.assertEqual(code, 0)
        from g4f.rocksoul_db import RocksoulDB
        with RocksoulDB(Path(self.db)).connect() as conn:
            run_id = fixture["run_ids"][0]
            conn.execute("UPDATE arena_runs SET score=0 WHERE id=?", (run_id,))
        code, audit = self.invoke("verify-campaign", fixture["campaign_id"])
        self.assertEqual(code, 4)
        self.assertFalse(audit["integrity_verified"])
        code, report = self.invoke("campaign-report", "--pack-digest", fixture["pack_digest"])
        self.assertEqual(code, 4)
        self.assertEqual(report["report_status"], "EVIDENCE_REJECTED")

    def test_live_campaign_requires_both_explicit_opt_ins_before_provider_resolution(self) -> None:
        self.write_manifest()
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        for case in value["pack"]["suite"]["cases"]:
            case["input"] = {"prompt": "return the word pass"}
            case["expected"] = "pass"
        value["pack"]["network_requirements"] = {"required": True, "mode": "online"}
        value["pack"]["environment_requirements"] = {"python": "any", "operating_system": "any"}
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        code, payload = self.invoke("run-campaign", str(self.manifest), "--dataset-file", str(self.dataset),
            "--provider", "FakeProvider", "--model", "fake-model", "--provider-revision", "rev-1",
            "--runtime-revision", "runtime-1", "--network-mode", "online", "--region", "test",
            "--confirm-pack-digest", "not-the-real-digest")
        self.assertEqual(code, 2)
        self.assertIn("--confirm-live", payload["error"])

        with patch.dict(os.environ, {}, clear=True), patch(
            "g4f.rocksoul_arena_production_cli._resolve_live_provider"
        ) as resolve:
            code, payload = self.invoke("run-campaign", str(self.manifest), "--dataset-file", str(self.dataset),
                "--provider", "FakeProvider", "--model", "fake-model", "--provider-revision", "rev-1",
                "--runtime-revision", "runtime-1", "--network-mode", "online", "--region", "test",
                "--confirm-live", "--confirm-pack-digest", "not-the-real-digest")
        self.assertEqual(code, 2)
        self.assertIn("ROCKSOUL_ALLOW_LIVE_ARENA=1", payload["error"])
        resolve.assert_not_called()

    def test_live_campaign_requires_registered_hash_verified_pack(self) -> None:
        self.write_manifest()
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        for case in value["pack"]["suite"]["cases"]:
            case["input"] = {"prompt": "return pass"}
            case["expected"] = "pass"
        value["pack"]["network_requirements"] = {"required": True, "mode": "online"}
        value["pack"]["environment_requirements"] = {"python": "any", "operating_system": "any"}
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        from g4f.rocksoul_arena_production_cli import load_pack_manifest
        digest = load_pack_manifest(self.manifest).digest
        with patch.dict(os.environ, {"ROCKSOUL_ALLOW_LIVE_ARENA": "1"}), patch(
            "g4f.rocksoul_arena_production_cli._resolve_live_provider"
        ) as resolve:
            code, payload = self.invoke("run-campaign", str(self.manifest), "--dataset-file", str(self.dataset),
                "--provider", "FakeProvider", "--model", "fake-model", "--provider-revision", "rev-1",
                "--runtime-revision", "runtime-1", "--network-mode", "online", "--region", "test",
                "--confirm-live", "--confirm-pack-digest", digest)
        self.assertEqual(code, 2)
        self.assertIn("not registered", payload["error"])
        resolve.assert_not_called()

    def test_live_campaign_runs_only_after_registration_and_persists_exact_evidence(self) -> None:
        self.write_manifest()
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        for case in value["pack"]["suite"]["cases"]:
            case["input"] = {"prompt": "return the word pass"}
            case["expected"] = "pass"
        value["pack"]["network_requirements"] = {"required": True, "mode": "online"}
        value["pack"]["environment_requirements"] = {"python": "any", "operating_system": "any"}
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        code, registered = self.invoke("register-pack", str(self.manifest), "--dataset-file", str(self.dataset))
        self.assertEqual(code, 0)
        fake_provider = type("FakeProvider", (), {})
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="pass"))])
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
        from g4f.rocksoul_arena_production_cli import load_pack_manifest
        digest = load_pack_manifest(self.manifest).digest
        with patch.dict(os.environ, {"ROCKSOUL_ALLOW_LIVE_ARENA": "1"}), patch(
            "g4f.rocksoul_arena_production_cli._resolve_live_provider", return_value=fake_provider
        ), patch("g4f.client.Client", return_value=fake_client):
            code, payload = self.invoke("run-campaign", str(self.manifest), "--dataset-file", str(self.dataset),
                "--provider", "FakeProvider", "--model", "fake-model", "--provider-revision", "provider-rev-1",
                "--runtime-revision", "runtime-rev-1", "--network-mode", "online", "--region", "test-region",
                "--confirm-live", "--confirm-pack-digest", digest, "--max-requests", "4")
        self.assertEqual(code, 0)
        self.assertTrue(payload["variance_accepted"])
        self.assertTrue(payload["artifact_verified"])
        self.assertEqual(payload["campaign_kind"], "operator-authorized-live")
        self.assertEqual(payload["provider_requests"], 4)
        self.assertEqual(payload["target"]["provider"], "FakeProvider")
        self.assertEqual(payload["target"]["runtime_revision"], "runtime-rev-1")
        self.assertEqual(payload["environment"]["network_mode"], "online")
        self.assertEqual(len(payload["run_ids"]), 2)
        code, stored = self.invoke("show-campaign", payload["campaign_id"])
        self.assertEqual(code, 0)
        self.assertEqual(stored["target"]["model"], "fake-model")

if __name__ == "__main__":
    unittest.main()
