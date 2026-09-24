# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Integration test for the itsimaintenance custom command's v2 chunked
protocol wiring (splunklib dispatch -> transform -> engine -> output).

Runs the command as a subprocess speaking the chunked protocol. Uses a
validation-failure row so no Splunk/ITSI runtime is required (the engine rejects
the row before any REST call; ITSI version detection degrades to 'unknown').
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

CMD = os.path.join(os.path.dirname(__file__), "..", "..", "bin",
                   "itsimaintenance.py")


def _chunk(meta, body=""):
    mb = json.dumps(meta).encode()
    bb = body.encode()
    return ("chunked 1.0,%d,%d\n" % (len(mb), len(bb))).encode() + mb + bb


class TestCommandProtocol(unittest.TestCase):
    def _run(self, rows_csv):
        dd = tempfile.mkdtemp(prefix="mw_test_")
        si = {
            "args": [], "raw_args": [], "dispatch_dir": dd, "sid": "s",
            "app": "itsi_maintenance_window_management", "owner": "admin",
            "username": "admin", "session_key": "dummy",
            "splunkd_uri": "https://127.0.0.1:8089", "splunk_version": "10.0.0",
            "search": "| itsimaintenance", "earliest_time": 0, "latest_time": 0,
        }
        inp = (_chunk({"action": "getinfo", "preview": False,
                       "searchinfo": si})
               + _chunk({"action": "execute", "finished": True}, rows_csv))
        p = subprocess.run([sys.executable, CMD], input=inp,
                           capture_output=True, timeout=120)
        return p.returncode, p.stdout.decode("utf-8", "replace")

    def test_missing_title_emits_failure(self):
        csv = ("operation,request_id,object_key,object_type,start_time,"
               "end_time,dry_run\r\n"
               "create,R1,k1,entity,1800000000,1800003600,true\r\n")
        rc, out = self._run(csv)
        self.assertEqual(rc, 0)
        self.assertIn("missing_required_field", out)
        self.assertIn("failure", out)

    def test_unsupported_operation_emits_failure(self):
        csv = "operation,request_id\r\nfrobnicate,R2\r\n"
        rc, out = self._run(csv)
        self.assertEqual(rc, 0)
        self.assertIn("failure", out)


if __name__ == "__main__":
    unittest.main()
