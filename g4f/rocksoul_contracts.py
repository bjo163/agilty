from __future__ import annotations

"""Canonical, dependency-free work contracts for ROCKSOUL.

A WorkItem describes the intended outcome and the authority/budget under which
work may happen. It deliberately does not execute providers or certify output.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PERMISSION_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
_VERIFICATION_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class ContractValidationError(ValueError):
    """Raised when a WorkItem contract is malformed or unsafe."""


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    VERIFYING = "verifying"
    ACCEPTED = "accepted"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


TERMINAL_WORK_STATUSES = frozenset({
    WorkStatus.ACCEPTED,
    WorkStatus.REJECTED,
    WorkStatus.CANCELLED,
    WorkStatus.EXPIRED,
})

_ALLOWED_TRANSITIONS = {
    WorkStatus.PENDING: frozenset({WorkStatus.PLANNING, WorkStatus.BLOCKED, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
    WorkStatus.PLANNING: frozenset({WorkStatus.READY, WorkStatus.BLOCKED, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
    WorkStatus.READY: frozenset({WorkStatus.RUNNING, WorkStatus.BLOCKED, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
    WorkStatus.RUNNING: frozenset({WorkStatus.VERIFYING, WorkStatus.BLOCKED, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
    WorkStatus.VERIFYING: frozenset({
        WorkStatus.ACCEPTED, WorkStatus.UNVERIFIED, WorkStatus.REJECTED,
        WorkStatus.UNCERTAIN, WorkStatus.BLOCKED, WorkStatus.CANCELLED, WorkStatus.EXPIRED,
    }),
    WorkStatus.UNVERIFIED: frozenset({WorkStatus.VERIFYING, WorkStatus.REJECTED, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
    WorkStatus.UNCERTAIN: frozenset({WorkStatus.VERIFYING, WorkStatus.UNVERIFIED, WorkStatus.REJECTED, WorkStatus.BLOCKED, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
    WorkStatus.BLOCKED: frozenset({WorkStatus.PENDING, WorkStatus.CANCELLED, WorkStatus.EXPIRED}),
}


def _non_empty_string(value: Any, field_name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ContractValidationError(f"{field_name} must not exceed {maximum} characters")
    return normalized


def _aware_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field_name} must include a timezone")
    return parsed


def _strict_keys(value: Mapping[str, Any], allowed: set[str], field_name: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ContractValidationError(f"{field_name} contains unknown fields: {', '.join(sorted(unknown))}")


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    """Hard upper bounds for one WorkItem; absent cost/token caps stay explicit."""

    max_wall_time_seconds: float = 90.0
    max_attempts: int = 3
    max_repairs: int = 0
    max_tokens: int | None = None
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        wall_time = self.max_wall_time_seconds
        if isinstance(wall_time, bool) or not isinstance(wall_time, (int, float)) or not math.isfinite(wall_time) or wall_time <= 0 or wall_time > 86400:
            raise ContractValidationError("max_wall_time_seconds must be finite and in (0, 86400]")
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 100:
            raise ContractValidationError("max_attempts must be an integer in [1, 100]")
        if isinstance(self.max_repairs, bool) or not isinstance(self.max_repairs, int) or not 0 <= self.max_repairs <= 10:
            raise ContractValidationError("max_repairs must be an integer in [0, 10]")
        if self.max_tokens is not None and (
            isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 10_000_000
        ):
            raise ContractValidationError("max_tokens must be an integer in [1, 10000000]")
        if self.max_cost_usd is not None and (
            isinstance(self.max_cost_usd, bool) or not isinstance(self.max_cost_usd, (int, float))
            or not math.isfinite(self.max_cost_usd) or self.max_cost_usd < 0 or self.max_cost_usd > 1_000_000
        ):
            raise ContractValidationError("max_cost_usd must be finite and in [0, 1000000]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "max_attempts": self.max_attempts,
            "max_repairs": self.max_repairs,
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionBudget":
        if not isinstance(value, Mapping):
            raise ContractValidationError("budget must be an object")
        _strict_keys(value, {"max_wall_time_seconds", "max_attempts", "max_repairs", "max_tokens", "max_cost_usd"}, "budget")
        try:
            return cls(**dict(value))
        except TypeError as exc:
            raise ContractValidationError(f"budget is missing or has invalid fields: {exc}") from exc


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    """One independently checkable condition for accepting a work outcome."""

    criterion_id: str
    description: str
    verification_method: str
    required: bool = True

    def __post_init__(self) -> None:
        criterion_id = _non_empty_string(self.criterion_id, "criterion_id", 128)
        description = _non_empty_string(self.description, "criterion description", 2000)
        method = _non_empty_string(self.verification_method, "verification_method", 64).lower()
        if not _ID_PATTERN.fullmatch(criterion_id):
            raise ContractValidationError("criterion_id contains unsupported characters")
        if not _VERIFICATION_PATTERN.fullmatch(method):
            raise ContractValidationError("verification_method must be a stable lowercase identifier")
        if not isinstance(self.required, bool):
            raise ContractValidationError("criterion required must be a boolean")
        object.__setattr__(self, "criterion_id", criterion_id)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "verification_method", method)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "description": self.description,
            "verification_method": self.verification_method,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AcceptanceCriterion":
        if not isinstance(value, Mapping):
            raise ContractValidationError("each acceptance criterion must be an object")
        _strict_keys(value, {"criterion_id", "description", "verification_method", "required"}, "acceptance criterion")
        try:
            return cls(**dict(value))
        except TypeError as exc:
            raise ContractValidationError(f"acceptance criterion is missing or has invalid fields: {exc}") from exc


@dataclass(frozen=True, slots=True)
class WorkItem:
    """Versioned-by-schema intent and authority contract for one unit of work.

    Empty permissions mean deny all tool capabilities. High/critical risk always
    requires human approval. Acceptance is impossible without at least one
    required criterion and a later verification decision.
    """

    work_id: str
    goal: str
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    risk: RiskLevel = RiskLevel.MEDIUM
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    permissions: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    deadline_at: str | None = None
    human_approval_required: bool | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        work_id = _non_empty_string(self.work_id, "work_id", 128)
        goal = _non_empty_string(self.goal, "goal", 10000)
        if not _ID_PATTERN.fullmatch(work_id):
            raise ContractValidationError("work_id contains unsupported characters")
        if not isinstance(self.risk, RiskLevel):
            try:
                object.__setattr__(self, "risk", RiskLevel(self.risk))
            except (TypeError, ValueError) as exc:
                raise ContractValidationError("risk must be low, medium, high, or critical") from exc
        if not isinstance(self.budget, ExecutionBudget):
            raise ContractValidationError("budget must be an ExecutionBudget")
        if not isinstance(self.acceptance_criteria, tuple) or not self.acceptance_criteria:
            raise ContractValidationError("acceptance_criteria must be a non-empty tuple")
        if any(not isinstance(item, AcceptanceCriterion) for item in self.acceptance_criteria):
            raise ContractValidationError("acceptance_criteria must contain AcceptanceCriterion values")
        criterion_ids = [item.criterion_id for item in self.acceptance_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ContractValidationError("acceptance criterion IDs must be unique")
        if not any(item.required for item in self.acceptance_criteria):
            raise ContractValidationError("at least one acceptance criterion must be required")
        if not isinstance(self.permissions, tuple):
            raise ContractValidationError("permissions must be a tuple")
        normalized_permissions = tuple(_non_empty_string(item, "permission", 128).lower() for item in self.permissions)
        if any(not _PERMISSION_PATTERN.fullmatch(item) for item in normalized_permissions):
            raise ContractValidationError("permissions must be exact lowercase capability identifiers; wildcards are forbidden")
        if len(normalized_permissions) != len(set(normalized_permissions)):
            raise ContractValidationError("permissions must be unique")
        created = _aware_datetime(self.created_at, "created_at")
        deadline = _aware_datetime(self.deadline_at, "deadline_at") if self.deadline_at is not None else None
        if deadline is not None and deadline <= created:
            raise ContractValidationError("deadline_at must be later than created_at")
        if self.human_approval_required is None:
            approval = self.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            object.__setattr__(self, "human_approval_required", approval)
        elif not isinstance(self.human_approval_required, bool):
            raise ContractValidationError("human_approval_required must be a boolean")
        elif self.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} and not self.human_approval_required:
            raise ContractValidationError("high and critical risk work always requires human approval")
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int) or self.schema_version != 1:
            raise ContractValidationError("unsupported WorkItem schema_version")
        object.__setattr__(self, "work_id", work_id)
        object.__setattr__(self, "goal", goal)
        object.__setattr__(self, "permissions", normalized_permissions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "work_id": self.work_id,
            "goal": self.goal,
            "acceptance_criteria": [item.to_dict() for item in self.acceptance_criteria],
            "risk": self.risk.value,
            "budget": self.budget.to_dict(),
            "permissions": list(self.permissions),
            "created_at": self.created_at,
            "deadline_at": self.deadline_at,
            "human_approval_required": self.human_approval_required,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkItem":
        if not isinstance(value, Mapping):
            raise ContractValidationError("WorkItem must be an object")
        _strict_keys(value, {
            "schema_version", "work_id", "goal", "acceptance_criteria", "risk",
            "budget", "permissions", "created_at", "deadline_at", "human_approval_required",
        }, "WorkItem")
        criteria = value.get("acceptance_criteria")
        permissions = value.get("permissions", [])
        if not isinstance(criteria, list):
            raise ContractValidationError("acceptance_criteria must be an array")
        if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
            raise ContractValidationError("permissions must be an array of strings")
        budget = ExecutionBudget.from_dict(value.get("budget", {}))
        try:
            risk = RiskLevel(value.get("risk", RiskLevel.MEDIUM.value))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("risk must be low, medium, high, or critical") from exc
        try:
            return cls(
                work_id=value.get("work_id"),
                goal=value.get("goal"),
                acceptance_criteria=tuple(AcceptanceCriterion.from_dict(item) for item in criteria),
                risk=risk,
                budget=budget,
                permissions=tuple(permissions),
                created_at=value.get("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
                deadline_at=value.get("deadline_at"),
                human_approval_required=value.get("human_approval_required"),
                schema_version=value.get("schema_version", 1),
            )
        except TypeError as exc:
            raise ContractValidationError(f"WorkItem is missing or has invalid fields: {exc}") from exc

    @property
    def contract_digest(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_status_transition(current: WorkStatus | str, target: WorkStatus | str) -> WorkStatus:
    """Return the target status or reject an illegal lifecycle transition."""
    try:
        source_status = current if isinstance(current, WorkStatus) else WorkStatus(current)
        target_status = target if isinstance(target, WorkStatus) else WorkStatus(target)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("unknown WorkItem status") from exc
    if target_status not in _ALLOWED_TRANSITIONS.get(source_status, frozenset()):
        raise ContractValidationError(f"illegal WorkItem transition: {source_status.value} -> {target_status.value}")
    return target_status
