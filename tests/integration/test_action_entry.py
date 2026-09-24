# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Offline end-to-end test of the modular alert action entry point.

Exercises argument handling, stdin JSON parsing, gzip results parsing, settings,
engine wiring and exit codes WITHOUT a Splunk runtime, by monkeypatching the
module-level transports to in-memory fakes.
"""
import csv
import gzip
import io
import json
import os
import sys
import tempfile
import unittest

BIN = os.path.join(os.path.dirname(__file__), "..", "..", "bin")
sys.path.insert(0, BIN)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

import imw.client as client_mod  # noqa: E402
import imw.idempotency as idem_mod  # noqa: E402
from fakes import FakeMaintTransport, FakeStateTransport  # noqa: E402


def _write_gz_results(rows):
    fd, path = tempfile.mkstemp(suffix=".csv.gz")
    os.close(fd)
    fields = sorted({k for r in rows for k in r})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        fh.write(buf.getvalue())
    return path


class TestActionEntry(unittest.TestCase):
    def setUp(self):
        # Patch module-level default transports used by the production code.
        self._maint = FakeMaintTransport()
        self._state = FakeStateTransport()
        self._orig_m = client_mod._default_transport
        self._orig_k = idem_mod._kv_transport
        client_mod._default_transport = self._maint
        idem_mod._kv_transport = lambda method, path, sk, json_body=None: \
            self._state(method, path, sk, json_body)
        # Import the action module fresh.
        import importlib
        self.action = importlib.import_module("itsi_maintenance_action")

    def tearDown(self):
        client_mod._default_transport = self._orig_m
        idem_mod._kv_transport = self._orig_k

    def _run(self, rows, configuration=None):
        path = _write_gz_results(rows)
        payload = {
            "session_key": "DEV-EPHEMERAL-KEY",
            "server_uri": "https://127.0.0.1:8089",
            "results_file": path,
            "search_name": "unit-test-search",
            "sid": "sid-123",
            "owner": "tester",
            "app": "itsi_maintenance_window_management",
            "configuration": configuration or {},
        }
        old_stdin, old_argv = sys.stdin, sys.argv
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.argv = ["itsi_maintenance_action.py", "--execute"]
        try:
            return self.action.main()
        finally:
            sys.stdin, sys.argv = old_stdin, old_argv
            os.remove(path)

    def test_not_execute_returns_1(self):
        old_argv = sys.argv
        sys.argv = ["itsi_maintenance_action.py"]
        try:
            self.assertEqual(self.action.main(), 1)
        finally:
            sys.argv = old_argv

    def test_dry_run_create_exit_0(self):
        rows = [{
            "operation": "create", "request_id": "E2E-1",
            "title": "CHG - e2e", "object_key": "ent1",
            "object_type": "entity", "start_time": "1800000000",
            "end_time": "1800003600", "dry_run": "true",
        }]
        self.assertEqual(self._run(rows), 0)

    def test_live_create_exit_0(self):
        rows = [{
            "operation": "create", "request_id": "E2E-2",
            "title": "CHG - e2e2", "object_key": "ent1",
            "object_type": "entity", "start_time": "1800000000",
            "end_time": "1800003600", "dry_run": "false",
        }]
        self.assertEqual(self._run(rows), 0)
        # A maintenance window should have been created in the fake backend.
        self.assertEqual(len(self._maint.windows), 1)

    def test_validation_failure_exit_3(self):
        rows = [{"operation": "create", "request_id": "E2E-3"}]  # missing fields
        self.assertEqual(self._run(rows), 3)

    def test_no_session_key_exit_2(self):
        path = _write_gz_results([{"operation": "list", "request_id": "x"}])
        payload = {"results_file": path, "configuration": {}}
        old_stdin, old_argv = sys.stdin, sys.argv
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.argv = ["itsi_maintenance_action.py", "--execute"]
        try:
            self.assertEqual(self.action.main(), 2)
        finally:
            sys.stdin, sys.argv = old_stdin, old_argv
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
