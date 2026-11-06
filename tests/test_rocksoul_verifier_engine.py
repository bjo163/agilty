from __future__ import annotations

import hashlib
import json
import unittest

from g4f.rocksoul_verification import EvidenceRequirement, VerificationOutcome, VerificationProfile, VerificationProfileError
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

    def test_profile_rejects_non_allowlisted_adapter(self):
        with self.assertRaises(VerificationProfileError):
            self.profile("shell", "test_receipt")

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


    def test_numeric_schema_bounds_reject_non_finite_and_boolean_values(self):
        profile = self.profile("json_schema", "json_validation")
        for schema in (
            {"type": "object", "properties": {"value": {"type": "number", "minimum": float("inf")}}},
            {"type": "object", "properties": {"value": {"type": "number", "maximum": float("nan")}}},
            {"type": "object", "properties": {"value": {"type": "number", "minimum": True}}},
        ):
            with self.subTest(schema=schema):
                result = self.engine.verify(
                    profile, b'{"value":1}', source="artifact://json/bad-bound", schema=schema,
                )
                self.assertEqual(result.result.outcome, VerificationOutcome.FAIL)

    def test_numeric_schema_bounds_enforce_valid_ranges(self):
        profile = self.profile("json_schema", "json_validation")
        valid = self.engine.verify(
            profile, b'{"value":3}', source="artifact://json/range-valid",
            schema={"type": "object", "properties": {"value": {"type": "number", "minimum": 1, "maximum": 5}}},
        )
        invalid = self.engine.verify(
            profile, b'{"value":8}', source="artifact://json/range-invalid",
            schema={"type": "object", "properties": {"value": {"type": "number", "minimum": 1, "maximum": 5}}},
        )
        self.assertEqual(valid.result.outcome, VerificationOutcome.PASS)
        self.assertEqual(invalid.result.outcome, VerificationOutcome.FAIL)



    def test_pytest_junit_receipt_passes_only_when_all_cases_pass(self):
        report = b'<testsuite name="pytest" tests="2"><testcase classname="sample" name="test_one"/><testcase classname="sample" name="test_two"/></testsuite>'
        result = self.engine.verify(
            self.profile("pytest", "test_receipt"), report, source="ci://run/123/junit.xml",
        )
        self.assertEqual(result.result.outcome, VerificationOutcome.PASS)
        self.assertEqual(result.evidence[0].evidence_type, "test_receipt")
        self.assertEqual(result.evidence[0].digest, hashlib.sha256(report).hexdigest())

    def test_pytest_junit_failures_and_skips_never_pass(self):
        failed = b'<testsuite><testcase name="test_bad"><failure message="assertion"/></testcase></testsuite>'
        skipped = b'<testsuite><testcase name="test_skip"><skipped/></testcase></testsuite>'
        profile = self.profile("pytest", "test_receipt")
        self.assertEqual(self.engine.verify(profile, failed, source="ci://failed").result.outcome, VerificationOutcome.FAIL)
        self.assertEqual(self.engine.verify(profile, skipped, source="ci://skipped").result.outcome, VerificationOutcome.INCONCLUSIVE)

    def test_pytest_junit_rejects_dtd_entities_and_empty_reports(self):
        profile = self.profile("pytest", "test_receipt")
        for report in (
            b'<!DOCTYPE testsuite [<!ENTITY x "expanded">]><testsuite><testcase name="x"/></testsuite>',
            b'<testsuite/>',
            b'<not-a-suite><testcase name="x"/></not-a-suite>',
        ):
            with self.subTest(report=report):
                result = self.engine.verify(profile, report, source="ci://invalid")
                self.assertNotEqual(result.result.outcome, VerificationOutcome.PASS)



    def test_http_contract_receipt_checks_https_status_and_body_schema(self):
        profile = self.profile("http_contract", "http_contract_receipt")
        schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
        receipt = b'{"method":"GET","url":"https://api.example.test/v1/health","status_code":200,"expected_status":200,"body":{"ok":true}}'
        passed = self.engine.verify(profile, receipt, source="capture://http/1", schema=schema)
        self.assertEqual(passed.result.outcome, VerificationOutcome.PASS)
        self.assertEqual(passed.evidence[0].evidence_type, "http_contract_receipt")
        mismatch = receipt.replace(b'"status_code":200', b'"status_code":503')
        failed = self.engine.verify(profile, mismatch, source="capture://http/2", schema=schema)
        self.assertEqual(failed.result.outcome, VerificationOutcome.FAIL)

    def test_http_contract_rejects_untrusted_urls_and_invalid_body(self):
        profile = self.profile("http_contract", "http_contract_receipt")
        schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
        for url, body in (
            ("http://api.example.test/health", {"ok": True}),
            ("https://user:secret@api.example.test/health", {"ok": True}),
            ("https://api.example.test/health#fragment", {"ok": True}),
            ("https://api.example.test/health", {"ok": "yes"}),
        ):
            receipt = json.dumps({
                "method": "GET", "url": url, "status_code": 200,
                "expected_status": 200, "body": body,
            }).encode()
            with self.subTest(url=url, body=body):
                result = self.engine.verify(profile, receipt, source="capture://http/invalid", schema=schema)
                self.assertEqual(result.result.outcome, VerificationOutcome.FAIL)


    def test_source_provenance_requires_exact_content_address(self):
        artifact = b"content-addressed artifact"
        digest = hashlib.sha256(artifact).hexdigest()
        profile = self.profile("source_provenance", "source_provenance")
        passed = self.engine.verify(profile, artifact, source=f"sha256:{digest}")
        failed = self.engine.verify(profile, artifact, source="https://example.test/artifact")
        self.assertEqual(passed.result.outcome, VerificationOutcome.PASS)
        self.assertEqual(passed.evidence[0].evidence_type, "source_provenance")
        self.assertEqual(failed.result.outcome, VerificationOutcome.FAIL)


if __name__ == "__main__":
    unittest.main()
