from __future__ import annotations

import threading
import unittest

from g4f import debug
from g4f.gui.server.backend_api import _parse_bool_query


class RequestDebugContextTests(unittest.TestCase):
    def test_debug_logs_are_isolated_between_threads(self):
        previous_logging = debug.logging
        previous_handler = debug.log_handler
        debug.logging = True
        debug.log_handler = lambda *args, **kwargs: None
        barrier = threading.Barrier(2)
        captured = {"a": [], "b": []}

        def worker(name: str) -> None:
            token = debug.set_request_log_sink(
                lambda *values, **kwargs: captured[name].append(" ".join(map(str, values)))
            )
            try:
                barrier.wait(timeout=2)
                debug.log(f"request-{name}")
                barrier.wait(timeout=2)
            finally:
                debug.reset_request_log_sink(token)

        threads = [
            threading.Thread(target=worker, args=("a",)),
            threading.Thread(target=worker, args=("b",)),
        ]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(captured, {"a": ["request-a"], "b": ["request-b"]})
        finally:
            debug.logging = previous_logging
            debug.log_handler = previous_handler

    def test_request_sink_is_reset_after_scope(self):
        previous_logging = debug.logging
        previous_handler = debug.log_handler
        debug.logging = True
        debug.log_handler = lambda *args, **kwargs: None
        captured = []
        token = debug.set_request_log_sink(lambda *values, **kwargs: captured.append(values))
        try:
            debug.log("inside")
        finally:
            debug.reset_request_log_sink(token)
            debug.logging = previous_logging
            debug.log_handler = previous_handler
        self.assertEqual(captured, [("inside",)])


class BooleanQueryParsingTests(unittest.TestCase):
    def test_supported_boolean_values(self):
        for value in ("true", "TRUE", "1", "yes", "on"):
            with self.subTest(value=value):
                self.assertIs(_parse_bool_query(value, False), True)
        for value in ("false", "FALSE", "0", "no", "off"):
            with self.subTest(value=value):
                self.assertIs(_parse_bool_query(value, True), False)

    def test_missing_and_invalid_values(self):
        self.assertIs(_parse_bool_query(None, True), True)
        self.assertIs(_parse_bool_query(None, False), False)
        with self.assertRaises(ValueError):
            _parse_bool_query("sometimes", False)


if __name__ == "__main__":
    unittest.main()
