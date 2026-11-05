from __future__ import annotations

"""Deterministic, bounded DAG contracts for composing ROCKSOUL WorkItems.

This module validates graph structure only. It does not schedule, execute, mutate
WorkItems, or imply that a dependency's output is trustworthy.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class WorkGraphValidationError(ValueError):
    """Raised when a WorkGraph is malformed, cyclic, or exceeds its limits."""


@dataclass(frozen=True, slots=True)
class WorkGraphNode:
    node_id: str
    work_id: str
    depends_on: tuple[str, ...] = ()
    required: bool = True

    def __post_init__(self) -> None:
        for name, value in (("node_id", self.node_id), ("work_id", self.work_id)):
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise WorkGraphValidationError(f"{name} must be a stable identifier")
        if not isinstance(self.depends_on, tuple):
            raise WorkGraphValidationError("depends_on must be a tuple")
        if len(self.depends_on) > 64:
            raise WorkGraphValidationError("a node cannot have more than 64 dependencies")
        if any(not isinstance(item, str) or not _ID.fullmatch(item) for item in self.depends_on):
            raise WorkGraphValidationError("dependency IDs must be stable identifiers")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise WorkGraphValidationError("dependency IDs must be unique")
        if self.node_id in self.depends_on:
            raise WorkGraphValidationError("a node cannot depend on itself")
        if not isinstance(self.required, bool):
            raise WorkGraphValidationError("required must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "work_id": self.work_id,
            "depends_on": sorted(self.depends_on),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkGraphNode":
        if not isinstance(value, Mapping):
            raise WorkGraphValidationError("each graph node must be an object")
        allowed = {"node_id", "work_id", "depends_on", "required"}
        unknown = set(value) - allowed
        if unknown:
            raise WorkGraphValidationError(f"graph node contains unknown fields: {', '.join(sorted(unknown))}")
        dependencies = value.get("depends_on", [])
        if not isinstance(dependencies, list):
            raise WorkGraphValidationError("depends_on must be an array")
        try:
            return cls(
                node_id=value["node_id"],
                work_id=value["work_id"],
                depends_on=tuple(dependencies),
                required=value.get("required", True),
            )
        except KeyError as exc:
            raise WorkGraphValidationError(f"graph node is missing {exc.args[0]}") from exc


@dataclass(frozen=True, slots=True)
class WorkGraph:
    graph_id: str
    nodes: tuple[WorkGraphNode, ...]
    schema_version: int = 1

    MAX_NODES = 256
    MAX_EDGES = 2048
    MAX_DEPTH = 64

    def __post_init__(self) -> None:
        if not isinstance(self.graph_id, str) or not _ID.fullmatch(self.graph_id):
            raise WorkGraphValidationError("graph_id must be a stable identifier")
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int) or self.schema_version != 1:
            raise WorkGraphValidationError("unsupported WorkGraph schema_version")
        if not isinstance(self.nodes, tuple) or not 1 <= len(self.nodes) <= self.MAX_NODES:
            raise WorkGraphValidationError(f"nodes must contain between 1 and {self.MAX_NODES} entries")
        if any(not isinstance(node, WorkGraphNode) for node in self.nodes):
            raise WorkGraphValidationError("nodes must contain WorkGraphNode values")
        node_ids = [node.node_id for node in self.nodes]
        work_ids = [node.work_id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise WorkGraphValidationError("node IDs must be unique")
        if len(set(work_ids)) != len(work_ids):
            raise WorkGraphValidationError("a WorkItem may appear only once in a graph")
        edge_count = sum(len(node.depends_on) for node in self.nodes)
        if edge_count > self.MAX_EDGES:
            raise WorkGraphValidationError(f"graph cannot contain more than {self.MAX_EDGES} dependency edges")
        known = set(node_ids)
        for node in self.nodes:
            missing = set(node.depends_on) - known
            if missing:
                raise WorkGraphValidationError(
                    f"node {node.node_id} references unknown dependencies: {', '.join(sorted(missing))}"
                )
        layers = self.topological_layers()
        if len(layers) > self.MAX_DEPTH:
            raise WorkGraphValidationError(f"graph depth cannot exceed {self.MAX_DEPTH}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "graph_id": self.graph_id,
            "nodes": [node.to_dict() for node in sorted(self.nodes, key=lambda item: item.node_id)],
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkGraph":
        if not isinstance(value, Mapping):
            raise WorkGraphValidationError("WorkGraph must be an object")
        allowed = {"schema_version", "graph_id", "nodes"}
        unknown = set(value) - allowed
        if unknown:
            raise WorkGraphValidationError(f"WorkGraph contains unknown fields: {', '.join(sorted(unknown))}")
        nodes = value.get("nodes")
        if not isinstance(nodes, list):
            raise WorkGraphValidationError("nodes must be an array")
        try:
            return cls(
                graph_id=value["graph_id"],
                nodes=tuple(WorkGraphNode.from_dict(item) for item in nodes),
                schema_version=value.get("schema_version", 1),
            )
        except KeyError as exc:
            raise WorkGraphValidationError(f"WorkGraph is missing {exc.args[0]}") from exc

    def topological_layers(self) -> tuple[tuple[str, ...], ...]:
        """Return deterministic parallelizable layers; reject cycles."""
        remaining = {node.node_id: set(node.depends_on) for node in self.nodes}
        layers: list[tuple[str, ...]] = []
        resolved: set[str] = set()
        while remaining:
            ready = tuple(sorted(node_id for node_id, deps in remaining.items() if deps <= resolved))
            if not ready:
                raise WorkGraphValidationError("dependency cycle detected")
            layers.append(ready)
            resolved.update(ready)
            for node_id in ready:
                remaining.pop(node_id)
        return tuple(layers)

    def ready_nodes(self, completed: Iterable[str] = ()) -> tuple[str, ...]:
        """Return nodes whose dependencies are complete, in stable ID order."""
        if isinstance(completed, (str, bytes)):
            raise WorkGraphValidationError("completed must be an iterable of node IDs, not a string")
        try:
            completed_values = tuple(completed)
        except TypeError as exc:
            raise WorkGraphValidationError("completed must be an iterable of node IDs") from exc
        if any(not isinstance(item, str) or not _ID.fullmatch(item) for item in completed_values):
            raise WorkGraphValidationError("completed node IDs must be stable identifiers")
        completed_ids = set(completed_values)
        known = {node.node_id for node in self.nodes}
        unknown = completed_ids - known
        if unknown:
            raise WorkGraphValidationError(f"unknown completed node IDs: {', '.join(sorted(unknown))}")
        return tuple(sorted(
            node.node_id for node in self.nodes
            if node.node_id not in completed_ids and set(node.depends_on) <= completed_ids
        ))

    def descendants(self, node_id: str) -> tuple[str, ...]:
        """Return all transitive dependents in deterministic topological order."""
        known = {node.node_id for node in self.nodes}
        if node_id not in known:
            raise WorkGraphValidationError("unknown node_id")
        reverse: dict[str, set[str]] = {key: set() for key in known}
        for node in self.nodes:
            for dependency in node.depends_on:
                reverse[dependency].add(node.node_id)
        found: set[str] = set()
        frontier = [node_id]
        while frontier:
            current = frontier.pop()
            for child in reverse[current] - found:
                found.add(child)
                frontier.append(child)
        order = [item for layer in self.topological_layers() for item in layer]
        return tuple(item for item in order if item in found)
