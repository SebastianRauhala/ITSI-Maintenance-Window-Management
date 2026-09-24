# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Structured, sanitized audit + application logging.

Guarantees:
  * The session key, Authorization headers, passwords and cookies are NEVER
    logged. The logger scrubs a small set of sensitive keys defensively.
  * Audit records are line-oriented key=value pairs written to
    ``$SPLUNK_HOME/var/log/splunk/itsi_maintenance_window_management.log`` and can be
    indexed via the default _internal monitor.
"""
import logging
import logging.handlers
import os
import re

from . import constants as C

_SENSITIVE_KEYS = re.compile(
    r"(?i)(session[_-]?key|authorization|passwd|password|cookie|token|"
    r"sessionKey|auth)"
)

_LOG_NAME = "itsi_maintenance_window_management"
_logger = None


def get_logger():
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(_LOG_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        try:
            log_dir = os.path.join(
                os.environ.get("SPLUNK_HOME", "."), "var", "log", "splunk")
            if not os.path.isdir(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, _LOG_NAME + ".log")
            handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=10 * 1024 * 1024, backupCount=5)
        except (OSError, IOError):
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)

    _logger = logger
    return logger


def _scrub(value):
    if isinstance(value, dict):
        return {k: (C.SESSION_KEY_REDACTION if _SENSITIVE_KEYS.search(str(k))
                    else _scrub(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def _fmt(value):
    s = str(value)
    if _SENSITIVE_KEYS.search(s) and "=" in s:
        return C.SESSION_KEY_REDACTION
    if any(c in s for c in (' ', '"', '=')):
        return '"%s"' % s.replace('"', "'")
    return s


def audit(event, **fields):
    """Emit one sanitized audit line."""
    logger = get_logger()
    safe = _scrub(fields)
    parts = ["event=%s" % event]
    for key in sorted(safe.keys()):
        if _SENSITIVE_KEYS.search(str(key)):
            continue
        val = safe[key]
        if val is None:
            continue
        parts.append("%s=%s" % (key, _fmt(val)))
    logger.info(" ".join(parts))


def info(message, **fields):
    audit(message, **fields)


def error(message, **fields):
    logger = get_logger()
    safe = _scrub(fields)
    parts = ["event=%s" % message]
    for key in sorted(safe.keys()):
        if _SENSITIVE_KEYS.search(str(key)):
            continue
        if safe[key] is None:
            continue
        parts.append("%s=%s" % (key, _fmt(safe[key])))
    logger.error(" ".join(parts))
