from __future__ import annotations

import hashlib
import unittest

from g4f.rocksoul_verification import EvidenceRequirement, VerificationOutcome, VerificationProfile
from g4f.rocksoul_verifier_engine import VerificationEngine


class VerificationEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = VerificationEngine()

    def profile(self, adapter="artifact_digest", evidence="artifact_digest"):
        return VerificationProfile(
            profile_id=f"test.{adapter}",
            version=1,
            adapter_id=adapter,
            evidence_requirements=(EvidenceRequirement(evidence),),
            independence_group=f"tests.{adapter}",
            timeout_seconds=2,
        )

    def test_artifact_digest_passes_only_for_exact_bytes(self):
        artifact = b"immutable artifact"
        result = self.engine.verify(
            self.profile(), artifact, source="artifact://test/one",
            expected_sha256=hashlib.sha256(artifact).hexdigest(),
        )
        self.assertEqual(result.result.outcome, VerificationOutcome.PASS)
        self.assertEqual(result.evidence[0].digest, hashlib.sha256(artifact).hexdigest())
        self.assertEqual(result.evidence[0].verifier_id, "rocksoul.artifact_digest")

    def test_artifact_digest_mismatch_is_fail(self):
        result = self.engine.verify(
            self.profile(), b"artifact", source="artifact://test/two",
            expected_sha256="0" * 64,
        )
        self.assertEqual(result.result.outcome, VerificationOutcome.FAIL)

    def test_missing_expected_digest_is_error_not_pass(self):
        result = self.engine.verify(self.profile(), b"artifact", source="artifact://test/three")
        self.assertEqual(result.result.outcome, VerificationOutcome.ERROR)

    def test_json_schema_adapter_validates_bounded_subset(self):
        schema = {
            "type": "object",
            "required": ["name", "count"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "minLength": 2},
                "count": {"type": "integer", "minimum": 1},
            },
        }
        valid = self.engine.verify(
            self.profile("json_schema", "json_validation"),
            b'{"name":"rock","count":3}',
            source="artifact://json/valid",
            schema=schema,
        )
        invalid = self.engine.verify(
            self.profile("json_schema", "json_validation"),
            b'{"name":"x","count":0,"extra":true}',
            source="artifact://json/invalid",
            schema=schema,
        )
        self.assertEqual(valid.result.outcome, VerificationOutcome.PASS)
        self.assertEqual(invalid.result.outcome, VerificationOutcome.FAIL)

    def test_unsupported_allowlisted_adapter_fails_closed(self):
        result = self.engine.verify(
            self.profile("pytest", "test_receipt"),
            b"receipt",
            source="artifact://receipt/one",
        )
        self.assertEqual(result.result.outcome, VerificationOutcome.ERROR)
        self.assertEqual(result.evidence, ())

    def test_rejects_empty_or_oversized_artifacts(self):
        for artifact in (b"", b"x" * (VerificationEngine.MAX_ARTIFACT_BYTES + 1)):
            with self.subTest(length=len(artifact)), self.assertRaises(ValueError):
                self.engine.verify(self.profile(), artifact, source="artifact://test/large",
                                   expected_sha256=hashlib.sha256(artifact).hexdigest())

    def test_non_finite_json_and_malformed_schema_constraints_fail_closed(self):
        non_finite = self.engine.verify(
            self.profile("json_schema", "json_validation"),
            b'{"value":NaN}',
            source="artifact://json/non-finite",
            schema={"type": "object"},
        )
        malformed = self.engine.verify(
            self.profile("json_schema", "json_validation"),
            b'{"name":"ok"}',
            source="artifact://json/malformed-schema",
            schema={"type": "object", "properties": {"name": {"type": "string", "minLength": "two"}}},
        )
        self.assertEqual(non_finite.result.outcome, VerificationOutcome.FAIL)
        self.assertEqual(malformed.result.outcome, VerificationOutcome.FAIL)

    def test_unsupported_schema_keywords_fail_closed(self):
        result = self.engine.verify(
            self.profile("json_schema", "json_validation"),
            b'{"name":"rock"}',
            source="artifact://json/unsupported",
            schema={"type": "object", "patternProperties": {}},
        )
        self.assertEqual(result.result.outcome, VerificationOutcome.FAIL)


if __name__ == "__main__":
    unittest.main()
