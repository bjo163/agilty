from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_db import RocksoulDB
from g4f.rocksoul_verification import EvidenceRequirement, VerificationProfile, VerificationProfileError
from g4f.rocksoul_verification_store import VerificationProfileStore


class VerificationProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = VerificationProfileStore(RocksoulDB(Path(self.temp.name) / "rocksoul.sqlite3"))

    def tearDown(self):
        self.temp.cleanup()

    def profile(self, timeout=10):
        return VerificationProfile(
            profile_id="json.check", version=1, adapter_id="json_schema",
            evidence_requirements=(EvidenceRequirement("json_validation"),),
            timeout_seconds=timeout,
        )

    def test_register_is_idempotent_and_resolvable(self):
        first = self.store.register(self.profile())
        second = self.store.register(self.profile())
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(self.store.resolve("json.check", 1), self.profile())

    def test_registered_version_is_immutable(self):
        self.store.register(self.profile())
        with self.assertRaises(VerificationProfileError):
            self.store.register(self.profile(timeout=20))

    def test_registry_rejects_tampered_profile_json(self):
        self.store.register(self.profile())
        with self.store.db.connect() as conn:
            conn.execute(
                "UPDATE rocksoul_verification_profiles SET profile_json=? WHERE profile_id=? AND version=?",
                ('{"schema_version":1}', "json.check", 1),
            )
        with self.assertRaises(VerificationProfileError):
            self.store.registry()

    def test_registry_loads_persisted_profiles(self):
        self.store.register(self.profile())
        registry = self.store.registry()
        self.assertEqual(registry.resolve("json.check", 1), self.profile())


if __name__ == "__main__":
    unittest.main()
