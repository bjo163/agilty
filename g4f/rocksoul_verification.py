from __future__ import annotations

"""Versioned, fail-closed verification contracts (not verifier implementations)."""

import hashlib
import json
import math
import re
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class VerificationProfileError(ValueError):
    """Invalid profile, evidence, or verifier resolution."""


_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_ADAPTERS = frozenset({"json_schema", "artifact_digest", "pytest", "http_contract", "source_provenance"})


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise VerificationProfileError(f"{name} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _strict(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    extra = set(value) - allowed
    if extra:
        raise VerificationProfileError(f"{name} contains unknown fields: {', '.join(sorted(extra))}")


class VerificationOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    evidence_type: str
    minimum_count: int = 1
    require_digest: bool = True
    require_source: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_type", _text(self.evidence_type, "evidence_type", 64).lower())
        if not _ID.fullmatch(self.evidence_type):
            raise VerificationProfileError("evidence_type must be a stable lowercase identifier")
        if isinstance(self.minimum_count, bool) or not isinstance(self.minimum_count, int) or not 1 <= self.minimum_count <= 100:
            raise VerificationProfileError("minimum_count must be an integer in [1, 100]")
        if not isinstance(self.require_digest, bool) or not isinstance(self.require_source, bool):
            raise VerificationProfileError("evidence requirement flags must be booleans")

    def to_dict(self) -> dict[str, Any]:
        return {"evidence_type": self.evidence_type, "minimum_count": self.minimum_count,
                "require_digest": self.require_digest, "require_source": self.require_source}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceRequirement":
        if not isinstance(value, Mapping):
            raise VerificationProfileError("evidence requirement must be an object")
        _strict(value, {"evidence_type", "minimum_count", "require_digest", "require_source"}, "evidence requirement")
        try:
            return cls(**dict(value))
        except TypeError as exc:
            raise VerificationProfileError(f"invalid evidence requirement: {exc}") from exc


@dataclass(frozen=True, slots=True)
class VerificationProfile:
    profile_id: str
    version: int
    adapter_id: str
    evidence_requirements: tuple[EvidenceRequirement, ...]
    severity: str = "error"
    independence_group: str = "deterministic"
    deterministic: bool = True
    side_effect_free: bool = True
    timeout_seconds: float = 10.0
    schema_version: int = 1

    def __post_init__(self) -> None:
        profile_id = _text(self.profile_id, "profile_id", 64).lower()
        adapter_id = _text(self.adapter_id, "adapter_id", 64).lower()
        severity = _text(self.severity, "severity", 16).lower()
        group = _text(self.independence_group, "independence_group", 64).lower()
        if not _ID.fullmatch(profile_id) or not _ID.fullmatch(adapter_id) or not _ID.fullmatch(group):
            raise VerificationProfileError("profile_id, adapter_id, and independence_group must be stable identifiers")
        if adapter_id not in _ALLOWED_ADAPTERS:
            raise VerificationProfileError("adapter_id is not in the built-in verifier adapter allowlist")
        if severity not in {"info", "warning", "error", "critical"}:
            raise VerificationProfileError("severity must be info, warning, error, or critical")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or not 1 <= self.version <= 1_000_000:
            raise VerificationProfileError("version must be an integer in [1, 1000000]")
        if not isinstance(self.evidence_requirements, tuple) or not self.evidence_requirements:
            raise VerificationProfileError("evidence_requirements must be a non-empty tuple")
        if any(not isinstance(item, EvidenceRequirement) for item in self.evidence_requirements):
            raise VerificationProfileError("evidence_requirements must contain EvidenceRequirement values")
        if len({item.evidence_type for item in self.evidence_requirements}) != len(self.evidence_requirements):
            raise VerificationProfileError("evidence requirement types must be unique")
        if not isinstance(self.deterministic, bool) or not isinstance(self.side_effect_free, bool):
            raise VerificationProfileError("deterministic and side_effect_free must be booleans")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not math.isfinite(self.timeout_seconds) or not 0.05 <= self.timeout_seconds <= 300:
            raise VerificationProfileError("timeout_seconds must be finite and in [0.05, 300]")
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise VerificationProfileError("unsupported VerificationProfile schema_version")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "adapter_id", adapter_id)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "independence_group", group)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "profile_id": self.profile_id, "version": self.version,
                "adapter_id": self.adapter_id, "evidence_requirements": [x.to_dict() for x in self.evidence_requirements],
                "severity": self.severity, "independence_group": self.independence_group,
                "deterministic": self.deterministic, "side_effect_free": self.side_effect_free,
                "timeout_seconds": self.timeout_seconds}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VerificationProfile":
        if not isinstance(value, Mapping):
            raise VerificationProfileError("profile must be an object")
        _strict(value, {"schema_version", "profile_id", "version", "adapter_id", "evidence_requirements",
                        "severity", "independence_group", "deterministic", "side_effect_free", "timeout_seconds"}, "profile")
        if value.get("schema_version") != 1 or isinstance(value.get("schema_version"), bool):
            raise VerificationProfileError("profile schema_version=1 is required")
        requirements = value.get("evidence_requirements")
        if not isinstance(requirements, list):
            raise VerificationProfileError("evidence_requirements must be an array")
        try:
            return cls(profile_id=value["profile_id"], version=value["version"], adapter_id=value["adapter_id"],
                       evidence_requirements=tuple(EvidenceRequirement.from_dict(x) for x in requirements),
                       severity=value.get("severity", "error"), independence_group=value.get("independence_group", "deterministic"),
                       deterministic=value.get("deterministic", True), side_effect_free=value.get("side_effect_free", True),
                       timeout_seconds=value.get("timeout_seconds", 10.0), schema_version=value["schema_version"])
        except (KeyError, TypeError) as exc:
            raise VerificationProfileError(f"profile is missing or has invalid fields: {exc}") from exc

    @property
    def digest(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    evidence_type: str
    source: str
    digest: str
    captured_at: str
    verifier_id: str
    verifier_version: str

    def __post_init__(self) -> None:
        for name, limit in (("evidence_id", 128), ("evidence_type", 64), ("source", 500),
                            ("captured_at", 64), ("verifier_id", 128), ("verifier_version", 64)):
            object.__setattr__(self, name, _text(getattr(self, name), name, limit))
        if not isinstance(self.digest, str) or not _DIGEST.fullmatch(self.digest):
            raise VerificationProfileError("evidence digest must be a lowercase SHA-256 hex digest")
        try:
            timestamp = datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise VerificationProfileError("captured_at must be a valid ISO-8601 timestamp") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise VerificationProfileError("captured_at must include a timezone")
        if not _ID.fullmatch(self.evidence_type.lower()):
            raise VerificationProfileError("evidence_type must be a stable identifier")


@dataclass(frozen=True, slots=True)
class VerificationResult:
    outcome: VerificationOutcome
    profile_id: str
    profile_version: int
    verifier_id: str
    verifier_version: str
    independence_group: str
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, VerificationOutcome):
            object.__setattr__(self, "outcome", VerificationOutcome(self.outcome))
        for name, value in (("profile_id", self.profile_id), ("verifier_id", self.verifier_id), ("verifier_version", self.verifier_version), ("independence_group", self.independence_group)):
            _text(value, name, 128)
        if isinstance(self.profile_version, bool) or not isinstance(self.profile_version, int) or self.profile_version < 1:
            raise VerificationProfileError("profile_version must be a positive integer")
        if not isinstance(self.findings, tuple):
            raise VerificationProfileError("findings must be a tuple")
        if self.outcome is VerificationOutcome.PASS and self.findings:
            raise VerificationProfileError("PASS results cannot contain unresolved findings")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 2000 for item in self.findings):
            raise VerificationProfileError("findings must be non-empty strings of at most 2000 characters")

    @property
    def satisfies_required_criterion(self) -> bool:
        return self.outcome is VerificationOutcome.PASS


