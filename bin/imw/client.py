# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""ITSI maintenance_calendar REST client.

Transport: uses ``splunk.rest.simpleRequest`` when running inside splunkd. That
call targets the LOCAL management interface, supplies the runtime session key,
and lets the Splunk platform handle TLS trust to local splunkd. We never disable
certificate validation and never hard-code host/port.

For unit tests a transport callable can be injected.

Physical contract (confirmed against ITSI 4.21.3 source):
  * Body for POST/PUT is form field ``data`` = a JSON string of the object.
  * ``_key`` is carried in the URL path for GET-by-id / PUT / DELETE.
  * Owner in the path must be ``nobody``.
  * Responses are raw JSON (output_modes=json).
"""
import json

from . import constants as C
from .errors import (
    ErrorCategory,
    MwError,
    category_for_http_status,
)


def _default_transport(method, path_or_uri, session_key, postargs=None,
                       getargs=None):
    """Real transport backed by splunk.rest.simpleRequest.

    Returns a tuple ``(status_int, body_text)``.
    """
    import splunk.rest as rest  # imported lazily; only available in splunkd

    kwargs = {
        "method": method,
        "sessionKey": session_key,
        "raiseAllErrors": False,
    }
    if getargs:
        kwargs["getargs"] = getargs
    if postargs:
        kwargs["postargs"] = postargs
    response, content = rest.simpleRequest(path_or_uri, **kwargs)
    if isinstance(content, bytes):
        content = content.decode("utf-8", "replace")
    try:
        status = int(response.status)
    except (AttributeError, ValueError, TypeError):
        status = 0
    return status, content


class MaintenanceClient(object):
    def __init__(self, session_key, transport=None, server_uri=None):
        """
        :param session_key: ephemeral runtime session key (kept in memory only).
        :param transport: callable(method, path, session_key, postargs, getargs)
                          -> (status, body). Defaults to splunk.rest.
        :param server_uri: optional explicit management URI. When provided the
                           client sends absolute URIs; otherwise it sends paths
                           (simpleRequest resolves them to local splunkd).
        """
        self._sk = session_key
        self._transport = transport or _default_transport
        self._server_uri = server_uri.rstrip("/") if server_uri else None

    # -- internal ---------------------------------------------------------
    def _abs(self, path):
        if self._server_uri:
            return self._server_uri + path
        return path

    def _request(self, method, path, postargs=None, getargs=None,
                 uncertain_on_timeout=False):
        try:
            status, body = self._transport(
                method, self._abs(path), self._sk, postargs, getargs
            )
        except Exception as exc:  # noqa: BLE001 - normalized below
            msg = str(exc).lower()
            if "certificate" in msg or "ssl" in msg or "tls" in msg:
                raise MwError(ErrorCategory.TLS_FAILURE,
                              "TLS validation failed contacting splunkd.")
            if "timed out" in msg or "timeout" in msg:
                cat = (ErrorCategory.TIMEOUT_POST_SUBMIT
                       if uncertain_on_timeout
                       else ErrorCategory.TIMEOUT_PRE_SUBMIT)
                raise MwError(cat, "Request timed out contacting splunkd.")
            raise MwError(ErrorCategory.INTERNAL,
                          "Transport error contacting splunkd.")

        if status in (200, 201, 204):
            if status == 204 or not body:
                return None
            return self._parse_json(body)
        # Non-2xx -> normalized error.
        category = category_for_http_status(status)
        raise MwError(category, self._safe_error_text(body), http_status=status)

    @staticmethod
    def _parse_json(body):
        if body is None or body == "":
            return None
        try:
            return json.loads(body)
        except (ValueError, TypeError):
            raise MwError(ErrorCategory.MALFORMED_RESPONSE,
                          "ITSI returned a non-JSON or malformed response.")

    @staticmethod
    def _safe_error_text(body):
        """Extract a short, sanitized message from an ITSI error body."""
        if not body:
            return "ITSI request failed."
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                for key in ("message", "error", "messages"):
                    if key in data:
                        val = data[key]
                        if isinstance(val, list) and val:
                            val = val[0]
                        if isinstance(val, dict):
                            val = val.get("text") or val.get("message")
                        if val:
                            return str(val)[:300]
        except (ValueError, TypeError):
            pass
        return str(body)[:300]

    # -- discovery --------------------------------------------------------
    def get_supported_object_types(self):
        return self._request("GET", C.SUPPORTED_TYPES_API_PATH)

    # -- object resolution ------------------------------------------------
    def resolve_object(self, object_type, object_key):
        """Return True if an entity/service with ``object_key`` exists.

        Uses the itoa_interface GET-by-id endpoint. Treats the key as opaque.
        """
        if object_type == "entity":
            base = C.ENTITY_API_PATH
            missing = ErrorCategory.ENTITY_NOT_FOUND
        elif object_type == "service":
            base = C.SERVICE_API_PATH
            missing = ErrorCategory.SERVICE_NOT_FOUND
        else:
            raise MwError(ErrorCategory.INVALID_INPUT,
                          "Unsupported object_type: %r" % object_type)
        path = base + "/" + _url_quote(object_key)
        try:
            obj = self._request("GET", path, getargs={"fields": "_key"})
        except MwError as e:
            if e.http_status == 404:
                raise MwError(missing,
                              "%s key not found." % object_type)
            raise
        if not obj or (isinstance(obj, dict) and not obj.get("_key")
                       and not obj.get("_key".encode())):
            raise MwError(missing, "%s key not found." % object_type)
        return True

    # -- maintenance_calendar CRUD ---------------------------------------
    def list_windows(self, filter_data=None, fields=None, count=None, skip=None):
        getargs = {}
        if filter_data is not None:
            getargs["filter"] = json.dumps(filter_data)
        if fields:
            getargs["fields"] = ",".join(fields)
        if count is not None:
            getargs["count"] = str(count)
        if skip is not None:
            getargs["skip"] = str(skip)
        return self._request("GET", C.MAINTENANCE_API_PATH, getargs=getargs)

    def get_window(self, window_key):
        path = C.MAINTENANCE_API_PATH + "/" + _url_quote(window_key)
        return self._request("GET", path)

    def create_window(self, window_obj):
        postargs = {"data": json.dumps(window_obj)}
        # A create timeout is UNCERTAIN: the window may or may not exist.
        return self._request(
            "POST", C.MAINTENANCE_API_PATH, postargs=postargs,
            uncertain_on_timeout=True,
        )

    def update_window(self, window_key, window_obj):
        path = C.MAINTENANCE_API_PATH + "/" + _url_quote(window_key)
        postargs = {"data": json.dumps(window_obj)}
        # ITSI accepts PUT or POST for edit-by-id; PUT matches capability.put.
        # Edit is a full object replace, so callers must pass the complete object
        # (read-modify-write). See reconcile.update_window / cancel_window.
        return self._request(
            "PUT", path, postargs=postargs, uncertain_on_timeout=True,
        )

    def delete_window(self, window_key):
        path = C.MAINTENANCE_API_PATH + "/" + _url_quote(window_key)
        return self._request("DELETE", path, uncertain_on_timeout=True)


def _url_quote(value):
    """Path-encode an opaque identifier. Never interpolate raw."""
    from urllib.parse import quote

    return quote(str(value), safe="")
