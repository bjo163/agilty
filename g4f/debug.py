import sys
from contextvars import ContextVar, Token
from typing import Callable, List, Optional, Any

logging: bool = False
version_check: bool = True
version: Optional[str] = None
log_handler: Callable[..., None] = print
logs: List[str] = []
_request_log_sink: ContextVar[Optional[Callable[..., None]]] = ContextVar("g4f_request_log_sink", default=None)


def set_request_log_sink(sink: Callable[..., None]) -> Token:
    """Route debug messages to the current request without changing global state."""
    return _request_log_sink.set(sink)


def reset_request_log_sink(token: Token) -> None:
    """Restore the previous request-local debug sink."""
    _request_log_sink.reset(token)


def enable_logging(handler: Callable[..., None] = print) -> None:
    """Enable debug logging with optional handler."""
    global logging, log_handler
    logging = True
    log_handler = handler


def disable_logging() -> None:
    """Disable debug logging."""
    global logging
    logging = False


def log(*text: Any, file: Optional[Any] = None) -> None:
    """Log a message if logging is enabled."""
    if logging:
        sink = _request_log_sink.get()
        if sink is not None:
            sink(*text, file=file)
            return
        message = " ".join(map(str, text))
        logs.append(message)
        log_handler(*text, file=file, flush=True)


def info(*text: Any, file: Optional[Any] = None) -> None:
    """Log an informational message if logging is enabled."""
    if logging:
        log_handler(*text, file=file, flush=True)


def error(*error_args: Any, name: Optional[str] = None) -> None:
    """Log an error message to stderr."""
    formatted_errors = [
        e if isinstance(e, str) else f"{name or type(e).__name__}: {e}"
        for e in error_args
    ]
    log(*formatted_errors, file=sys.stderr)
