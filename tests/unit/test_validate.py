# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

from imw.config import Settings  # noqa: E402
from imw.errors import ValidationError  # noqa: E402
from imw.validate import normalize_and_group  # noqa: E402

NOW = 1789600000
START = str(NOW + 3600)
END = str(NOW + 7200)


def row(**kw):
    base = {"operation": "create", "request_id": "R1", "title": "T",
            "object_key": "ent1", "object_type": "entity",
            "start_time": START, "end_time": END, "dry_run": "true"}
    base.update(kw)
    return base


class TestGrouping(unittest.TestCase):
    def setUp(self):
        self.s = Settings({})

    def test_single_create(self):
        g = normalize_and_group([row()], self.s, NOW)
        self.assertIn("R1", g)
        self.assertEqual(len(g["R1"].objects), 1)

    def test_group_dedup_objects(self):
        g = normalize_and_group([row(), row()], self.s, NOW)
        self.assertEqual(len(g["R1"].objects), 1)

    def test_auto_split_mixed(self):
        rows = [row(object_key="ent1", object_type="entity"),
                row(object_key="svc1", object_type="service")]
        g = normalize_and_group(rows, self.s, NOW)
        windows = g["R1"].build_windows(self.s.auto_split_mixed)
        self.assertEqual(len(windows), 2)

    def test_conflicting_title(self):
        rows = [row(), row(title="OTHER")]
        with self.assertRaises(ValidationError):
            normalize_and_group(rows, self.s, NOW)

    def test_missing_request_id(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(request_id="")], self.s, NOW)

    def test_missing_title_create(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(title="")], self.s, NOW)

    def test_bad_object_type(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(object_type="host")], self.s, NOW)

    def test_end_equals_start(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(end_time=START)], self.s, NOW)

    def test_unsupported_operation(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(operation="frobnicate")], self.s, NOW)

    def test_operation_not_allowed(self):
        s = Settings({"allowed_operations": "list"})
        with self.assertRaises(ValidationError):
            normalize_and_group([row()], s, NOW)

    def test_too_many_rows(self):
        s = Settings({"max_rows_per_invocation": "1"})
        with self.assertRaises(ValidationError):
            normalize_and_group([row(), row(request_id="R2")], s, NOW)

    def test_title_prefix_enforced(self):
        s = Settings({"required_title_prefix": "CHG"})
        with self.assertRaises(ValidationError):
            normalize_and_group([row(title="nope")], s, NOW)
        normalize_and_group([row(title="CHG123")], s, NOW)

    def test_protected_key(self):
        s = Settings({"protected_object_keys": "ent1"})
        with self.assertRaises(ValidationError):
            normalize_and_group([row()], s, NOW)

    def test_require_change_id(self):
        s = Settings({"require_change_id": "true"})
        with self.assertRaises(ValidationError):
            normalize_and_group([row()], s, NOW)
        normalize_and_group([row(change_id="CHG1")], s, NOW)

    def test_update_requires_key(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(operation="update")], self.s, NOW)

    def test_delete_disabled_by_default(self):
        with self.assertRaises(ValidationError):
            normalize_and_group(
                [row(operation="delete", maintenance_window_key="k1")],
                self.s, NOW)

    def test_object_key_charset(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(object_key="bad key/../x")], self.s, NOW)

    def test_request_id_allows_spaces(self):
        # Spaces are permitted in request_id (stored under a hashed KV key).
        normalize_and_group([row(request_id="Auto MW 2026-09-23 14:42")],
                            self.s, NOW)

    def test_request_id_rejects_tab(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(request_id="Auto\tMW")], self.s, NOW)

    def test_request_id_rejects_newline(self):
        with self.assertRaises(ValidationError):
            normalize_and_group([row(request_id="Auto\nMW")], self.s, NOW)

    def test_url_field_is_data_only(self):
        # A URL supplied in a field is just rejected as an invalid key; it is
        # never fetched or interpreted.
        with self.assertRaises(ValidationError):
            normalize_and_group(
                [row(object_key="http://evil.example/x")], self.s, NOW)


if __name__ == "__main__":
    unittest.main()