class VerificationProfileRegistry:
    """In-memory immutable-version registry; adapter execution is deliberately separate."""

    def __init__(self, profiles: tuple[VerificationProfile, ...] = ()) -> None:
        self._profiles: dict[tuple[str, int], VerificationProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: VerificationProfile) -> None:
        if not isinstance(profile, VerificationProfile):
            raise VerificationProfileError("only validated VerificationProfile values may be registered")
        key = (profile.profile_id, profile.version)
        existing = self._profiles.get(key)
        if existing is not None and existing.digest != profile.digest:
            raise VerificationProfileError("profile versions are immutable and cannot be overwritten")
        self._profiles[key] = profile

    def resolve(self, profile_id: str, version: int) -> VerificationProfile:
        if isinstance(version, bool) or not isinstance(version, int):
            raise VerificationProfileError("profile version must be an integer")
        profile = self._profiles.get((str(profile_id).lower(), version))
        if profile is None:
            raise VerificationProfileError("unknown verification profile or version mismatch")
        return profile

    def validate_evidence(self, profile: VerificationProfile, evidence: tuple[EvidenceRecord, ...]) -> None:
        if not isinstance(evidence, tuple) or any(not isinstance(item, EvidenceRecord) for item in evidence):
            raise VerificationProfileError("evidence must be a tuple of validated EvidenceRecord values")
        if not evidence:
            raise VerificationProfileError("empty evidence cannot satisfy a verification profile")
        for requirement in profile.evidence_requirements:
            matching = [item for item in evidence if item.evidence_type == requirement.evidence_type]
            if len(matching) < requirement.minimum_count:
                raise VerificationProfileError(f"insufficient evidence for type: {requirement.evidence_type}")
            for item in matching:
                if requirement.require_digest and not item.digest:
                    raise VerificationProfileError("evidence digest is required")
                if requirement.require_source and not item.source:
                    raise VerificationProfileError("evidence source is required")

    def independence_groups(self) -> tuple[str, ...]:
        return tuple(sorted({profile.independence_group for profile in self._profiles.values()}))

    def list_profiles(self) -> tuple[VerificationProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))
