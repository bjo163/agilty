from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from g4f.rocksoul_work_graph_cli import main


class WorkGraphCliTests(unittest.TestCase):
    def test_create_list_verify_and_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_file = root / "graph.json"
            graph_file.write_text(json.dumps({"graph_id": "cli-pipeline", "nodes": [{"node_id": "build", "work_id": "cli-build"}, {"node_id": "test", "work_id": "cli-test", "depends_on": ["build"]}]}), encoding="utf-8")
            db_file = root / "rocksoul.sqlite3"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--db", str(db_file), "create", str(graph_file)]), 0)
            self.assertEqual(json.loads(output.getvalue())["graph"]["graph_id"], "cli-pipeline")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--db", str(db_file), "list"]), 0)
            self.assertEqual(json.loads(output.getvalue())["total"], 1)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--db", str(db_file), "verify", "cli-pipeline"]), 0)
            self.assertTrue(json.loads(output.getvalue())["ok"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--db", str(db_file), "readiness", "cli-pipeline"]), 0)
            self.assertEqual(json.loads(output.getvalue())["blocked_nodes"], ["build", "test"])

    def test_invalid_graph_file_returns_error_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_file = root / "bad.json"
            graph_file.write_text('{"graph_id":"bad","nodes":[]}', encoding="utf-8")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                result = main(["--db", str(root / "db.sqlite3"), "create", str(graph_file)])
            self.assertEqual(result, 2)
            self.assertIn("nodes must contain", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
