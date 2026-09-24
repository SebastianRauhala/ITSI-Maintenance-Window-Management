# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

from fakes import FakeStateTransport  # noqa: E402
from imw.errors import PayloadConflictError  # noqa: E402
from imw.idempotency import (  # noqa: E402
    IdempotencyManager,
    StateStore,
    compute_payload_hash,
)


def windows():
    return [{"title": "T", "comment": "", "start_time": 100, "end_time": 200,
             "objects": [{"_key": "e1", "object_type": "entity"}]}]


class TestHash(unittest.TestCase):
    def test_order_independent(self):
        w1 = [{"title": "T", "start_time": 1, "end_time": 2, "objects": [
            {"_key": "a", "object_type": "entity"},
            {"_key": "b", "object_type": "entity"}]}]
        w2 = [{"title": "T", "start_time": 1, "end_time": 2, "objects": [
            {"_key": "b", "object_type": "entity"},
            {"_key": "a", "object_type": "entity"}]}]
        self.assertEqual(compute_payload_hash("create", w1),
                         compute_payload_hash("create", w2))

    def test_changes_with_data(self):
        a = compute_payload_hash("create", windows())
        w = windows()
        w[0]["end_time"] = 999
        self.assertNotEqual(a, compute_payload_hash("create", w))


class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.store = StateStore("sk", transport=FakeStateTransport())
        self.idem = IdempotencyManager(self.store)

    def test_new_then_duplicate(self):
        h = compute_payload_hash("create", windows())
        status, _ = self.idem.begin("R1", h, "create")
        self.assertEqual(status, "new")
        status2, _ = self.idem.begin("R1", h, "create")
        self.assertEqual(status2, "duplicate")

    def test_payload_conflict(self):
        self.idem.begin("R1", "hash-a", "create")
        with self.assertRaises(PayloadConflictError):
            self.idem.begin("R1", "hash-b", "create")

    def test_operation_conflict(self):
        self.idem.begin("R1", "h", "create")
        with self.assertRaises(PayloadConflictError):
            self.idem.begin("R1", "h", "update")

    def test_mark_and_get(self):
        self.idem.begin("R1", "h", "create")
        self.idem.mark("R1", "succeeded", itsi_window_keys=["k1"])
        rec = self.idem.get("R1")
        self.assertEqual(rec["state"], "succeeded")
        self.assertEqual(rec["itsi_window_keys"], ["k1"])

    def test_request_id_with_spaces(self):
        rid = "Auto-Ent-MW 2026-09-23 14:42:30 CEST"
        status, rec = self.idem.begin(rid, "h", "create")
        self.assertEqual(status, "new")
        # KV _key is hashed/safe; request_id preserved as a field.
        self.assertTrue(rec["_key"].startswith("rid_"))
        self.assertNotIn(" ", rec["_key"])
        self.assertEqual(rec["request_id"], rid)
        # Same spaced id + same payload -> duplicate (idempotent).
        status2, _ = self.idem.begin(rid, "h", "create")
        self.assertEqual(status2, "duplicate")


if __name__ == "__main__":
    unittest.main()
