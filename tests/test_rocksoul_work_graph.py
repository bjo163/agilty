from __future__ import annotations

import unittest

from g4f.rocksoul_work_graph import (
    WorkGraph,
    WorkGraphNode,
    WorkGraphValidationError,
)


class WorkGraphTests(unittest.TestCase):
    def graph(self):
        return WorkGraph(
            graph_id="release-pipeline",
            nodes=(
                WorkGraphNode("verify", "work-verify", ("build",)),
                WorkGraphNode("publish", "work-publish", ("verify", "docs")),
                WorkGraphNode("build", "work-build"),
                WorkGraphNode("docs", "work-docs", ("build",)),
            ),
        )

    def test_topological_layers_are_deterministic(self):
        self.assertEqual(
            self.graph().topological_layers(),
            (("build",), ("docs", "verify"), ("publish",)),
        )

    def test_ready_nodes_require_all_dependencies(self):
        graph = self.graph()
        self.assertEqual(graph.ready_nodes(), ("build",))
        self.assertEqual(graph.ready_nodes(("build",)), ("docs", "verify"))
        self.assertEqual(graph.ready_nodes(("build", "docs", "verify")), ("publish",))

    def test_descendants_are_transitive_and_topologically_ordered(self):
        self.assertEqual(self.graph().descendants("build"), ("docs", "verify", "publish"))
        self.assertEqual(self.graph().descendants("verify"), ("publish",))

    def test_digest_is_independent_of_input_node_order(self):
        first = self.graph()
        second = WorkGraph(first.graph_id, tuple(reversed(first.nodes)))
        self.assertEqual(first.digest, second.digest)

    def test_round_trip_is_canonical(self):
        graph = self.graph()
        restored = WorkGraph.from_dict(graph.to_dict())
        self.assertEqual(restored.to_dict(), graph.to_dict())
        self.assertEqual(restored.digest, graph.digest)

    def test_digest_normalizes_dependency_order(self):
        first = WorkGraph("g", (
            WorkGraphNode("a", "wa"),
            WorkGraphNode("b", "wb", ("a",)),
            WorkGraphNode("c", "wc", ("a", "b")),
        ))
        second = WorkGraph("g", (
            WorkGraphNode("c", "wc", ("b", "a")),
            WorkGraphNode("b", "wb", ("a",)),
            WorkGraphNode("a", "wa"),
        ))
        self.assertEqual(first.digest, second.digest)

    def test_rejects_non_integer_schema_version_and_string_completed(self):
        with self.assertRaises(WorkGraphValidationError):
            WorkGraph.from_dict({"schema_version": 1.0, "graph_id": "g", "nodes": [{"node_id": "a", "work_id": "wa"}]})
        with self.assertRaises(WorkGraphValidationError):
            self.graph().ready_nodes("build")

    def test_rejects_duplicate_node_and_work_ids(self):
        with self.assertRaises(WorkGraphValidationError):
            WorkGraph("g", (WorkGraphNode("a", "w1"), WorkGraphNode("a", "w2")))
        with self.assertRaises(WorkGraphValidationError):
            WorkGraph("g", (WorkGraphNode("a", "w1"), WorkGraphNode("b", "w1")))

    def test_rejects_unknown_dependency_and_self_dependency(self):
        with self.assertRaises(WorkGraphValidationError):
            WorkGraph("g", (WorkGraphNode("a", "w1", ("missing",)),))
        with self.assertRaises(WorkGraphValidationError):
            WorkGraphNode("a", "w1", ("a",))

    def test_rejects_cycles(self):
        with self.assertRaisesRegex(WorkGraphValidationError, "cycle"):
            WorkGraph("g", (
                WorkGraphNode("a", "w1", ("b",)),
                WorkGraphNode("b", "w2", ("a",)),
            ))

    def test_rejects_excessive_depth(self):
        nodes = [WorkGraphNode("n0", "w0")]
        nodes.extend(WorkGraphNode(f"n{i}", f"w{i}", (f"n{i-1}",)) for i in range(1, 65))
        with self.assertRaisesRegex(WorkGraphValidationError, "depth"):
            WorkGraph("deep", tuple(nodes))

    def test_rejects_unknown_completed_nodes(self):
        with self.assertRaisesRegex(WorkGraphValidationError, "unknown completed"):
            self.graph().ready_nodes(("not-in-graph",))

    def test_rejects_unknown_fields_and_bad_node_shapes(self):
        with self.assertRaises(WorkGraphValidationError):
            WorkGraph.from_dict({"graph_id": "g", "nodes": [], "admin": True})
        with self.assertRaises(WorkGraphValidationError):
            WorkGraph.from_dict({"graph_id": "g", "nodes": [{"node_id": "a", "work_id": "w", "depends_on": "b"}]})

    def test_rejects_oversized_graph(self):
        nodes = tuple(WorkGraphNode(f"n{i}", f"w{i}") for i in range(257))
        with self.assertRaisesRegex(WorkGraphValidationError, "between 1 and 256"):
            WorkGraph("large", nodes)


if __name__ == "__main__":
    unittest.main()
