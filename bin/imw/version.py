# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""ITSI version detection (best-effort, read-only)."""
from .errors import MwError


def detect_itsi_version(session_key, transport=None):
    """Return the installed ITSI app version string, or 'unknown'.

    Reads /services/apps/local/itsi via splunk.rest. Never raises.
    """
    try:
        if transport is None:
            import splunk.rest as rest

            response, content = rest.simpleRequest(
                "/services/apps/local/itsi",
                sessionKey=session_key,
                getargs={"output_mode": "json"},
                method="GET",
                raiseAllErrors=False,
            )
            if isinstance(content, bytes):
                content = content.decode("utf-8", "replace")
            status = int(getattr(response, "status", 0))
        else:
            status, content = transport(session_key)
        if status != 200:
            return "unknown"
        import json

        data = json.loads(content)
        entry = data.get("entry", [])
        if entry:
            return entry[0].get("content", {}).get("version", "unknown")
    except (MwError, ValueError, TypeError, KeyError, Exception):
        return "unknown"
    return "unknown"
