#!/usr/bin/env python3
# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Modular alert action entry point for ITSI Maintenance Window Management.

Splunk invokes this script as::

    itsi_maintenance_action.py --execute

and delivers a JSON payload on stdin containing the ephemeral ``session_key``,
the runtime ``server_uri``, the gzipped ``results_file`` and the alert
``configuration`` (param.* values).

This script:
  * reads and parses the search results,
  * builds bounded safety settings from the configuration,
  * runs the orchestration engine (validate / dry-run / CRUD),
  * writes sanitized audit records,
  * NEVER logs or returns the session key.
"""
import csv
import gzip
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from imw import audit  # noqa: E402
from imw import constants as C  # noqa: E402
from imw.client import MaintenanceClient  # noqa: E402
from imw.config import Settings  # noqa: E402
from imw.engine import Engine  # noqa: E402
from imw.version import detect_itsi_version  # noqa: E402


def _read_results(results_file):
    if not results_file or not os.path.isfile(results_file):
        return []
    with gzip.open(results_file, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def _run(payload):
    session_key = payload.get("session_key") or ""
    server_uri = payload.get("server_uri") or None
    configuration = payload.get("configuration") or {}

    if not session_key:
        audit.error("no_session_key")
        sys.stderr.write("ERROR: no runtime session key supplied.\n")
        return 2

    rows = _read_results(payload.get("results_file"))

    settings = Settings(configuration)
    itsi_version = detect_itsi_version(session_key)
    client = MaintenanceClient(session_key, server_uri=server_uri)

    context = {
        "search_name": payload.get("search_name"),
        "sid": payload.get("sid"),
        "owner": payload.get("owner"),
        "app": payload.get("app"),
    }

    engine = Engine(session_key, settings, client, itsi_version=itsi_version)
    try:
        results = engine.run(rows, context=context)
    except Exception as exc:  # noqa: BLE001 - top-level guard
        # engine.run only raises on pre-flight validation errors.
        from imw.errors import MwError

        if isinstance(exc, MwError):
            audit.audit("preflight_failure",
                        error_category=exc.category,
                        error_message=exc.message,
                        search_name=context.get("search_name"))
            sys.stderr.write("VALIDATION FAILED: %s\n" % exc.message)
            return 3
        audit.error("unexpected_failure")
        sys.stderr.write("ERROR: unexpected failure (see server logs).\n")
        return 4

    failures = [r for r in results if r.get("result") == "failure"]
    for r in results:
        sys.stderr.write(
            "request_id=%s operation=%s dry_run=%s result=%s%s\n" % (
                r.get("request_id"), r.get("operation"), r.get("dry_run"),
                r.get("result"),
                (" error=%s" % r.get("error_category"))
                if r.get("error_category") else "",
            )
        )
    return 1 if failures else 0


def main():
    if "--execute" not in sys.argv:
        sys.stderr.write(
            "This is a Splunk modular alert action. Invoke via a saved search "
            "alert action, not directly.\n")
        return 1
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        audit.error("bad_payload")
        sys.stderr.write("ERROR: could not parse alert payload.\n")
        return 2
    return _run(payload)


if __name__ == "__main__":
    sys.exit(main())
