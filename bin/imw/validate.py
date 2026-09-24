# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Strict input validation, grouping, auto-split and payload construction.

Turns raw alert-action result rows into a small set of validated
``RequestGroup`` objects, each carrying one operation and (for create) one or
more ITSI ``maintenance_calendar`` payloads.

Security: field values are treated strictly as data. Nothing here evaluates SPL,
Python, templates, shell, URLs or dynamic imports. Endpoint/security constants
are never taken from row data.
"""
import re

from . import constants as C
from .config import as_bool
from .errors import ErrorCategory, ValidationError
from .timeutil import parse_utc_to_epoch, validate_window

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# Opaque ITSI keys: conservative allow-list (no spaces).
_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
# request_id is a human-facing correlation id. Spaces are allowed; tab/newline
# and other control characters are not (the anchored class rejects them). The
# app stores state under a hashed KV _key, so spaces here are safe.
_REQID_RE = re.compile(r"^[A-Za-z0-9._: -]{1,128}$")

_WINDOW_ATTRS = ("title", "comment", "start_time", "end_time", "operation")


def _s(value):
    if value is None:
        return ""
    return _CONTROL.sub("", str(value)).strip()


def _require(row, field, request_hint=""):
    val = _s(row.get(field))
    if val == "":
        raise ValidationError(
            "Missing required field %r%s." % (field, request_hint),
            ErrorCategory.MISSING_FIELD,
        )
    return val


class RequestGroup(object):
    def __init__(self, request_id, operation):
        self.request_id = request_id
        self.operation = operation
        self.group_id = ""
        self.change_id = ""
        self.requested_by = ""
        self.title = ""
        self.comment = ""
        self.start_epoch = None
        self.end_epoch = None
        self.dry_run = None
        self.maintenance_window_key = ""
        self.objects = []  # list of {"_key","object_type"}
        self._seen_objs = set()

    def add_object(self, key, otype):
        pair = (otype, key)
        if pair in self._seen_objs:
            return
        self._seen_objs.add(pair)
        self.objects.append({"_key": key, "object_type": otype})

    def object_types(self):
        return {o["object_type"] for o in self.objects}

    def build_windows(self, auto_split):
        """Return a list of ITSI payloads (auto-split by object type)."""
        by_type = {}
        for o in self.objects:
            by_type.setdefault(o["object_type"], []).append(
                {"_key": o["_key"], "object_type": o["object_type"]})
        windows = []
        types = sorted(by_type.keys())
        if len(types) > 1 and not auto_split:
            raise ValidationError(
                "Request %s mixes entities and services in one window, which "
                "ITSI does not support. Enable auto_split or submit separately."
                % self.request_id,
                ErrorCategory.INVALID_INPUT,
            )
        for t in types:
            # ITSI enforces globally-unique maintenance-window titles. When a
            # request is auto-split by object type we must disambiguate the
            # title so the second create does not collide (HTTP 409).
            title = self.title
            if len(types) > 1:
                title = "%s [%s]" % (self.title, t)
            windows.append({
                "title": title,
                "comment": self.comment,
                "objects": by_type[t],
                "start_time": self.start_epoch,
                "end_time": self.end_epoch,
            })
        return windows


def normalize_and_group(rows, settings, now_epoch):
    """Parse rows into a dict of request_id -> RequestGroup, validated."""
    if not isinstance(rows, list):
        raise ValidationError("No result rows provided.",
                              ErrorCategory.INVALID_INPUT)
    if len(rows) == 0:
        raise ValidationError("No result rows to process.",
                              ErrorCategory.INVALID_INPUT)
    if len(rows) > settings.max_rows:
        raise ValidationError(
            "Too many rows (%d > max %d)." % (len(rows), settings.max_rows),
            ErrorCategory.LIMIT_EXCEEDED,
        )

    groups = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValidationError("Row %d is not a record." % idx,
                                  ErrorCategory.INVALID_INPUT)
        operation = _require(row, "operation")
        if operation not in C.SUPPORTED_OPERATIONS:
            raise ValidationError(
                "Unsupported operation %r." % operation,
                ErrorCategory.UNSUPPORTED_OPERATION,
            )
        settings.ensure_operation_allowed(operation)

        request_id = _require(row, "request_id")
        if not _REQID_RE.match(request_id):
            raise ValidationError(
                "request_id has invalid characters or length.",
                ErrorCategory.INVALID_INPUT,
            )

        grp = groups.get(request_id)
        if grp is None:
            grp = RequestGroup(request_id, operation)
            groups[request_id] = grp
        elif grp.operation != operation:
            raise ValidationError(
                "request_id %s used with conflicting operations." % request_id,
                ErrorCategory.PAYLOAD_CONFLICT,
            )

        _apply_row(grp, row, settings)

    # Post-process each group per operation type.
    for grp in groups.values():
        _finalize_group(grp, settings, now_epoch)
    return groups


def _apply_row(grp, row, settings):
    def set_consistent(attr, value, label):
        current = getattr(grp, attr)
        if current in (None, "") and value not in (None, ""):
            setattr(grp, attr, value)
        elif value not in (None, "") and current != value:
            raise ValidationError(
                "Conflicting %s within request_id %s (grouped rows must match)."
                % (label, grp.request_id),
                ErrorCategory.PAYLOAD_CONFLICT,
            )

    set_consistent("group_id", _s(row.get("group_id")), "group_id")
    set_consistent("change_id", _s(row.get("change_id")), "change_id")
    set_consistent("requested_by", _s(row.get("requested_by")), "requested_by")
    set_consistent("maintenance_window_key",
                   _s(row.get("maintenance_window_key")),
                   "maintenance_window_key")

    title = _s(row.get("title"))
    if title:
        if len(title) > settings.max_title_len:
            raise ValidationError("title exceeds maximum length.",
                                  ErrorCategory.LIMIT_EXCEEDED)
        set_consistent("title", title, "title")

    comment = _s(row.get("comment"))
    if comment:
        if len(comment) > settings.max_comment_len:
            raise ValidationError("comment exceeds maximum length.",
                                  ErrorCategory.LIMIT_EXCEEDED)
        set_consistent("comment", comment, "comment")

    # dry_run: any explicit value must be consistent within the group.
    if _s(row.get("dry_run")) != "":
        val = as_bool(row.get("dry_run"), settings.default_dry_run)
        if grp.dry_run is None:
            grp.dry_run = val
        elif grp.dry_run != val:
            raise ValidationError(
                "Conflicting dry_run within request_id %s." % grp.request_id,
                ErrorCategory.PAYLOAD_CONFLICT,
            )

    # Timestamps (only when present; required-ness enforced per operation).
    st = _s(row.get("start_time"))
    if st:
        epoch = parse_utc_to_epoch(st, "start_time")
        if grp.start_epoch is None:
            grp.start_epoch = epoch
        elif grp.start_epoch != epoch:
            raise ValidationError(
                "Conflicting start_time within request_id %s." % grp.request_id,
                ErrorCategory.PAYLOAD_CONFLICT,
            )
    et = _s(row.get("end_time"))
    if et:
        epoch = parse_utc_to_epoch(et, "end_time")
        if grp.end_epoch is None:
            grp.end_epoch = epoch
        elif grp.end_epoch != epoch:
            raise ValidationError(
                "Conflicting end_time within request_id %s." % grp.request_id,
                ErrorCategory.PAYLOAD_CONFLICT,
            )

    # Object (optional depending on operation).
    okey = _s(row.get("object_key"))
    otype = _s(row.get("object_type"))
    if okey or otype:
        if not okey or not otype:
            raise ValidationError(
                "Both object_key and object_type are required together "
                "(request_id %s)." % grp.request_id,
                ErrorCategory.MISSING_FIELD,
            )
        if otype not in C.SUPPORTED_OBJECT_TYPES:
            raise ValidationError(
                "Unsupported object_type %r." % otype,
                ErrorCategory.INVALID_INPUT,
            )
        if otype not in settings.allowed_object_types:
            raise ValidationError(
                "object_type %r is not allowed by configuration." % otype,
                ErrorCategory.NOT_ALLOWED,
            )
        if not _KEY_RE.match(okey):
            raise ValidationError(
                "object_key has invalid characters or length.",
                ErrorCategory.INVALID_INPUT,
            )
        if okey in settings.protected_keys:
            raise ValidationError(
                "object_key %s is on the protected deny-list." % okey,
                ErrorCategory.NOT_ALLOWED,
            )
        grp.add_object(okey, otype)


def _finalize_group(grp, settings, now_epoch):
    if grp.dry_run is None:
        grp.dry_run = settings.default_dry_run

    if settings.require_change_id and grp.operation in C.WRITE_OPERATIONS \
            and not grp.change_id:
        raise ValidationError(
            "change_id is required for write operations (request_id %s)."
            % grp.request_id, ErrorCategory.MISSING_FIELD)

    op = grp.operation
    if op == "create":
        _validate_create(grp, settings, now_epoch)
    elif op in ("update", "cancel"):
        if not grp.maintenance_window_key:
            raise ValidationError(
                "maintenance_window_key is required for %s (request_id %s)."
                % (op, grp.request_id), ErrorCategory.MISSING_FIELD)
        if not _KEY_RE.match(grp.maintenance_window_key):
            raise ValidationError(
                "maintenance_window_key has invalid characters or length.",
                ErrorCategory.INVALID_INPUT)
        if op == "update":
            # For update we require a full new window definition.
            _validate_create(grp, settings, now_epoch)
    elif op == "delete":
        if not grp.maintenance_window_key:
            raise ValidationError(
                "maintenance_window_key is required for delete (request_id %s)."
                % grp.request_id, ErrorCategory.MISSING_FIELD)
        if not _KEY_RE.match(grp.maintenance_window_key):
            raise ValidationError(
                "maintenance_window_key has invalid characters or length.",
                ErrorCategory.INVALID_INPUT)
    # list / validate: no extra requirements.


def _validate_create(grp, settings, now_epoch):
    if not grp.title:
        raise ValidationError(
            "title is required for create/update (request_id %s)."
            % grp.request_id, ErrorCategory.MISSING_FIELD)
    if settings.title_prefix and not grp.title.startswith(settings.title_prefix):
        raise ValidationError(
            "title must start with the required prefix %r."
            % settings.title_prefix, ErrorCategory.INVALID_INPUT)
    if grp.start_epoch is None or grp.end_epoch is None:
        raise ValidationError(
            "start_time and end_time are required for create/update "
            "(request_id %s)." % grp.request_id, ErrorCategory.MISSING_FIELD)
    validate_window(
        grp.start_epoch, grp.end_epoch, now_epoch,
        settings.max_duration_s, settings.max_future_horizon_s,
        settings.min_lead_s,
    )
    if not grp.objects:
        raise ValidationError(
            "At least one object_key/object_type is required for create/update "
            "(request_id %s)." % grp.request_id, ErrorCategory.MISSING_FIELD)
    if len(grp.objects) > settings.max_objects:
        raise ValidationError(
            "Too many objects (%d > max %d) in request_id %s."
            % (len(grp.objects), settings.max_objects, grp.request_id),
            ErrorCategory.LIMIT_EXCEEDED)
