from __future__ import annotations

"""Strict aggregate budgets and deny-by-default authority composition for WorkGraphs."""

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from .rocksoul_contracts import ExecutionBudget, WorkItem, _PERMISSION_PATTERN
from .rocksoul_work_graph import WorkGraph, WorkGraphValidationError


class WorkGraphBudgetError(ValueError):
    """A graph budget or authority composition is unsafe or unrepresentable."""


@dataclass(frozen=True, slots=True)
class WorkGraphBudget:
    """Finite aggregate ceilings for the complete graph, not per-node grants."""

    max_wall_time_seconds: float
    max_attempts: int
    max_repairs: int
    max_tokens: int
    max_cost_usd: float
    schema_version: int = 1

    def __post_init__(self) -> None:
        wall = self.max_wall_time_seconds
        if isinstance(wall, bool) or not isinstance(wall, (int, float)) or not math.isfinite(wall) or not 0 < wall <= 604800:
            raise WorkGraphBudgetError("max_wall_time_seconds must be finite and in (0, 604800]")
        for name, value, low, high in (
            ("max_attempts", self.max_attempts, 1, 10000),
            ("max_repairs", self.max_repairs, 0, 1000),
            ("max_tokens", self.max_tokens, 1, 2**63 - 1),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise WorkGraphBudgetError(f"{name} must be an integer in [{low}, {high}]")
        cost = self.max_cost_usd
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or not 0 <= cost <= 1_000_000:
            raise WorkGraphBudgetError("max_cost_usd must be finite and in [0, 1000000]")
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int) or self.schema_version != 1:
            raise WorkGraphBudgetError("unsupported WorkGraph budget schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "max_attempts": self.max_attempts,
            "max_repairs": self.max_repairs,
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkGraphBudget":
        if not isinstance(value, Mapping):
            raise WorkGraphBudgetError("graph budget must be an object")
        allowed = {"schema_version", "max_wall_time_seconds", "max_attempts", "max_repairs", "max_tokens", "max_cost_usd"}
        unknown = set(value) - allowed
        if unknown:
            raise WorkGraphBudgetError(f"graph budget contains unknown fields: {', '.join(sorted(unknown))}")
        required = allowed - {"schema_version"}
        missing = required - set(value)
        if missing:
            raise WorkGraphBudgetError(f"graph budget is missing required finite caps: {', '.join(sorted(missing))}")
        try:
            return cls(**dict(value))
        except TypeError as exc:
            raise WorkGraphBudgetError(f"invalid graph budget fields: {exc}") from exc


def _intersect_budget(child: ExecutionBudget, graph: WorkGraphBudget) -> dict[str, Any]:
    """Return child ceilings narrowed by the aggregate graph ceilings."""
    return {
        "max_wall_time_seconds": min(float(child.max_wall_time_seconds), float(graph.max_wall_time_seconds)),
        "max_attempts": min(child.max_attempts, graph.max_attempts),
        "max_repairs": min(child.max_repairs, graph.max_repairs),
        "max_tokens": min(child.max_tokens, graph.max_tokens) if child.max_tokens is not None else graph.max_tokens,
        "max_cost_usd": min(float(child.max_cost_usd), float(graph.max_cost_usd)) if child.max_cost_usd is not None else graph.max_cost_usd,
    }


def resolve_graph_budget_and_authority(
    graph: WorkGraph,
    graph_budget: WorkGraphBudget,
    graph_permissions: tuple[str, ...],
    work_items: Mapping[str, WorkItem],
) -> dict[str, Any]:
    """Resolve effective per-node limits and exact permission intersections.

    Aggregate resource ceilings are checked conservatively by summing each
    node's effective maximum. This deliberately rejects plans whose aggregate
    upper bound cannot be proven to fit the graph envelope.
    """
    if not isinstance(graph, WorkGraph) or not isinstance(graph_budget, WorkGraphBudget):
        raise WorkGraphBudgetError("validated WorkGraph and WorkGraphBudget are required")
    if not isinstance(graph_permissions, tuple) or len(graph_permissions) > 100:
        raise WorkGraphBudgetError("graph_permissions must be a tuple of at most 100 exact capabilities")
    if any(not isinstance(p, str) or not _PERMISSION_PATTERN.fullmatch(p) for p in graph_permissions):
        raise WorkGraphBudgetError("graph permissions must be exact lowercase capability identifiers")
    if len(set(graph_permissions)) != len(graph_permissions):
        raise WorkGraphBudgetError("graph permissions must be unique")
    if not isinstance(work_items, Mapping):
        raise WorkGraphBudgetError("work_items must map work IDs to validated WorkItems")
    graph_caps = set(graph_permissions)
    nodes = []
    totals = {"max_wall_time_seconds": 0.0, "max_attempts": 0, "max_repairs": 0, "max_tokens": 0, "max_cost_usd": 0.0}
    for node in sorted(graph.nodes, key=lambda item: item.node_id):
        item = work_items.get(node.work_id)
        if not isinstance(item, WorkItem) or item.work_id != node.work_id:
            raise WorkGraphBudgetError(f"validated WorkItem contract is missing for node {node.node_id}")
        effective = _intersect_budget(item.budget, graph_budget)
        for key in totals:
            totals[key] += effective[key]
        permissions = sorted(set(item.permissions) & graph_caps)
        nodes.append({
            "node_id": node.node_id,
            "work_id": node.work_id,
            "budget": effective,
            "permissions": permissions,
            "human_approval_required": bool(item.human_approval_required),
            "child_contract_digest": item.contract_digest,
        })
    for key, maximum in graph_budget.to_dict().items():
        if key == "schema_version":
            continue
        total_key = key
        if totals[total_key] > maximum:
            raise WorkGraphBudgetError(f"aggregate {key} exceeds graph budget: {totals[total_key]} > {maximum}")
    decision = {
        "schema_version": 1,
        "graph_id": graph.graph_id,
        "graph_digest": graph.digest,
        "graph_budget": graph_budget.to_dict(),
        "graph_permissions": sorted(graph_caps),
        "nodes": nodes,
        "aggregate_upper_bound": totals,
        "approval_policy": "child_work_item_approval_required_independently",
    }
    canonical = json.dumps(decision, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    decision["decision_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return decision
