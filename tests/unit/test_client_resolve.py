# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

from fakes import FakeMaintTransport  # noqa: E402
from imw.client import MaintenanceClient  # noqa: E402
from imw.errors import MwError  # noqa: E402


class TestBatchedResolve(unittest.TestCase):
    def setUp(self):
        self.t = FakeMaintTransport()
        self.c = MaintenanceClient("sk", transport=self.t)

    def test_all_present(self):
        keys = ["k%03d" % i for i in range(450)]
        self.assertTrue(self.c.resolve_objects("entity", keys, batch_size=200))
        # 450 keys / 200 = 3 batched GETs on the entity collection.
        gets = [c for c in self.t.calls if c[0] == "GET"
                and c[1].rstrip("/").endswith("/entity")]
        self.assertEqual(len(gets), 3)

    def test_missing_key_raises(self):
        self.t.missing_object_keys = {"k002"}
        with self.assertRaises(MwError) as ctx:
            self.c.resolve_objects("entity", ["k001", "k002", "k003"])
        self.assertEqual(ctx.exception.category, "entity_not_found")
        self.assertIn("k002", ctx.exception.message)

    def test_service_missing_category(self):
        self.t.missing_object_keys = {"s9"}
        with self.assertRaises(MwError) as ctx:
            self.c.resolve_objects("service", ["s1", "s9"])
        self.assertEqual(ctx.exception.category, "service_not_found")

    def test_dedup_and_empty(self):
        self.assertTrue(self.c.resolve_objects("entity", []))
        self.assertTrue(self.c.resolve_objects("entity", ["a", "a", "b"]))


if __name__ == "__main__":
    unittest.main()
