#!/usr/bin/env python3
# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""``itsimaintenance`` custom search command (chunked / v2 protocol).

Interactive interface to ITSI maintenance windows. Users pipe rows describing
the desired operation and see per-row results inline:

    | makeresults
    | eval operation="list", request_id="ui-1"
    | itsimaintenance

    | makeresults
    | eval operation="create", request_id="CHG123", title="CHG123 - maint",
           object_key="<KEY>", object_type="entity",
           start_time="1800000000", end_time="1800003600", dry_run="false"
    | itsimaintenance

Safety:
  * Declared with ``run_in_preview = false`` (default for chunked commands), so
    it does NOT execute while the user is typing / on partial preview data.
  * Reuses the same validated engine as the alert action, including the KV Store
    idempotency layer, so any accidental re-run is a no-op.
  * Uses only the ephemeral search session key (in memory) against the runtime
    ``splunkd_uri``. No stored credentials; the session key is never emitted.
"""
import json
import os
import sys

_BIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BIN, "lib"))
sys.path.insert(0, _BIN)

from splunklib.searchcommands import (  # noqa: E402
    dispatch,
    EventingCommand,
    Configuration,
    Option,
)
from splunklib.searchcommands.validators import Boolean  # noqa: E402

from imw import audit  # noqa: E402
from imw import constants as C  # noqa: E402
from imw.client import MaintenanceClient  # noqa: E402
from imw.config import Settings  # noqa: E402
from imw.engine import Engine  # noqa: E402
from imw.errors import MwError  # noqa: E402
from imw.version import detect_itsi_version  # noqa: E402

_INPUT_FIELDS = (
    "operation", "request_id", "group_id", "change_id", "requested_by",
    "title", "comment", "object_key", "object_type", "start_time", "end_time",
    "maintenance_window_key", "dry_run",
)


@Configuration()
class ItsiMaintenanceCommand(EventingCommand):
    """Create/inspect/update/cancel/delete ITSI maintenance windows."""

    dry_run = Option(
        doc="Override dry-run for this invocation (true/false). When omitted, "
            "the per-row dry_run field or the configured default is used.",
        require=False, validate=Boolean(),
    )

    def _load_settings(self):
        """Load safety settings from itsi_maintenance.conf [safety] (merged)."""
        cfg = {}
        try:
            confs = self.service.confs["itsi_maintenance"]
            if "safety" in confs:
                cfg = dict(confs["safety"].content)
        except Exception:  # noqa: BLE001 - fall back to safe defaults
            cfg = {}
        return Settings(cfg)

    def transform(self, records):
        si = self.metadata.searchinfo
        session_key = getattr(si, "session_key", None)
        splunkd_uri = getattr(si, "splunkd_uri", None)

        if not session_key:
            yield _err_record("__no_session__",
                              "No session key available to the command.")
            return

        settings = self._load_settings()
        client = MaintenanceClient(session_key, server_uri=splunkd_uri)
        itsi_version = detect_itsi_version(session_key)
        engine = Engine(session_key, settings, client, itsi_version=itsi_version)

        rows = []
        for rec in records:
            row = {k: rec.get(k) for k in _INPUT_FIELDS if rec.get(k) not in
                   (None, "")}
            if self.dry_run is not None:
                row["dry_run"] = "true" if self.dry_run else "false"
            rows.append(row)

        if not rows:
            yield _err_record("__no_rows__",
                              "No input rows. Pipe rows describing the "
                              "operation into | itsimaintenance.")
            return

        context = {
            "search_name": getattr(si, "search", None),
            "sid": getattr(si, "sid", None),
            "owner": getattr(si, "owner", None) or getattr(si, "username", None),
            "app": getattr(si, "app", None),
            "invoked_via": "custom_command",
        }

        try:
            results = engine.run(rows, context=context)
        except MwError as e:
            audit.audit("command_preflight_failure",
                        error_category=e.category, error_message=e.message)
            yield _err_record("__preflight__", e.message, e.category)
            return
        except Exception:  # noqa: BLE001
            audit.error("command_unexpected_failure")
            yield _err_record("__internal__", "Internal error (see logs).")
            return

        for r in results:
            # Expand list results into one row per window for tabular display.
            if r.get("operation") == "list" and isinstance(r.get("windows"),
                                                            list):
                if not r["windows"]:
                    yield _to_record({k: v for k, v in r.items()
                                      if k != "windows"})
                for w in r["windows"]:
                    row = {
                        "request_id": r.get("request_id"),
                        "operation": "list",
                        "result": "success",
                        "maintenance_window_key": w.get("_key"),
                        "title": w.get("title"),
                        "start_time": w.get("start_time"),
                        "end_time": w.get("end_time"),
                        "object_count": w.get("object_count"),
                    }
                    yield _to_record(row)
            else:
                yield _to_record(r)


def _to_record(result):
    out = {}
    for k, v in result.items():
        if isinstance(v, (list, tuple)):
            out[k] = ", ".join(str(x) for x in v)
        elif isinstance(v, dict):
            out[k] = json.dumps(v)
        elif isinstance(v, bool):
            out[k] = "true" if v else "false"
        elif v is None:
            continue
        else:
            out[k] = v
    # Sanitize defensively: never emit sensitive keys.
    for bad in ("session_key", "sessionKey", "authorization", "Authorization"):
        out.pop(bad, None)
    return out


def _err_record(request_id, message, category="invalid_input"):
    return {
        "request_id": request_id,
        "result": "failure",
        "error_category": category,
        "error_message": message,
        "app_version": C.APP_VERSION,
    }


if __name__ == "__main__":
    dispatch(ItsiMaintenanceCommand, sys.argv, sys.stdin, sys.stdout, __name__)
