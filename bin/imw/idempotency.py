# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""App-owned idempotency and operation-state store, backed by an app KV Store
collection (``itsi_mw_automation_state``).

This is OUR collection, never an ITSI collection. State is stored in KV Store so
that it is shared across search-head cluster members; local files are never
authoritative.

Idempotency contract:
  * ``request_id`` is the KV Store ``_key`` -> uniqueness is enforced by KV Store.
  * Re-submitting the same ``request_id`` with the same ``payload_hash`` is a
    safe no-op (returns the prior result).
  * Re-submitting the same ``request_id`` with a different ``payload_hash`` is a
    hard conflict.
"""
import hashlib
import json
import time

from . import constants as C
from .errors import DuplicateRequestError, ErrorCategory, MwError, PayloadConflictError


def compute_payload_hash(operation, windows):
    """Deterministic SHA-256 over the normalized request.

    ``windows`` is a list of window dicts (each with title, comment, start_time,
    end_time, objects). Objects are sorted so ordering never affects the hash.
    """
    normalized = {
        "operation": operation,
        "windows": [],
    }
    for w in windows:
        objs = sorted(
            ({"_key": o["_key"], "object_type": o["object_type"]}
             for o in w.get("objects", [])),
            key=lambda o: (o["object_type"], o["_key"]),
        )
        normalized["windows"].append({
            "title": w.get("title"),
            "comment": w.get("comment", ""),
            "start_time": w.get("start_time"),
            "end_time": w.get("end_time"),
            "objects": objs,
        })
    normalized["windows"].sort(
        key=lambda w: (w["title"], w["start_time"], w["end_time"])
    )
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def state_key(request_id):
    """Derive a KV-Store-safe ``_key`` from a (possibly space-containing)
    request_id. The human request_id is stored as a field; the collection key is
    a deterministic hash so any allowed request_id maps to a safe, fixed-length
    key.
    """
    return "rid_" + hashlib.sha256(request_id.encode("utf-8")).hexdigest()


def _kv_transport(method, path, session_key, json_body=None):
    """KV Store transport using splunk.rest with a JSON body."""
    import splunk.rest as rest

    kwargs = {"method": method, "sessionKey": session_key,
              "raiseAllErrors": False}
    if json_body is not None:
        kwargs["jsonargs"] = json.dumps(json_body)
    response, content = rest.simpleRequest(path, **kwargs)
    if isinstance(content, bytes):
        content = content.decode("utf-8", "replace")
    try:
        status = int(response.status)
    except (AttributeError, ValueError, TypeError):
        status = 0
    return status, content


class StateStore(object):
    def __init__(self, session_key, transport=None):
        self._sk = session_key
        self._t = transport or _kv_transport

    def _data_path(self, key=None):
        base = C.STATE_COLLECTION_API
        if key:
            from urllib.parse import quote
            return base + "/" + quote(str(key), safe="")
        return base

    def get(self, request_id):
        status, body = self._t("GET", self._data_path(request_id), self._sk)
        if status == 404:
            return None
        if status != 200:
            raise MwError(ErrorCategory.STATE_ERROR,
                          "State backend read failed (%s)." % status,
                          http_status=status)
        try:
            return json.loads(body)
        except (ValueError, TypeError):
            raise MwError(ErrorCategory.STATE_ERROR,
                          "State backend returned malformed JSON.")

    def insert(self, record):
        status, body = self._t("POST", self._data_path(), self._sk, record)
        if status in (200, 201):
            return True
        if status == 409:
            # Concurrent/duplicate insert.
            return False
        raise MwError(ErrorCategory.STATE_ERROR,
                      "State backend insert failed (%s)." % status,
                      http_status=status)

    def update(self, request_id, record):
        status, _ = self._t("POST", self._data_path(request_id), self._sk,
                            record)
        if status in (200, 201):
            return True
        raise MwError(ErrorCategory.STATE_ERROR,
                      "State backend update failed (%s)." % status,
                      http_status=status)

    def delete(self, request_id):
        status, _ = self._t("DELETE", self._data_path(request_id), self._sk)
        return status in (200, 201, 404)


class IdempotencyManager(object):
    """Coordinates the state record lifecycle for a single request."""

    def __init__(self, store):
        self._store = store

    def begin(self, request_id, payload_hash, operation, extra=None):
        """Reserve the request_id. Returns ('new'|'duplicate', existing_record).

        Raises PayloadConflictError if the same request_id was used with a
        different payload.
        """
        now = int(time.time())
        key = state_key(request_id)
        record = {
            "_key": key,
            "request_id": request_id,
            "payload_hash": payload_hash,
            "operation": operation,
            "state": C.STATE_RECEIVED,
            "first_seen": now,
            "last_update": now,
            "attempt_count": 1,
            "itsi_window_keys": [],
            "http_status": None,
            "error_category": None,
            "result": None,
        }
        if extra:
            record.update(extra)

        inserted = self._store.insert(record)
        if inserted:
            return "new", record

        existing = self._store.get(key)
        if existing is None:
            # Lost race then vanished; treat as new attempt.
            return "new", record
        if existing.get("payload_hash") != payload_hash:
            raise PayloadConflictError(
                "request_id %r was already used with different data "
                "(payload conflict)." % request_id
            )
        if existing.get("operation") != operation:
            raise PayloadConflictError(
                "request_id %r was already used for a different operation."
                % request_id
            )
        return "duplicate", existing

    def get(self, request_id):
        """Return the state record for a request_id, or None."""
        return self._store.get(state_key(request_id))

    def mark(self, request_id, state, **fields):
        key = state_key(request_id)
        existing = self._store.get(key)
        if existing is None:
            existing = {"_key": key, "request_id": request_id}
        existing["state"] = state
        existing["last_update"] = int(time.time())
        existing.update(fields)
        self._store.update(key, existing)
        return existing

    def bump_attempt(self, request_id):
        key = state_key(request_id)
        existing = self._store.get(key) or {
            "_key": key, "request_id": request_id, "attempt_count": 0}
        existing["attempt_count"] = int(existing.get("attempt_count", 0)) + 1
        existing["last_update"] = int(time.time())
        self._store.update(key, existing)
        return existing["attempt_count"]


def is_terminal_success(record):
    return bool(record) and record.get("state") == C.STATE_SUCCEEDED


def raise_if_duplicate_success(record):
    """If a prior identical request already succeeded, signal a safe no-op."""
    if is_terminal_success(record):
        raise DuplicateRequestError(
            "request_id %r already completed successfully (idempotent no-op)."
            % record.get("request_id")
        )
