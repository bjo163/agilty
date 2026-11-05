from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
