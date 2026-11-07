from __future__ import annotations

"""Spawn-isolated MarkItDown worker; this module has no server startup side effects."""

import os
from typing import Any


def run_markitdown_extraction(
    connection,
    file_path: str,
    extension: str,
    mimetype: str,
    recognition_language: str | None,
    max_output_chars: int,
    max_memory_bytes: int,
    cpu_seconds: int,
) -> None:
    try:
        if os.name == "posix":
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
                resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
                resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            except (ImportError, OSError, ValueError):
                pass
        from g4f.integration.markitdown import MarkItDown, StreamInfo

        result = MarkItDown().convert(
            file_path,
            stream_info=StreamInfo(extension=extension, mimetype=mimetype),
            recognition_language=recognition_language,
        )
        text = result.text_content or ""
        truncated = len(text) > max_output_chars
        connection.send({
            "ok": True,
            "text": text[:max_output_chars],
            "truncated": truncated,
        })
    except BaseException:
        try:
            connection.send({"ok": False, "code": "document_extraction_failed"})
        except Exception:
            pass
    finally:
        connection.close()
