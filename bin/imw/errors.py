# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""Typed error categories for ITSI Maintenance Window Management.

Every failure is mapped to one of these categories so that audit records and
alert-action results carry a stable, non-sensitive ``error_category`` string.
No exception here ever carries a session key, authorization header, password or
raw response headers.
"""


class ErrorCategory(object):
    INVALID_INPUT = "invalid_input"
    MISSING_FIELD = "missing_required_field"
    INVALID_TIMESTAMP = "invalid_timestamp"
    ENTITY_NOT_FOUND = "entity_not_found"
    SERVICE_NOT_FOUND = "service_not_found"
    AMBIGUOUS_OBJECT = "ambiguous_object_resolution"
    DUPLICATE_REQUEST = "duplicate_request"
    PAYLOAD_CONFLICT = "payload_conflict"
    BAD_REQUEST = "bad_request_400"
    AUTHN_FAILED = "authentication_failed_401"
    AUTHZ_FAILED = "authorization_failed_403"
    NOT_FOUND = "not_found_404"
    CONFLICT = "conflict_409"
    THROTTLED = "throttled_429"
    SERVER_ERROR = "server_error_5xx"
    TLS_FAILURE = "tls_validation_failure"
    TIMEOUT_PRE_SUBMIT = "timeout_before_submission"
    TIMEOUT_POST_SUBMIT = "timeout_after_possible_submission"
    MALFORMED_RESPONSE = "malformed_api_response"
    UNSUPPORTED_VERSION = "unsupported_itsi_version"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    LIMIT_EXCEEDED = "limit_exceeded"
    NOT_ALLOWED = "operation_not_allowed"
    STATE_ERROR = "state_backend_error"
    INTERNAL = "internal_error"


# Categories for which a bounded retry with backoff is safe *for reads* or for
# operations that have already been made idempotent by reconciliation.
RETRYABLE_CATEGORIES = frozenset(
    {
        ErrorCategory.THROTTLED,
        ErrorCategory.SERVER_ERROR,
        ErrorCategory.TIMEOUT_PRE_SUBMIT,
    }
)


class MwError(Exception):
    """Base application error.

    :param category: one of ``ErrorCategory`` values.
    :param message: sanitized, human-readable message (no secrets).
    :param http_status: optional upstream HTTP status code.
    :param retryable: explicit override for retry decisions.
    """

    def __init__(self, category, message, http_status=None, retryable=None):
        super(MwError, self).__init__(message)
        self.category = category
        self.message = message
        self.http_status = http_status
        if retryable is None:
            self.retryable = category in RETRYABLE_CATEGORIES
        else:
            self.retryable = retryable

    def as_dict(self):
        return {
            "error_category": self.category,
            "error_message": self.message,
            "http_status": self.http_status,
            "retryable": self.retryable,
        }


class ValidationError(MwError):
    def __init__(self, message, category=ErrorCategory.INVALID_INPUT):
        super(ValidationError, self).__init__(category, message, retryable=False)


class AuthorizationError(MwError):
    def __init__(self, message):
        super(AuthorizationError, self).__init__(
            ErrorCategory.AUTHZ_FAILED, message, http_status=403, retryable=False
        )


class DuplicateRequestError(MwError):
    def __init__(self, message):
        super(DuplicateRequestError, self).__init__(
            ErrorCategory.DUPLICATE_REQUEST, message, retryable=False
        )


class PayloadConflictError(MwError):
    def __init__(self, message):
        super(PayloadConflictError, self).__init__(
            ErrorCategory.PAYLOAD_CONFLICT, message, retryable=False
        )


def category_for_http_status(status):
    """Map an HTTP status code to an :class:`ErrorCategory`."""
    if status == 400:
        return ErrorCategory.BAD_REQUEST
    if status == 401:
        return ErrorCategory.AUTHN_FAILED
    if status == 403:
        return ErrorCategory.AUTHZ_FAILED
    if status == 404:
        return ErrorCategory.NOT_FOUND
    if status == 409:
        return ErrorCategory.CONFLICT
    if status == 429:
        return ErrorCategory.THROTTLED
    if status and 500 <= status < 600:
        return ErrorCategory.SERVER_ERROR
    return ErrorCategory.MALFORMED_RESPONSE
