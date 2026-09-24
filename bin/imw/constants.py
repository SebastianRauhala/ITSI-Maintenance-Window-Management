# Copyright (c) 2026. Licensed under the Apache License, Version 2.0.
"""
Fixed, non-overridable application constants for ITSI Maintenance Window Management.

SECURITY: Nothing in this module may be replaced by search-result content or by
user configuration at runtime. Endpoint paths, namespace, owner and object type
are compile-time constants. This is intentional and required by the security
model (see docs/THREAT_MODEL.md).

The maintenance_calendar endpoint below was confirmed against ITSI 4.21.3 by
reading the installed handler source:
  SA-ITOA/default/restmap.conf  (stanza maintenance_services_interface_*)
  SA-ITOA/bin/maintenance_services_interface_splunkd.py
  SA-ITOA/lib/maintenance_services/maintenance_services_rest_provider/...
"""

APP_ID = "itsi_maintenance_window_management"
APP_VERSION = "1.1.0"

# ITSI backend app + owner. Owner MUST be "nobody": the ITSI provider explicitly
# rejects any other owner for maintenance_calendar
# (maintenance_services_rest_provider: 'Maintenance objects can only exist at
# app level (owner="nobody")').
ITSI_APP_NAMESPACE = "SA-ITOA"
ITSI_OWNER_NAMESPACE = "nobody"

MAINTENANCE_OBJECT_TYPE = "maintenance_calendar"

# Confirmed authoritative endpoint (NOT the /itoa_interface/ candidate, which 404s).
MAINTENANCE_API_PATH = (
    "/servicesNS/nobody/SA-ITOA/maintenance_services_interface/maintenance_calendar"
)
# Endpoint that returns the supported object types for the maintenance interface.
SUPPORTED_TYPES_API_PATH = (
    "/servicesNS/nobody/SA-ITOA/maintenance_services_interface/get_supported_object_types"
)

# Endpoints used to resolve/validate entity and service keys (read-only GET).
# itoa_interface is the generic ITSI object interface.
ENTITY_API_PATH = "/servicesNS/nobody/SA-ITOA/itoa_interface/entity"
SERVICE_API_PATH = "/servicesNS/nobody/SA-ITOA/itoa_interface/service"

SUPPORTED_OBJECT_TYPES = frozenset({"entity", "service"})
SUPPORTED_OPERATIONS = frozenset(
    {"validate", "list", "create", "update", "cancel", "delete"}
)

# Operations that write to ITSI.
WRITE_OPERATIONS = frozenset({"create", "update", "cancel", "delete"})

# App-owned KV Store collection for idempotency / operation state.
# This is OUR collection, never an ITSI collection.
STATE_COLLECTION = "itsi_mw_automation_state"
STATE_COLLECTION_API = (
    "/servicesNS/nobody/{app}/storage/collections/data/{collection}".format(
        app=APP_ID, collection=STATE_COLLECTION
    )
)

# Custom capability defined by this app (authorize.conf). Used to group app
# administration and gate the app-owned KV state collection. Maintenance-window
# operations themselves are enforced by ITSI's native capabilities below.
CAP_MANAGE = "manage_itsi_maintenance_windows"

# Native ITSI capabilities required at the ITSI REST layer (informational; the
# ITSI handler enforces these itself).
ITSI_CAP_READ = "read_maintenance_calendar"
ITSI_CAP_WRITE = "write_maintenance_calendar"
ITSI_CAP_DELETE = "delete_maintenance_calendar"

# Operation state machine values.
STATE_RECEIVED = "received"
STATE_VALIDATING = "validating"
STATE_VALIDATED = "validated"
STATE_SUBMITTING = "submitting"
STATE_RECONCILE = "reconciliation_required"
STATE_SUCCEEDED = "succeeded"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"

# HTTP timeouts (seconds).
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30

# Retry policy (only applied to safe/idempotent operations).
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 0.5  # seconds; exponential

# Log field used to mark the app version / itsi version in audit records.
SESSION_KEY_REDACTION = "<redacted>"
