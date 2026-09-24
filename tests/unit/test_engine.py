# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

from fakes import FakeMaintTransport, FakeStateTransport  # noqa: E402
from imw.client import MaintenanceClient  # noqa: E402
from imw.config import Settings  # noqa: E402
from imw.engine import Engine  # noqa: E402
from imw.errors import MwError  # noqa: E402
from imw.idempotency import StateStore  # noqa: E402

NOW = 1789600000


def make_engine(cfg=None):
    mt = FakeMaintTransport()
    client = MaintenanceClient("sk", transport=mt)
    store = StateStore("sk", transport=FakeStateTransport())
    settings = Settings(cfg or {})
    eng = Engine("sk", settings, client, state_store=store,
                 itsi_version="4.21.3", now_epoch=NOW)
    return eng, mt


def create_rows(request_id="R1", dry_run="false", **over):
    base = dict(operation="create", request_id=request_id, title="CHG - test",
                object_key="ent1", object_type="entity",
                start_time=str(NOW + 3600), end_time=str(NOW + 7200),
                dry_run=dry_run)
    base.update(over)
    return [base]


class TestEngineDryRun(unittest.TestCase):
    def test_dry_run_no_write(self):
        eng, mt = make_engine()
        res = eng.run(create_rows(dry_run="true"))
        self.assertEqual(res[0]["result"], "success")
        self.assertTrue(res[0]["dry_run"])
        posts = [c for c in mt.calls if c[0] == "POST"]
        self.assertEqual(posts, [])


class TestEngineCreate(unittest.TestCase):
    def test_create_writes_and_returns_key(self):
        eng, mt = make_engine()
        res = eng.run(create_rows())
        self.assertEqual(res[0]["result"], "success")
        self.assertEqual(len(res[0]["maintenance_window_keys"]), 1)

    def test_idempotent_duplicate_noop(self):
        eng, mt = make_engine()
        eng.run(create_rows())
        posts_before = len([c for c in mt.calls if c[0] == "POST"
                            and c[1].rstrip("/").endswith("maintenance_calendar")])
        res2 = eng.run(create_rows())
        self.assertEqual(res2[0]["result"], "noop")
        posts_after = len([c for c in mt.calls if c[0] == "POST"
                          and c[1].rstrip("/").endswith("maintenance_calendar")])
        self.assertEqual(posts_before, posts_after)

    def test_payload_conflict_rejected(self):
        eng, mt = make_engine()
        eng.run(create_rows())
        res = eng.run(create_rows(end_time=str(NOW + 99999)))
        self.assertEqual(res[0]["result"], "failure")
        self.assertEqual(res[0]["error_category"], "payload_conflict")

    def test_auto_split_creates_two(self):
        eng, mt = make_engine()
        rows = create_rows() + create_rows(object_key="svc1",
                                           object_type="service")
        res = eng.run(rows)
        self.assertEqual(len(res[0]["maintenance_window_keys"]), 2)

    def test_entity_not_found(self):
        eng, mt = make_engine()
        mt.script("GET", "/entity/ent1", 404, {"message": "no"})
        res = eng.run(create_rows())
        self.assertEqual(res[0]["result"], "failure")
        self.assertEqual(res[0]["error_category"], "entity_not_found")

    def test_403_maps_to_authz(self):
        eng, mt = make_engine()
        mt.script("POST", "maintenance_calendar", 403, {"message": "denied"})
        res = eng.run(create_rows())
        self.assertEqual(res[0]["result"], "failure")
        self.assertEqual(res[0]["error_category"], "authorization_failed_403")


class TestEngineList(unittest.TestCase):
    def test_list(self):
        eng, mt = make_engine()
        eng.run(create_rows())
        res = eng.run([{"operation": "list", "request_id": "L1"}])
        self.assertEqual(res[0]["result"], "success")
        self.assertGreaterEqual(res[0]["window_count"], 1)


class TestEngineCancel(unittest.TestCase):
    def test_cancel_sets_end_time(self):
        eng, mt = make_engine()
        c = eng.run(create_rows())
        key = c[0]["maintenance_window_keys"][0]
        res = eng.run([{"operation": "cancel", "request_id": "C1",
                        "maintenance_window_key": key, "dry_run": "false"}])
        self.assertEqual(res[0]["result"], "success")
        # Future window collapses into the past: end_time == now.
        self.assertEqual(res[0]["cancelled_end_time"], NOW)
        self.assertFalse(res[0]["was_active"])


class TestEngineDelete(unittest.TestCase):
    def test_delete_disabled(self):
        eng, mt = make_engine()
        c = eng.run(create_rows())
        key = c[0]["maintenance_window_keys"][0]
        # Delete is rejected at pre-flight validation when not enabled.
        from imw.errors import ValidationError
        with self.assertRaises(ValidationError):
            eng.run([{"operation": "delete", "request_id": "D1",
                      "maintenance_window_key": key, "dry_run": "false"}])

    def test_delete_enabled(self):
        eng, mt = make_engine({"enable_delete": "true",
                               "allowed_operations":
                               "create,delete,list,cancel,update,validate"})
        c = eng.run(create_rows())
        key = c[0]["maintenance_window_keys"][0]
        res = eng.run([{"operation": "delete", "request_id": "D2",
                        "maintenance_window_key": key, "dry_run": "false"}])
        self.assertEqual(res[0]["result"], "success")
        self.assertTrue(res[0]["deleted"])


if __name__ == "__main__":
    unittest.main()
