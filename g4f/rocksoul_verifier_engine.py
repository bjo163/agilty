from __future__ import annotations

"""Small deterministic verifier adapters. No dynamic imports or shell execution."""

import hashlib
import json
import math
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .rocksoul_verification import (
    EvidenceRecord, VerificationOutcome, VerificationProfile, VerificationProfileError, VerificationResult,
)


@dataclass(frozen=True, slots=True)
class VerificationExecution:
    result: VerificationResult
    evidence: tuple[EvidenceRecord, ...]
    artifact_digest: str
    duration_ms: float


class VerificationEngine:
    """Execute only explicitly implemented built-in, side-effect-free adapters."""

    VERSION = "1.0.0"
    MAX_ARTIFACT_BYTES = 1_000_000
    MAX_SCHEMA_BYTES = 65_536
    MAX_JSON_DEPTH = 32
    MAX_SCHEMA_NODES = 2000

    def verify(
        self,
        profile: VerificationProfile,
        artifact: bytes,
        *,
        source: str,
        expected_sha256: str | None = None,
        schema: Mapping[str, Any] | None = None,
    ) -> VerificationExecution:
        if not isinstance(profile, VerificationProfile):
            raise VerificationProfileError("verify requires a registered, validated profile")
        if not isinstance(artifact, bytes) or not artifact or len(artifact) > self.MAX_ARTIFACT_BYTES:
            raise VerificationProfileError("artifact must contain 1 to 1000000 bytes")
        if not isinstance(source, str) or not source.strip() or len(source) > 500:
            raise VerificationProfileError("artifact source must be a non-empty provenance reference")
        if not profile.deterministic or not profile.side_effect_free:
            raise VerificationProfileError("this engine executes only deterministic, side-effect-free profiles")

        started = time.monotonic()
        digest = hashlib.sha256(artifact).hexdigest()
        findings: list[str] = []
        evidence_type: str | None = None
        outcome = VerificationOutcome.ERROR

        if profile.adapter_id == "artifact_digest":
            evidence_type = "artifact_digest"
            if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
                findings.append("expected_sha256 is required for artifact_digest verification")
            elif expected_sha256.lower() != digest:
                findings.append("artifact SHA-256 does not match the expected digest")
                outcome = VerificationOutcome.FAIL
            else:
                outcome = VerificationOutcome.PASS
        elif profile.adapter_id == "json_schema":
            evidence_type = "json_validation"
            try:
                def reject_constant(token: str):
                    raise ValueError(f"non-finite JSON number is forbidden: {token}")
                document = json.loads(artifact.decode("utf-8"), parse_constant=reject_constant)
                if not isinstance(schema, Mapping):
                    raise ValueError("a JSON schema object is required")
                self._validate_schema(document, schema)
                outcome = VerificationOutcome.PASS
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
                findings.append(str(exc)[:2000])
                outcome = VerificationOutcome.FAIL
        elif profile.adapter_id == "pytest":
            evidence_type = "test_receipt"
            try:
                if b"<!DOCTYPE" in artifact.upper() or b"<!ENTITY" in artifact.upper():
                    raise ValueError("JUnit XML DTD and entity declarations are forbidden")
                root = ET.fromstring(artifact)
                if root.tag not in {"testsuite", "testsuites"}:
                    raise ValueError("pytest adapter requires a JUnit testsuite/testsuites document")
                cases = root.findall(".//testcase")
                if not cases:
                    raise ValueError("JUnit report contains no test cases")
                failures = sum(1 for case in cases if case.find("failure") is not None)
                errors = sum(1 for case in cases if case.find("error") is not None)
                skipped = sum(1 for case in cases if case.find("skipped") is not None)
                unnamed = sum(1 for case in cases if not str(case.attrib.get("name", "")).strip())
                if unnamed:
                    raise ValueError("JUnit report contains unnamed test cases")
                findings.append(f"tests={len(cases)} failures={failures} errors={errors} skipped={skipped}")
                if failures or errors:
                    outcome = VerificationOutcome.FAIL
                elif skipped:
                    outcome = VerificationOutcome.INCONCLUSIVE
                else:
                    outcome = VerificationOutcome.PASS
            except (ET.ParseError, ValueError, RecursionError) as exc:
                findings.append(str(exc)[:2000])
                outcome = VerificationOutcome.FAIL
        elif profile.adapter_id == "http_contract":
            evidence_type = "http_contract_receipt"
            try:
                receipt = json.loads(artifact.decode("utf-8"))
                if not isinstance(receipt, dict) or set(receipt) != {"method", "url", "status_code", "expected_status", "body"}:
                    raise ValueError("HTTP receipt must contain exactly method, url, status_code, expected_status, and body")
                method = receipt["method"]
                if not isinstance(method, str) or method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
                    raise ValueError("HTTP receipt method is invalid")
                url = receipt["url"]
                if not isinstance(url, str) or len(url) > 2048:
                    raise ValueError("HTTP receipt URL is invalid")
                parsed_url = urlsplit(url)
                if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password or parsed_url.fragment:
                    raise ValueError("HTTP receipt URL must be an absolute HTTPS URL without credentials or fragment")
                status_code = receipt["status_code"]
                expected_status = receipt["expected_status"]
                if any(isinstance(value, bool) or not isinstance(value, int) or not 100 <= value <= 599 for value in (status_code, expected_status)):
                    raise ValueError("HTTP receipt status codes must be integers in [100, 599]")
                if not isinstance(schema, Mapping):
                    raise ValueError("a response-body JSON schema is required for HTTP contract verification")
                self._validate_schema(receipt["body"], schema)
                if status_code != expected_status:
                    findings.append(f"HTTP status {status_code} does not match expected status {expected_status}")
                    outcome = VerificationOutcome.FAIL
                else:
                    outcome = VerificationOutcome.PASS
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
                findings.append(str(exc)[:2000])
                outcome = VerificationOutcome.FAIL
        else:
            findings.append(f"no executable built-in adapter is registered for {profile.adapter_id}")
            outcome = VerificationOutcome.ERROR

        duration_ms = (time.monotonic() - started) * 1000.0
        if duration_ms > profile.timeout_seconds * 1000.0:
            outcome = VerificationOutcome.ERROR
            findings.append("verifier exceeded its declared timeout")
        if evidence_type is not None:
            evidence = (EvidenceRecord(
                evidence_id=hashlib.sha256(f"{profile.profile_id}:{profile.version}:{digest}:{source}".encode()).hexdigest()[:32],
                evidence_type=evidence_type,
                source=source,
                digest=digest,
                captured_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                verifier_id=f"rocksoul.{profile.adapter_id}",
                verifier_version=self.VERSION,
            ),)
        else:
            evidence = ()
        result = VerificationResult(
            outcome=outcome,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            verifier_id=f"rocksoul.{profile.adapter_id}",
            verifier_version=self.VERSION,
            independence_group=profile.independence_group,
            findings=tuple(findings),
        )
        return VerificationExecution(result, evidence, digest, duration_ms)

    @classmethod
    def _validate_schema(cls, document: Any, schema: Mapping[str, Any]) -> None:
        allowed = {
            "type", "enum", "required", "properties", "additionalProperties", "items",
            "minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum",
        }
        nodes = 0

        def check(value: Any, rule: Mapping[str, Any], path: str, depth: int) -> None:
            nonlocal nodes
            nodes += 1
            if nodes > cls.MAX_SCHEMA_NODES or depth > cls.MAX_JSON_DEPTH:
                raise ValueError("JSON schema complexity limit exceeded")
            unknown = set(rule) - allowed
            if unknown:
                raise ValueError(f"unsupported JSON schema keywords at {path}: {', '.join(sorted(unknown))}")
            if "enum" in rule:
                allowed_values = rule["enum"]
                if not isinstance(allowed_values, list) or not 1 <= len(allowed_values) <= 100:
                    raise ValueError(f"invalid enum constraint at {path}")
                if value not in allowed_values:
                    raise ValueError(f"{path} is not one of the allowed enum values")
            for key in ("minLength", "maxLength", "minItems", "maxItems"):
                if key in rule and (isinstance(rule[key], bool) or not isinstance(rule[key], int) or not 0 <= rule[key] <= 1_000_000):
                    raise ValueError(f"{key} must be a bounded non-negative integer at {path}")
            for key in ("minimum", "maximum"):
                if key in rule and (isinstance(rule[key], bool) or not isinstance(rule[key], (int, float)) or not math.isfinite(rule[key])):
                    raise ValueError(f"{key} must be a finite number at {path}")
            if "minLength" in rule and "maxLength" in rule and rule["minLength"] > rule["maxLength"]:
                raise ValueError(f"minLength exceeds maxLength at {path}")
            if "minItems" in rule and "maxItems" in rule and rule["minItems"] > rule["maxItems"]:
                raise ValueError(f"minItems exceeds maxItems at {path}")
            if "minimum" in rule and "maximum" in rule and rule["minimum"] > rule["maximum"]:
                raise ValueError(f"minimum exceeds maximum at {path}")
            expected = rule.get("type")
            types = {
                "object": dict, "array": list, "string": str, "integer": int,
                "number": (int, float), "boolean": bool, "null": type(None),
            }
            if expected is not None:
                if expected not in types:
                    raise ValueError(f"unsupported JSON schema type at {path}")
                valid = isinstance(value, types[expected])
                if expected in {"integer", "number"} and isinstance(value, bool):
                    valid = False
                if not valid:
                    raise ValueError(f"{path} must be {expected}")
            if isinstance(value, dict):
                required = rule.get("required", [])
                properties = rule.get("properties", {})
                if not isinstance(required, list) or len(required) > 100 or any(not isinstance(key, str) for key in required):
                    raise ValueError(f"invalid required constraint at {path}")
                if not isinstance(properties, Mapping) or len(properties) > 100:
                    raise ValueError(f"invalid properties constraint at {path}")
                if "additionalProperties" in rule and not isinstance(rule["additionalProperties"], bool):
                    raise ValueError(f"additionalProperties must be a boolean at {path}")
                missing = [key for key in required if key not in value]
                if missing:
                    raise ValueError(f"{path} is missing required properties: {', '.join(map(str, missing))}")
                if rule.get("additionalProperties", True) is False:
                    extras = set(value) - set(properties)
                    if extras:
                        raise ValueError(f"{path} contains additional properties: {', '.join(sorted(extras))}")
                for key, child_schema in properties.items():
                    if key in value:
                        if not isinstance(child_schema, Mapping):
                            raise ValueError(f"invalid property schema for {key}")
                        check(value[key], child_schema, f"{path}.{key}", depth + 1)
            if isinstance(value, list) and "items" in rule:
                child_schema = rule["items"]
                if not isinstance(child_schema, Mapping):
                    raise ValueError(f"invalid items schema at {path}")
                for index, item in enumerate(value):
                    check(item, child_schema, f"{path}[{index}]", depth + 1)
            if isinstance(value, str):
                if "minLength" in rule and len(value) < rule["minLength"]:
                    raise ValueError(f"{path} is shorter than minLength")
                if "maxLength" in rule and len(value) > rule["maxLength"]:
                    raise ValueError(f"{path} is longer than maxLength")
            if isinstance(value, list):
                if "minItems" in rule and len(value) < rule["minItems"]:
                    raise ValueError(f"{path} has fewer than minItems")
                if "maxItems" in rule and len(value) > rule["maxItems"]:
                    raise ValueError(f"{path} has more than maxItems")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if "minimum" in rule and value < rule["minimum"]:
                    raise ValueError(f"{path} is below minimum")
                if "maximum" in rule and value > rule["maximum"]:
                    raise ValueError(f"{path} is above maximum")

        if len(json.dumps(schema, ensure_ascii=False, allow_nan=False).encode("utf-8")) > cls.MAX_SCHEMA_BYTES:
            raise ValueError("JSON schema exceeds 65536 bytes")
        check(document, schema, "$", 0)
