from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Logger singleton ─────────────────────────────────────────────────────────

logger = logging.getLogger("stylisttg")

_configured = False


def configure_logging(*, log_dir: str | Path = "logs", level: int = logging.INFO) -> None:
    """Configure structured logging to console and file. Safe to call multiple times."""
    global _configured
    if _configured:
        return
    _configured = True

    logger.setLevel(level)
    logger.propagate = False

    # Console handler — human-readable, colored
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(_ColorFormatter())
    logger.addHandler(console)

    # File handler — JSON lines, machine-parseable
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        log_path / f"stylisttg_{timestamp}.jsonl",
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(_JsonFormatter())
    logger.addHandler(file_handler)


# ── Public helpers ───────────────────────────────────────────────────────────

def log_event(event: str, **fields: Any) -> None:
    """Emit a structured log entry at INFO level."""
    logger.info("", extra={"event": event, "fields": fields})


def log_warn(event: str, **fields: Any) -> None:
    """Emit a structured log entry at WARNING level."""
    logger.warning("", extra={"event": event, "fields": fields})


def log_error(event: str, **fields: Any) -> None:
    """Emit a structured log entry at ERROR level."""
    logger.error("", extra={"event": event, "fields": fields})


def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    *,
    request_id: str | None = None,
    account_id: str | None = None,
    error_code: str | None = None,
) -> None:
    """Log an HTTP request/response pair."""
    level = logging.WARNING if status_code >= 400 else logging.INFO
    fields: dict[str, Any] = {
        "method": method,
        "path": path,
        "status": status_code,
        "duration_ms": round(duration_ms, 1),
    }
    if request_id:
        fields["request_id"] = request_id
    if account_id:
        fields["account_id"] = account_id
    if error_code:
        fields["error_code"] = error_code

    logger.log(level, "", extra={"event": "http_request", "fields": fields})


def generate_request_id() -> str:
    """Generate a short request ID for tracing."""
    return uuid.uuid4().hex[:12]


# ── Formatters ───────────────────────────────────────────────────────────────

_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
}
_RESET = "\033[0m"
_DIM = "\033[2m"


class _ColorFormatter(logging.Formatter):
    """Console formatter: colored level + human-readable event + fields."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        color = _COLORS.get(record.levelname, "")

        event = getattr(record, "event", None)
        fields = getattr(record, "fields", None)

        if event:
            parts = [
                f"{_DIM}{ts}{_RESET}",
                f"{color}{record.levelname:<7}{_RESET}",
                f"{event}",
            ]
            if fields:
                field_str = " ".join(f"{k}={_format_value(v)}" for k, v in fields.items())
                parts.append(f"{_DIM}{field_str}{_RESET}")
            return " ".join(parts)

        # Fallback for plain messages (e.g. from uvicorn)
        return f"{_DIM}{ts}{_RESET} {color}{record.levelname:<7}{_RESET} {record.getMessage()}"


class _JsonFormatter(logging.Formatter):
    """File formatter: one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", record.getMessage() or "log")
        fields = getattr(record, "fields", {})

        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": event,
        }
        if fields:
            entry.update(fields)
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
            entry["exception_type"] = record.exc_info[1].__class__.__name__

        return json.dumps(entry, default=str, ensure_ascii=False)


def _format_value(v: Any) -> str:
    """Format a value for console display."""
    if isinstance(v, str) and len(v) > 60:
        return f'"{v[:57]}..."'
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)
