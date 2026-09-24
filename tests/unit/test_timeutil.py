# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bin"))

from imw.errors import ValidationError  # noqa: E402
from imw.timeutil import parse_utc_to_epoch, validate_window  # noqa: E402


class TestParse(unittest.TestCase):
    def test_epoch_seconds_str(self):
        self.assertEqual(parse_utc_to_epoch("1789635600"), 1789635600)

    def test_epoch_seconds_int(self):
        self.assertEqual(parse_utc_to_epoch(1789635600), 1789635600)

    def test_iso_z(self):
        # 2026-09-18T00:00:00Z
        v = parse_utc_to_epoch("2026-09-18T00:00:00Z")
        self.assertIsInstance(v, int)

    def test_iso_offset(self):
        a = parse_utc_to_epoch("2026-09-18T02:00:00+02:00")
        b = parse_utc_to_epoch("2026-09-18T00:00:00Z")
        self.assertEqual(a, b)

    def test_reject_naive_local(self):
        with self.assertRaises(ValidationError):
            parse_utc_to_epoch("2026-09-18 00:00:00")

    def test_reject_milliseconds(self):
        with self.assertRaises(ValidationError):
            parse_utc_to_epoch("1789635600000")

    def test_reject_garbage(self):
        with self.assertRaises(ValidationError):
            parse_utc_to_epoch("not-a-time")

    def test_missing(self):
        with self.assertRaises(ValidationError):
            parse_utc_to_epoch(None)


class TestWindow(unittest.TestCase):
    def test_end_before_start(self):
        with self.assertRaises(ValidationError):
            validate_window(100, 50, 0, 0, 0, 0)

    def test_end_equal_start(self):
        with self.assertRaises(ValidationError):
            validate_window(100, 100, 0, 0, 0, 0)

    def test_duration_limit(self):
        with self.assertRaises(ValidationError):
            validate_window(0, 1000, 0, 500, 0, 0)

    def test_future_horizon(self):
        with self.assertRaises(ValidationError):
            validate_window(10000, 10100, 0, 0, 5000, 0)

    def test_min_lead(self):
        with self.assertRaises(ValidationError):
            validate_window(100, 200, 0, 0, 0, 500)

    def test_ok(self):
        validate_window(1000, 2000, 0, 100000, 100000, 0)


if __name__ == "__main__":
    unittest.main()
