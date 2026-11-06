import unittest

from g4f.api import _append_bounded_capture


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


if __name__ == "__main__":
    unittest.main()
