from __future__ import annotations

import unittest

from g4f.rocksoul_verification import (
    EvidenceRecord, EvidenceRequirement, VerificationOutcome, VerificationProfile,
    VerificationProfileError, VerificationProfileRegistry, VerificationResult,
)


def profile(**overrides):
    values = {
        "profile_id": "code.tests",
        "version": 1,
        "adapter_id": "pytest",
        "evidence_requirements": (EvidenceRequirement("test_receipt"),),
        "independence_group": "deterministic_tests",
    }
    values.update(overrides)
    return VerificationProfile(**values)


def evidence(**overrides):
    values = {
        "evidence_id": "ev-1",
        "evidence_type": "test_receipt",
        "source": "ci://run/123",
        "digest": "a" * 64,
        "captured_at": "2026-11-06T10:00:00+07:00",
        "verifier_id": "pytest-adapter",
        "verifier_version": "1.0.0",
    }
    values.update(overrides)
    return EvidenceRecord(**values)


class VerificationProfileTests(unittest.TestCase):
    def test_profile_round_trip_and_digest(self):
        item = profile()
        restored = VerificationProfile.from_dict(item.to_dict())
        self.assertEqual(restored, item)
        self.assertEqual(restored.digest, item.digest)
        self.assertEqual(len(item.digest), 64)

    def test_rejects_unknown_fields_and_schema_versions(self):
        payload = profile().to_dict()
        payload["dynamic_import"] = "os"
        with self.assertRaises(VerificationProfileError):
            VerificationProfile.from_dict(payload)
        payload = profile().to_dict()
        payload["schema_version"] = 2
        with self.assertRaises(VerificationProfileError):
            VerificationProfile.from_dict(payload)

    def test_adapter_must_be_allowlisted(self):
        with self.assertRaises(VerificationProfileError):
            profile(adapter_id="arbitrary_python_callable")

    def test_timeout_is_finite_and_bounded(self):
        for value in (0, -1, 300.1, float("inf"), float("nan"), True):
            with self.subTest(value=value), self.assertRaises(VerificationProfileError):
                profile(timeout_seconds=value)

    def test_registry_versions_are_immutable(self):
        registry = VerificationProfileRegistry((profile(),))
        registry.register(profile())
        with self.assertRaises(VerificationProfileError):
            registry.register(profile(timeout_seconds=20))
        with self.assertRaises(VerificationProfileError):
            registry.resolve("code.tests", 2)

    def test_independence_groups_are_explicit(self):
        registry = VerificationProfileRegistry((profile(), profile(profile_id="api.contract", adapter_id="http_contract", independence_group="http_contracts")))
        self.assertEqual(registry.independence_groups(), ("deterministic_tests", "http_contracts"))

    def test_empty_and_insufficient_evidence_fail_closed(self):
        registry = VerificationProfileRegistry((profile(),))
        selected = registry.resolve("code.tests", 1)
        with self.assertRaises(VerificationProfileError):
            registry.validate_evidence(selected, ())
        with self.assertRaises(VerificationProfileError):
            registry.validate_evidence(selected, (evidence(evidence_type="other"),))

    def test_evidence_requires_digest_and_provenance(self):
        with self.assertRaises(VerificationProfileError):
            evidence(digest="not-a-digest")
        with self.assertRaises(VerificationProfileError):
            evidence(source="")

    def test_only_pass_satisfies_required_criterion(self):
        for outcome in (VerificationOutcome.FAIL, VerificationOutcome.INCONCLUSIVE, VerificationOutcome.ERROR, VerificationOutcome.SKIPPED):
            result = VerificationResult(outcome, "code.tests", 1, "pytest", "1.0", "deterministic_tests")
            self.assertFalse(result.satisfies_required_criterion)
        passed = VerificationResult(VerificationOutcome.PASS, "code.tests", 1, "pytest", "1.0", "deterministic_tests")
        self.assertTrue(passed.satisfies_required_criterion)

    def test_pass_cannot_hide_findings(self):
        with self.assertRaises(VerificationProfileError):
            VerificationResult(VerificationOutcome.PASS, "code.tests", 1, "pytest", "1.0", "deterministic_tests", ("failed test",))


if __name__ == "__main__":
    unittest.main()
