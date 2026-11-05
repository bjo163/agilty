from __future__ import annotations

"""Small deterministic verifier adapters. No dynamic imports or shell execution."""

import hashlib
import json
import time
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
                document = json.loads(artifact.decode("utf-8"))
                if not isinstance(schema, Mapping):
                    raise ValueError("a JSON schema object is required")
                self._validate_schema(document, schema)
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
            if "enum" in rule and value not in rule["enum"]:
                raise ValueError(f"{path} is not one of the allowed enum values")
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
                if not isinstance(required, list) or not isinstance(properties, Mapping):
                    raise ValueError(f"invalid object schema at {path}")
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

        if len(json.dumps(schema, ensure_ascii=False).encode("utf-8")) > cls.MAX_SCHEMA_BYTES:
            raise ValueError("JSON schema exceeds 65536 bytes")
        check(document, schema, "$", 0)
