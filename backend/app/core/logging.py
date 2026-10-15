"""Logging estructurado sin secretos.

Un filtro redacta valores sensibles (contraseñas, tokens, cookies, cabeceras Authorization)
antes de escribir cualquier línea.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

_SECRET_PATTERNS = [
    re.compile(
        r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie|set-cookie)"
        r"(\"?\s*[:=]\s*\"?)([^\s\",;]+)"
    ),
    re.compile(r"wfa_[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)([^@\s]+)(@)"),
]


def redact(text: str) -> str:
    # Orden: primero los formatos específicos (Bearer, API keys, URLs), después clave=valor genérico.
    text = _SECRET_PATTERNS[2].sub("Bearer [REDACTED]", text)
    text = _SECRET_PATTERNS[1].sub("wfa_[REDACTED]", text)
    text = _SECRET_PATTERNS[3].sub(lambda m: f"{m.group(1)}[REDACTED]{m.group(3)}", text)
    text = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(str(a)) for a in record.args) if isinstance(record.args, tuple) else record.args
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "path", "method", "status", "duration_ms", "job_id", "report_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)
