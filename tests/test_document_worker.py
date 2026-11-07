from __future__ import annotations

import unittest

from g4f.gui.server.document_worker import run_markitdown_extraction


class _CaptureConnection:
    def __init__(self):
        self.messages = []
        self.closed = False

    def send(self, value):
        self.messages.append(value)

    def close(self):
        self.closed = True


class DocumentWorkerTests(unittest.TestCase):
    def test_worker_returns_stable_failure_without_leaking_exception_text(self):
        connection = _CaptureConnection()
        run_markitdown_extraction(
            connection,
            "/definitely/not/a/real/document.pdf",
            ".pdf",
            "application/pdf",
            None,
            1000,
            512 * 1024 * 1024,
            5,
        )
        self.assertEqual(connection.messages, [{
            "ok": False, "code": "document_extraction_failed"
        }])
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
