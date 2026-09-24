# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Runtime configuration / safety controls for the alert action.

Values originate from ``alert_actions.conf`` (defaults) and per-saved-search
``param.*`` overrides delivered in the alert payload's ``configuration`` dict.
Fixed security constants live in :mod:`imw.constants` and are NOT configurable.
"""
from .errors import ErrorCategory, ValidationError

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return default


def as_int(value, default):
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


class Settings(object):
    """Parsed, bounded safety controls."""

    def __init__(self, cfg=None):
        cfg = cfg or {}
        # Behavior
        self.default_dry_run = as_bool(cfg.get("default_dry_run"), True)
        self.enable_delete = as_bool(cfg.get("enable_delete"), False)
        self.allow_cancel_active = as_bool(cfg.get("allow_cancel_active"), True)
        self.allow_modify_completed = as_bool(
            cfg.get("allow_modify_completed"), False)
        self.require_change_id = as_bool(cfg.get("require_change_id"), False)
        self.auto_split_mixed = as_bool(cfg.get("auto_split_mixed"), True)

        # Limits
        self.max_rows = as_int(cfg.get("max_rows_per_invocation"), 2000)
        self.max_objects = as_int(cfg.get("max_objects_per_window"), 1000)
        self.max_duration_s = as_int(cfg.get("max_duration_seconds"), 7 * 86400)
        self.max_future_horizon_s = as_int(
            cfg.get("max_future_horizon_seconds"), 365 * 86400)
        self.min_lead_s = as_int(cfg.get("min_lead_seconds"), 0)
        self.max_title_len = as_int(cfg.get("max_title_length"), 256)
        self.max_comment_len = as_int(cfg.get("max_comment_length"), 1024)
        self.max_request_id_len = as_int(cfg.get("max_request_id_length"), 128)

        # Allowed operations / object types (intersected with the fixed sets).
        self.allowed_operations = _csv_set(
            cfg.get("allowed_operations"),
            default={"validate", "list", "create", "update", "cancel"},
        )
        self.allowed_object_types = _csv_set(
            cfg.get("allowed_object_types"), default={"entity", "service"})

        # Required title prefix (optional).
        self.title_prefix = (cfg.get("required_title_prefix") or "").strip()

        # Protected object deny-list (keys that may never be maintained).
        self.protected_keys = _csv_set(cfg.get("protected_object_keys"),
                                       default=set())

        # Optional summary index (must already exist / be approved).
        self.summary_index = (cfg.get("summary_index") or "").strip()

        if not self.enable_delete:
            self.allowed_operations.discard("delete")

    def ensure_operation_allowed(self, operation):
        if operation not in self.allowed_operations:
            raise ValidationError(
                "Operation %r is not enabled by configuration." % operation,
                ErrorCategory.NOT_ALLOWED,
            )
        if operation == "delete" and not self.enable_delete:
            raise ValidationError(
                "Delete is disabled by default. Enable it explicitly and with "
                "care.", ErrorCategory.NOT_ALLOWED,
            )


def _csv_set(value, default):
    if value is None or str(value).strip() == "":
        return set(default)
    return {p.strip() for p in str(value).split(",") if p.strip()}
