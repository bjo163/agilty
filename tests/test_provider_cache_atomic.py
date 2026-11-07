from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import g4f.gui.server.api as gui_api
from g4f.gui.server.api import Api


class ProviderCachePersistenceTests(unittest.TestCase):
    def test_provider_cache_is_written_as_valid_atomic_json(self):
        previous_writable = gui_api._providers_cache_writable
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "providers.json"
            try:
                gui_api._providers_cache_writable = True
                with patch.object(Api, "_providers_cache_file", return_value=target):
                    self.assertTrue(Api._write_providers_cache([{"name": "Example"}]))
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                                 [{"name": "Example"}])
                self.assertEqual([item.name for item in Path(directory).iterdir()],
                                 ["providers.json"])
            finally:
                gui_api._providers_cache_writable = previous_writable


if __name__ == "__main__":
    unittest.main()
