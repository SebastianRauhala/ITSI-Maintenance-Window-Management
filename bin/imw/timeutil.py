# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""UTC timestamp parsing and validation.

Confirmed against ITSI 4.21.3 source
(SA-ITOA/lib/maintenance_services/objects/maintenance_calendar.py::_validate_time_fields):
    start_time / end_time are stored as epoch SECONDS (float-coercible), UTC based,
    and ITSI requires start_time < end_time.

This module accepts a deliberately small, unambiguous set of input formats and
normalizes them to an integer epoch-seconds value. It refuses ambiguous local
times without an explicit offset, per requirement section 6.
"""
import datetime
import re

from .errors import ErrorCategory, ValidationError

_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

# Pure integer / float epoch seconds, e.g. "1789635600" or "1789635600.0".
_EPOCH_RE = re.compile(r"^\d{9,11}(\.\d+)?$")

# ISO-8601 with an explicit UTC designator or numeric offset. We REQUIRE a
# timezone; naive local timestamps are rejected as ambiguous.
_ISO_TZ_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?"
    r"(Z|[+-]\d{2}:?\d{2})$"
)


def parse_utc_to_epoch(value, field_name="timestamp"):
    """Parse ``value`` into an integer epoch-seconds value (UTC).

    Accepted forms:
      * epoch seconds as int/float/str (>= 1970, 9-11 digits)
      * ISO-8601 with a ``Z`` suffix or explicit numeric offset

    Rejected:
      * naive local timestamps (no offset) -> ambiguous
      * negative or out-of-range values
      * anything else
    """
    if value is None:
        raise ValidationError(
            "%s is required." % field_name, ErrorCategory.MISSING_FIELD
        )

    # Numeric epoch (int/float already).
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        epoch = float(value)
        return _finalize(epoch, field_name)

    if not isinstance(value, str):
        raise ValidationError(
            "%s must be a string or number." % field_name,
            ErrorCategory.INVALID_TIMESTAMP,
        )

    text = value.strip()
    if text == "":
        raise ValidationError(
            "%s is empty." % field_name, ErrorCategory.MISSING_FIELD
        )

    if _EPOCH_RE.match(text):
        return _finalize(float(text), field_name)

    if _ISO_TZ_RE.match(text):
        iso = text.replace(" ", "T")
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        # Normalize +HHMM to +HH:MM for fromisoformat on older Pythons.
        iso = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", iso)
        try:
            dt = datetime.datetime.fromisoformat(iso)
        except ValueError:
            raise ValidationError(
                "%s is not a valid ISO-8601 timestamp." % field_name,
                ErrorCategory.INVALID_TIMESTAMP,
            )
        if dt.tzinfo is None:
            raise ValidationError(
                "%s is missing a timezone; local times are ambiguous and "
                "rejected. Use epoch seconds or an ISO-8601 value with Z/offset."
                % field_name,
                ErrorCategory.INVALID_TIMESTAMP,
            )
        epoch = (dt - _EPOCH).total_seconds()
        return _finalize(epoch, field_name)

    raise ValidationError(
        "%s is not a recognized UTC timestamp. Provide epoch seconds or an "
        "ISO-8601 value with an explicit Z/offset." % field_name,
        ErrorCategory.INVALID_TIMESTAMP,
    )


def _finalize(epoch, field_name):
    if epoch < 0:
        raise ValidationError(
            "%s must be a non-negative epoch value." % field_name,
            ErrorCategory.INVALID_TIMESTAMP,
        )
    # Guard against obviously wrong magnitudes (e.g. milliseconds passed as int).
    # 100000000000 == year 5138; anything above is almost certainly ms.
    if epoch >= 100000000000:
        raise ValidationError(
            "%s looks like milliseconds; provide epoch SECONDS." % field_name,
            ErrorCategory.INVALID_TIMESTAMP,
        )
    return int(round(epoch))


def validate_window(start_epoch, end_epoch, now_epoch,
                    max_duration_s, max_future_horizon_s, min_lead_s):
    """Validate a start/end window against configured safety limits.

    All arguments are integer epoch seconds except the limits (seconds).
    Raises :class:`ValidationError` on any violation.
    """
    if end_epoch <= start_epoch:
        raise ValidationError(
            "end_time must be strictly later than start_time.",
            ErrorCategory.INVALID_TIMESTAMP,
        )
    duration = end_epoch - start_epoch
    if max_duration_s and duration > max_duration_s:
        raise ValidationError(
            "Maintenance duration %ds exceeds the configured maximum %ds."
            % (duration, max_duration_s),
            ErrorCategory.LIMIT_EXCEEDED,
        )
    if max_future_horizon_s and (start_epoch - now_epoch) > max_future_horizon_s:
        raise ValidationError(
            "start_time is further in the future than the configured horizon "
            "(%ds)." % max_future_horizon_s,
            ErrorCategory.LIMIT_EXCEEDED,
        )
    if min_lead_s and (start_epoch - now_epoch) < min_lead_s:
        raise ValidationError(
            "start_time does not meet the configured minimum lead time (%ds)."
            % min_lead_s,
            ErrorCategory.LIMIT_EXCEEDED,
        )
