# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Shared test fakes. No secrets, no network."""
import json


class FakeMaintTransport(object):
    """Fake for imw.client transport: records calls, returns scripted responses.

    responses: dict keyed by (METHOD, path_suffix) -> (status, body_obj)
    Default GET list returns []. create returns a generated _key.
    """

    def __init__(self):
        self.calls = []
        self.windows = {}
        self._counter = 0
        self.scripted = {}
        self.raise_on = {}

    def script(self, method, suffix, status, body):
        self.scripted[(method, suffix)] = (status, body)

    def __call__(self, method, path, session_key, postargs=None, getargs=None):
        self.calls.append((method, path, postargs, getargs))
        for suffix, exc in self.raise_on.items():
            if suffix in path and method == exc[0]:
                raise exc[1]
        for (m, suffix), (status, body) in self.scripted.items():
            if m == method and path.endswith(suffix):
                return status, json.dumps(body) if body is not None else ""
        base = path.rstrip("/")
        is_collection = base.endswith("maintenance_calendar")
        if method == "POST" and is_collection:
            self._counter += 1
            key = "mwkey-%d" % self._counter
            data = json.loads(postargs["data"])
            data["_key"] = key
            self.windows[key] = data
            return 200, json.dumps({"_key": key})
        if method == "GET" and is_collection:
            return 200, json.dumps(list(self.windows.values()))
        if method == "GET" and "/maintenance_calendar/" in path:
            key = path.rsplit("/", 1)[-1]
            if key in self.windows:
                return 200, json.dumps(self.windows[key])
            return 404, json.dumps({"message": "not found"})
        if method == "PUT" and "/maintenance_calendar/" in path:
            key = path.rsplit("/", 1)[-1]
            data = json.loads(postargs["data"])
            data["_key"] = key
            self.windows[key] = data
            return 200, json.dumps({"_key": key})
        if method == "DELETE" and "/maintenance_calendar/" in path:
            key = path.rsplit("/", 1)[-1]
            self.windows.pop(key, None)
            return 200, ""
        if method == "GET" and ("/entity/" in path or "/service/" in path):
            key = path.rsplit("/", 1)[-1]
            return 200, json.dumps({"_key": key})
        if method == "GET" and path.endswith("get_supported_object_types"):
            return 200, json.dumps(["maintenance_calendar"])
        return 200, json.dumps([])


class FakeStateTransport(object):
    """Fake KV Store transport for imw.idempotency."""

    def __init__(self):
        self.records = {}

    def __call__(self, method, path, session_key, json_body=None):
        # Path is .../storage/collections/data/<collection>[/<key>]
        remainder = path.split("collections/data/", 1)[-1]
        parts = remainder.split("/", 1)
        key = parts[1] if len(parts) == 2 and parts[1] else None
        is_collection = key is None
        if method == "GET":
            if key and key in self.records:
                return 200, json.dumps(self.records[key])
            return 404, ""
        if method == "POST":
            rec = dict(json_body)
            k = key or rec.get("_key")
            if is_collection and k in self.records:
                return 409, ""  # insert conflict on existing _key
            self.records[k] = rec
            return 200, json.dumps({"_key": k})
        if method == "DELETE":
            self.records.pop(key, None)
            return 200, ""
        return 200, ""
