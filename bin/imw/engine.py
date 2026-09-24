# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Operation orchestration: validate -> authorize -> idempotency -> reconcile
-> call ITSI -> record audit -> return result.
"""
from . import audit
from . import constants as C
from .errors import (
    DuplicateRequestError,
    ErrorCategory,
    MwError,
)
from .idempotency import (
    IdempotencyManager,
    StateStore,
    compute_payload_hash,
)
from .validate import normalize_and_group


class Engine(object):
    def __init__(self, session_key, settings, client, state_store=None,
                 itsi_version="unknown", now_epoch=None):
        import time
        self._sk = session_key
        self._settings = settings
        self._client = client
        self._store = state_store or StateStore(session_key)
        self._idem = IdempotencyManager(self._store)
        self._itsi_version = itsi_version
        self._now = int(now_epoch if now_epoch is not None else time.time())

    # -- public -----------------------------------------------------------
    def run(self, rows, context=None):
        """Process all rows. Returns a list of per-request result dicts."""
        context = context or {}
        groups = normalize_and_group(rows, self._settings, self._now)
        results = []
        for request_id, grp in groups.items():
            results.append(self._run_group(grp, context))
        return results

    # -- per group --------------------------------------------------------
    def _run_group(self, grp, context):
        base = {
            "request_id": grp.request_id,
            "group_id": grp.group_id,
            "change_id": grp.change_id,
            "requested_by": grp.requested_by,
            "operation": grp.operation,
            "dry_run": grp.dry_run,
            "app_version": C.APP_VERSION,
            "itsi_version": self._itsi_version,
        }
        base.update({k: v for k, v in context.items() if v is not None})
        try:
            if grp.operation == "list":
                out = self._op_list(grp)
            elif grp.operation == "validate":
                out = self._op_validate(grp)
            elif grp.operation == "create":
                out = self._op_create(grp)
            elif grp.operation == "update":
                out = self._op_update(grp)
            elif grp.operation == "cancel":
                out = self._op_cancel(grp)
            elif grp.operation == "delete":
                out = self._op_delete(grp)
            else:  # pragma: no cover - guarded earlier
                raise MwError(ErrorCategory.UNSUPPORTED_OPERATION,
                              "Unsupported operation.")
            base.update(out)
            base.setdefault("result", "success")
            audit.audit("operation_result", **base)
            return base
        except (MwError, DuplicateRequestError) as e:
            base["result"] = ("noop" if isinstance(e, DuplicateRequestError)
                              else "failure")
            base.update(e.as_dict())
            audit.audit("operation_result", **base)
            return base
        except Exception:  # noqa: BLE001 - never leak internals
            base["result"] = "failure"
            base["error_category"] = ErrorCategory.INTERNAL
            base["error_message"] = "Internal error (see server logs)."
            audit.error("operation_internal_error", request_id=grp.request_id)
            return base

    # -- operations -------------------------------------------------------
    def _op_list(self, grp):
        windows = self._client.list_windows(count=200)
        summary = _summarize_windows(windows)
        return {"result": "success", "window_count": len(summary),
                "windows": summary}

    def _op_validate(self, grp):
        # Dry-run style validation without writes.
        return self._plan(grp, resolve=True)

    def _op_create(self, grp):
        windows = grp.build_windows(self._settings.auto_split_mixed)
        payload_hash = compute_payload_hash("create", windows)

        plan = self._plan(grp, resolve=True, windows=windows)
        if grp.dry_run:
            plan["dry_run"] = True
            plan["payload_hash"] = payload_hash
            return plan

        status, record = self._idem.begin(grp.request_id, payload_hash, "create")
        if status == "duplicate":
            if record.get("state") == C.STATE_SUCCEEDED:
                raise DuplicateRequestError(
                    "request_id %s already created windows %s (idempotent "
                    "no-op)." % (grp.request_id,
                                 record.get("itsi_window_keys")))
            # Prior attempt uncertain -> reconcile before recreating.
            self._idem.bump_attempt(grp.request_id)

        self._idem.mark(grp.request_id, C.STATE_SUBMITTING,
                        payload_hash=payload_hash)

        created_keys = []
        try:
            for w in windows:
                existing = self._reconcile_find(w)
                if existing:
                    created_keys.append(existing)
                    continue
                resp = self._client.create_window(w)
                key = _extract_key(resp)
                if not key:
                    # Uncertain: response lacked a key. Force reconciliation.
                    self._idem.mark(grp.request_id, C.STATE_RECONCILE)
                    raise MwError(ErrorCategory.MALFORMED_RESPONSE,
                                  "Create response missing _key; "
                                  "reconciliation required.")
                created_keys.append(key)
        except MwError as e:
            if e.category == ErrorCategory.TIMEOUT_POST_SUBMIT:
                self._idem.mark(grp.request_id, C.STATE_RECONCILE,
                                error_category=e.category)
            else:
                self._idem.mark(grp.request_id, C.STATE_FAILED,
                                error_category=e.category,
                                http_status=e.http_status)
            raise

        self._idem.mark(grp.request_id, C.STATE_SUCCEEDED,
                        itsi_window_keys=created_keys, http_status=200,
                        result="success")
        plan["dry_run"] = False
        plan["maintenance_window_keys"] = created_keys
        plan["payload_hash"] = payload_hash
        return plan

    def _op_update(self, grp):
        windows = grp.build_windows(self._settings.auto_split_mixed)
        if len(windows) != 1:
            raise MwError(ErrorCategory.INVALID_INPUT,
                          "Update targets exactly one window; do not mix "
                          "object types on update.")
        new_window = windows[0]
        payload_hash = compute_payload_hash("update", windows)
        plan = self._plan(grp, resolve=True, windows=windows)
        plan["maintenance_window_key"] = grp.maintenance_window_key
        if grp.dry_run:
            plan["dry_run"] = True
            plan["payload_hash"] = payload_hash
            return plan

        existing = self._client.get_window(grp.maintenance_window_key)
        self._guard_completed(existing)
        merged = _merge_for_replace(existing, new_window)
        self._client.update_window(grp.maintenance_window_key, merged)
        return {"dry_run": False, "maintenance_window_key":
                grp.maintenance_window_key, "payload_hash": payload_hash}

    def _op_cancel(self, grp):
        plan = {"operation": "cancel",
                "maintenance_window_key": grp.maintenance_window_key}
        if grp.dry_run:
            plan["dry_run"] = True
            return plan
        existing = self._client.get_window(grp.maintenance_window_key)
        self._guard_completed(existing)
        start = int(float(existing.get("start_time", 0)))
        end = int(float(existing.get("end_time", 0)))
        is_active = start <= self._now < end
        if is_active and not self._settings.allow_cancel_active:
            raise MwError(ErrorCategory.NOT_ALLOWED,
                          "Cancelling an active window is disabled by config.")
        # Cancel semantics: ensure the window has no effect after 'now' while
        # preserving ITSI's start_time < end_time rule.
        #   * active window  -> end_time = now (start stays in the past)
        #   * future window  -> collapse into the past (start=now-1, end=now)
        new_end = self._now
        new_start = min(start, self._now - 1)
        cancelled = dict(existing)
        cancelled["start_time"] = new_start
        cancelled["end_time"] = new_end
        _strip_readonly(cancelled)
        self._client.update_window(grp.maintenance_window_key, cancelled)
        return {"dry_run": False,
                "maintenance_window_key": grp.maintenance_window_key,
                "cancelled_end_time": new_end, "was_active": is_active}

    def _op_delete(self, grp):
        if not self._settings.enable_delete:
            raise MwError(ErrorCategory.NOT_ALLOWED,
                          "Delete is disabled by default.")
        plan = {"operation": "delete",
                "maintenance_window_key": grp.maintenance_window_key}
        if grp.dry_run:
            plan["dry_run"] = True
            return plan
        # Deletion is gated by enable_delete + the delete capability. A window
        # in any state (future/active/completed) may be removed; completed
        # windows are inert. The completed-guard only protects update/cancel.
        existing = self._client.get_window(grp.maintenance_window_key)
        if not existing:
            raise MwError(ErrorCategory.NOT_FOUND,
                          "Maintenance window not found.")
        self._client.delete_window(grp.maintenance_window_key)
        return {"dry_run": False,
                "maintenance_window_key": grp.maintenance_window_key,
                "deleted": True}

    # -- helpers ----------------------------------------------------------
    def _plan(self, grp, resolve, windows=None):
        if resolve:
            for o in grp.objects:
                self._client.resolve_object(o["object_type"], o["_key"])
        out = {
            "title": grp.title,
            "start_time": grp.start_epoch,
            "end_time": grp.end_epoch,
            "object_keys": [o["_key"] for o in grp.objects],
            "object_types": sorted(grp.object_types()),
            "planned_window_count": len(windows) if windows else 0,
        }
        return out

    def _reconcile_find(self, window):
        """Look for an existing window matching this payload signature.

        Scales to any number of windows: first tries a server-side filter on the
        (globally unique) title; only falls back to paging the whole collection
        if the API appears to ignore the filter.
        """
        target = _signature(window)
        title = window.get("title")
        try:
            candidates = self._client.list_windows(
                filter_data={"title": title})
        except MwError:
            candidates = None

        if candidates is not None:
            for c in candidates:
                if _signature(c) == target:
                    return c.get("_key")
            # If every returned row actually matches the requested title, the
            # server honored the filter and an absence here is authoritative.
            if all(c.get("title") == title for c in candidates):
                return None
            # Otherwise the filter was ignored -> fall through to paging.

        return self._reconcile_find_paged(target)

    def _reconcile_find_paged(self, target):
        page = 500
        skip = 0
        max_scan = 100000  # safety bound
        while skip <= max_scan:
            try:
                batch = self._client.list_windows(count=page, skip=skip)
            except MwError:
                return None
            if not batch:
                return None
            for c in batch:
                if _signature(c) == target:
                    return c.get("_key")
            if len(batch) < page:
                return None
            skip += page
        return None

    def _guard_completed(self, existing):
        if not existing:
            raise MwError(ErrorCategory.NOT_FOUND, "Maintenance window not "
                          "found.")
        end = int(float(existing.get("end_time", 0)))
        if end <= self._now and not self._settings.allow_modify_completed:
            raise MwError(ErrorCategory.NOT_ALLOWED,
                          "Window is completed; modifying it is disabled.")


def _signature(window):
    objs = tuple(sorted(
        (o.get("object_type"), o.get("_key"))
        for o in window.get("objects", [])))
    return (
        window.get("title"),
        int(float(window.get("start_time", 0))),
        int(float(window.get("end_time", 0))),
        objs,
    )


def _merge_for_replace(existing, new_window):
    """Produce a full object for PUT (edit is a replace)."""
    merged = dict(existing) if isinstance(existing, dict) else {}
    for k in ("title", "comment", "objects", "start_time", "end_time"):
        if k in new_window:
            merged[k] = new_window[k]
    _strip_readonly(merged)
    return merged


# Server-managed fields observed on ITSI 4.21.3 GET responses. These must not be
# re-sent on edit; ITSI recomputes them.
_READONLY_FIELDS = (
    "sec_grp_list", "can_edit", "_user", "_version", "mod_source",
    "mod_timestamp", "object_type", "identifying_name", "create_time",
    "create_source", "create_by", "_owner", "version",
)


def _strip_readonly(obj):
    for ro in _READONLY_FIELDS:
        obj.pop(ro, None)
    return obj


def _extract_key(resp):
    if isinstance(resp, dict):
        return resp.get("_key") or resp.get("_id") or resp.get("id")
    if isinstance(resp, str):
        return resp or None
    if isinstance(resp, list) and resp:
        return _extract_key(resp[0])
    return None


def _summarize_windows(windows):
    out = []
    for w in windows or []:
        if not isinstance(w, dict):
            continue
        out.append({
            "_key": w.get("_key"),
            "title": w.get("title"),
            "start_time": w.get("start_time"),
            "end_time": w.get("end_time"),
            "object_count": len(w.get("objects", []) or []),
        })
    return out
