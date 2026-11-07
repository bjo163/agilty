from __future__ import annotations

import os
import threading
import unittest
from unittest.mock import patch

from g4f import debug
from g4f.api import _api_auth_mode, _matches_api_key, _principal_id
from g4f.gui.server.backend_api import _bounded_int_env, _parse_bool_query


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



class ApiAuthPolicyTests(unittest.TestCase):
    def test_auth_mode_defaults_to_optional_and_can_require_authentication(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_api_auth_mode(), "optional")
        with patch.dict(os.environ, {"G4F_AUTH_MODE": "required"}, clear=True):
            self.assertEqual(_api_auth_mode(), "required")
        with patch.dict(os.environ, {"G4F_API_HOST": "0.0.0.0"}, clear=True):
            self.assertEqual(_api_auth_mode(), "required")
        with patch.dict(os.environ, {"G4F_API_HOST": "::1"}, clear=True):
            self.assertEqual(_api_auth_mode(), "optional")

    def test_auth_mode_rejects_unknown_values(self):
        with patch.dict(os.environ, {"G4F_AUTH_MODE": "sometimes"}, clear=True):
            with self.assertRaises(ValueError):
                _api_auth_mode()

    def test_api_key_accepts_supported_headers_and_bearer(self):
        self.assertTrue(_matches_api_key("secret", {"g4f-api-key": "secret"}))
        self.assertTrue(_matches_api_key("secret", {"x-api-key": "secret"}))
        self.assertTrue(_matches_api_key("secret", {"authorization": "Bearer secret"}))
        self.assertFalse(_matches_api_key("secret", {"x-api-key": "wrong"}))
        self.assertFalse(_matches_api_key("secret", {}))

    def test_principal_id_is_stable_opaque_and_namespaced(self):
        first = _principal_id("key", "example-secret")
        second = _principal_id("key", "example-secret")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("key_"))
        self.assertNotIn("example-secret", first)
        self.assertNotEqual(first, _principal_id("user", "example-secret"))


class UploadLimitConfigurationTests(unittest.TestCase):
    def test_upload_limits_use_defaults_and_clamp_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_bounded_int_env("G4F_MAX_UPLOAD_FILES", 10, 1, 50), 10)
        with patch.dict(os.environ, {"G4F_MAX_UPLOAD_FILES": "999"}, clear=True):
            self.assertEqual(_bounded_int_env("G4F_MAX_UPLOAD_FILES", 10, 1, 50), 50)
        with patch.dict(os.environ, {"G4F_MAX_UPLOAD_FILES": "invalid"}, clear=True):
            self.assertEqual(_bounded_int_env("G4F_MAX_UPLOAD_FILES", 10, 1, 50), 10)
        with patch.dict(os.environ, {"G4F_EXTRACTION_TIMEOUT_SECONDS": "999"}, clear=True):
            self.assertEqual(_bounded_int_env("G4F_EXTRACTION_TIMEOUT_SECONDS", 30, 3, 120), 120)
        with patch.dict(os.environ, {"G4F_EXTRACTION_MAX_OUTPUT_CHARS": "bad"}, clear=True):
            self.assertEqual(_bounded_int_env("G4F_EXTRACTION_MAX_OUTPUT_CHARS", 1_000_000, 1000, 5_000_000), 1_000_000)


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
