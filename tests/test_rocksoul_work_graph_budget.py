from __future__ import annotations

import unittest

from g4f.rocksoul_contracts import AcceptanceCriterion, ExecutionBudget, WorkItem
from g4f.rocksoul_work_graph import WorkGraph, WorkGraphNode
from g4f.rocksoul_work_graph_budget import (
    WorkGraphBudget,
    WorkGraphBudgetError,
    resolve_graph_budget_and_authority,
)


def item(work_id: str, *, budget=None, permissions=(), approval=False) -> WorkItem:
    return WorkItem(
        work_id=work_id,
        goal="Test work",
        acceptance_criteria=(AcceptanceCriterion("done", "Complete the task", "manual"),),
        budget=budget or ExecutionBudget(),
        permissions=tuple(permissions),
        human_approval_required=approval,
    )


class WorkGraphBudgetTests(unittest.TestCase):
    def graph(self, count=1):
        return WorkGraph("graph", tuple(WorkGraphNode(f"n{i}", f"w{i}") for i in range(count)))

    def budget(self, **overrides):
        values = {
            "max_wall_time_seconds": 600.0,
            "max_attempts": 20,
            "max_repairs": 10,
            "max_tokens": 100_000,
            "max_cost_usd": 100.0,
        }
        values.update(overrides)
        return WorkGraphBudget(**values)

    def test_intersects_child_budget_and_exact_permissions(self):
        graph = self.graph()
        child = item(
            "w0",
            budget=ExecutionBudget(
                max_wall_time_seconds=120,
                max_attempts=2,
                max_repairs=1,
                max_tokens=5000,
                max_cost_usd=4.5,
            ),
            permissions=("files.read", "network.fetch"),
            approval=True,
        )
        decision = resolve_graph_budget_and_authority(
            graph, self.budget(), ("files.read", "tools.invoke"), {"w0": child}
        )
        node = decision["nodes"][0]
        self.assertEqual(node["budget"]["max_wall_time_seconds"], 120)
        self.assertEqual(node["budget"]["max_attempts"], 2)
        self.assertEqual(node["budget"]["max_repairs"], 1)
        self.assertEqual(node["budget"]["max_tokens"], 5000)
        self.assertEqual(node["budget"]["max_cost_usd"], 4.5)
        self.assertEqual(node["permissions"], ["files.read"])
        self.assertTrue(node["human_approval_required"])
        self.assertEqual(len(decision["decision_digest"]), 64)

    def test_graph_caps_bound_unlimited_child_token_and_cost(self):
        child = item("w0", budget=ExecutionBudget(max_tokens=None, max_cost_usd=None))
        decision = resolve_graph_budget_and_authority(
            self.graph(), self.budget(max_tokens=900, max_cost_usd=2.0), (), {"w0": child}
        )
        self.assertEqual(decision["nodes"][0]["budget"]["max_tokens"], 900)
        self.assertEqual(decision["nodes"][0]["budget"]["max_cost_usd"], 2.0)
        self.assertEqual(decision["nodes"][0]["permissions"], [])

    def test_aggregate_budget_rejects_sum_above_graph_ceiling(self):
        graph = self.graph(2)
        children = {
            "w0": item("w0", budget=ExecutionBudget(max_attempts=2)),
            "w1": item("w1", budget=ExecutionBudget(max_attempts=2)),
        }
        with self.assertRaisesRegex(WorkGraphBudgetError, "aggregate max_attempts"):
            resolve_graph_budget_and_authority(
                graph, self.budget(max_attempts=3), (), children
            )

    def test_graph_permissions_cannot_expand_child_authority(self):
        child = item("w0", permissions=("files.read",))
        decision = resolve_graph_budget_and_authority(
            self.graph(), self.budget(), ("files.read", "shell.execute"), {"w0": child}
        )
        self.assertEqual(decision["nodes"][0]["permissions"], ["files.read"])

    def test_missing_child_contract_fails_closed(self):
        with self.assertRaisesRegex(WorkGraphBudgetError, "missing"):
            resolve_graph_budget_and_authority(self.graph(), self.budget(), (), {})

    def test_rejects_nonfinite_boolean_and_invalid_graph_caps(self):
        for values in (
            {"max_wall_time_seconds": float("inf")},
            {"max_wall_time_seconds": True},
            {"max_attempts": True},
            {"max_attempts": 0},
            {"max_repairs": -1},
            {"max_tokens": 0},
            {"max_cost_usd": float("nan")},
        ):
            with self.subTest(values=values), self.assertRaises(WorkGraphBudgetError):
                self.budget(**values)

    def test_from_dict_requires_every_finite_graph_cap(self):
        with self.assertRaisesRegex(WorkGraphBudgetError, "missing required finite caps"):
            WorkGraphBudget.from_dict({"max_wall_time_seconds": 60})


if __name__ == "__main__":
    unittest.main()
