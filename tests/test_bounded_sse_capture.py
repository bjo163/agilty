import unittest

from g4f.api import _append_bounded_capture, _safe_body_for_log, _sanitize_query


class BoundedSSECaptureTests(unittest.TestCase):
    def test_capture_retains_all_bytes_below_limit(self):
        buffer = bytearray()
        self.assertFalse(_append_bounded_capture(buffer, b"event: message\n", 64))
        self.assertFalse(_append_bounded_capture(buffer, b"data: {}\n\n", 64))
        self.assertEqual(bytes(buffer), b"event: message\ndata: {}\n\n")

    def test_capture_retains_bounded_tail_after_overflow(self):
        buffer = bytearray(b"12345")
        self.assertTrue(_append_bounded_capture(buffer, b"6789", 6))
        self.assertEqual(bytes(buffer), b"456789")
        self.assertTrue(_append_bounded_capture(buffer, b"abcdefghi", 4))
        self.assertEqual(bytes(buffer), b"fghi")

    def test_zero_limit_disables_capture(self):
        buffer = bytearray()
        self.assertTrue(_append_bounded_capture(buffer, b"payload", 0))
        self.assertEqual(bytes(buffer), b"")

    def test_sensitive_json_fields_are_redacted(self):
        body = b'{"model":"demo","api_key":"secret","nested":{"password":"pw"}}'
        result = _safe_body_for_log(body, "application/json")
        self.assertEqual(result["api_key"], "***")
        self.assertEqual(result["nested"]["password"], "***")
        self.assertEqual(result["model"], "demo")

    def test_non_json_body_is_omitted(self):
        self.assertIn("omitted", _safe_body_for_log(b"private prompt", "text/plain"))

    def test_query_credentials_are_redacted(self):
        self.assertEqual(_sanitize_query("model=x&api_key=secret&access-token=abc"),
                         "model=x&api_key=%2A%2A%2A&access-token=%2A%2A%2A")


if __name__ == "__main__":
    unittest.main()
