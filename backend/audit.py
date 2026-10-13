"""Append-only audit trail for the agent team (output/audit_trail.json).

The file is one JSON array. Every write takes a thread lock and an exclusive
file lock, reads the array, appends, writes a temp file, fsyncs it and swaps it
in with os.replace, so the file is always valid JSON and is never truncated. A
file that cannot be parsed is renamed to audit_trail.corrupt-<ts>.json (never
deleted) and a new array is started.

Nothing secret or personal is written: values that look like API keys or bearer
tokens are redacted, secret-named fields are dropped, prompt and message text is
replaced by its length, and customer names/notes are left out of summaries.
AUDIT_TRAIL_PATH overrides the path (tests only).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_TRAIL_PATH = Path(os.getenv("AUDIT_TRAIL_PATH", str(PROJECT_ROOT / "output" / "audit_trail.json")))

logger = logging.getLogger("campus_customs.audit")
_lock = threading.Lock()

_SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|pk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,}|[A-Za-z0-9+/_\-]{32,})"
)
# Keys whose values are dropped. "token" alone or *_token, but not usage counts like input_tokens.
_SECRET_KEY_RE = re.compile(r"(api[_-]?key|(^|_)token$|secret|password|authorization|cookie)", re.I)
# Free text that may hold a person's words or name: logged as a length only.
_TEXT_FIELDS = {"task", "body", "subject", "recipient", "reason", "resolution_note", "prompt"}
# Fields left out of result summaries because they hold names or free text.
_PII_FIELDS = {"requester", "recipient", "body", "subject", "notes", "reason", "note", "description"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# Set by backend/agents.py from MODEL_NAME (the name is defined only there). Any
# dated provider snapshot of it (e.g. "<model>-2026-01-31" in a gateway error) is
# written as the plain pinned name, so logs never carry another model id.
_pinned_model: str | None = None
_snapshot_re: re.Pattern | None = None


def set_pinned_model(name: str) -> None:
    global _pinned_model, _snapshot_re
    _pinned_model = name
    _snapshot_re = re.compile(re.escape(name) + r"-\d{4}-\d{2}-\d{2}")


def normalize_model_ids(value: str) -> str:
    return _snapshot_re.sub(_pinned_model, value) if _snapshot_re else value


def _redact_str(value: str) -> str:
    value = normalize_model_ids(value)
    key = os.getenv("PORTKEY_API_KEY", "")
    if key and key in value:
        value = value.replace(key, "[REDACTED]")
    return _SECRET_VALUE_RE.sub("[REDACTED]", value)


def redact(value: Any) -> Any:
    """Recursively redact secrets from a JSON-like value."""
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _SECRET_KEY_RE.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def safe_args(args: dict[str, Any] | None) -> dict[str, Any] | None:
    """Tool/delegation arguments with free text replaced by its length and a short hash."""
    if args is None:
        return None
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k in _TEXT_FIELDS and isinstance(v, str):
            out[k] = {"chars": len(v), "sha256_8": hashlib.sha256(v.encode()).hexdigest()[:8]}
        else:
            out[k] = v
    return redact(out)


def summarize(result: Any, limit: int = 240) -> str:
    """A short, PII-free summary of a tool result."""
    if isinstance(result, dict):
        flat = {k: v for k, v in result.items() if k not in _PII_FIELDS and not isinstance(v, (dict, list))}
        nested = {k: f"<{type(v).__name__} len={len(v)}>" for k, v in result.items()
                  if k not in _PII_FIELDS and isinstance(v, (dict, list))}
        text = json.dumps({**flat, **nested}, default=str, ensure_ascii=False)
    else:
        text = str(result)
    text = _redact_str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def append(entries: list[dict[str, Any]]) -> None:
    """Append entries to the audit array. Never raises (auditing must not break a run)."""
    if not entries:
        return
    path = AUDIT_TRAIL_PATH
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path.with_name(path.name + ".lock"), "w") as lock_fh:
                fcntl.flock(lock_fh, fcntl.LOCK_EX)
                try:
                    data: list = []
                    if path.exists():
                        try:
                            with open(path, encoding="utf-8") as fh:
                                data = json.load(fh)
                            if not isinstance(data, list):
                                raise ValueError("audit trail is not a JSON array")
                        except (json.JSONDecodeError, ValueError):
                            corrupt = path.with_name(f"audit_trail.corrupt-{int(time.time())}.json")
                            os.replace(path, corrupt)  # preserve, never delete
                            logger.warning("audit trail unparseable; preserved as %s", corrupt.name)
                            data = []
                    data.extend(redact(entries))
                    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
                    with open(tmp, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, ensure_ascii=False, indent=2)
                        fh.flush()
                        os.fsync(fh.fileno())
                    os.replace(tmp, path)
                finally:
                    fcntl.flock(lock_fh, fcntl.LOCK_UN)
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit write failed: %s", type(exc).__name__)


def count() -> int:
    if not AUDIT_TRAIL_PATH.exists():
        return 0
    with open(AUDIT_TRAIL_PATH, encoding="utf-8") as fh:
        return len(json.load(fh))
