# ITSI 5.x Compatibility Analysis

**Status: Documentation-reviewed for ITSI 5.x; live validation pending.**
No ITSI 5.x instance was available. Do **not** treat 5.x as validated.

## Basis of the analysis
The maintenance functionality in ITSI 4.21.3 is implemented by the
`maintenance_services` package in `SA-ITOA` with:
- REST handler `maintenance_services_interface_splunkd.py` mounted at
  `/maintenance_services_interface/...` with an explicit **version path segment**
  (`vLatest` or `v<itsi_version>`) already built in.
- Object model `maintenance_calendar` storing `start_time`/`end_time` as UTC
  **epoch seconds**, `objects` as `{_key, object_type}` (entity|service),
  globally-unique titles, and server-managed fields.

## Expected to be stable in 5.x
- Endpoint shape `/servicesNS/nobody/SA-ITOA/maintenance_services_interface/maintenance_calendar`
  and the `data`=JSON request encoding (long-standing ITOA interface pattern).
- Epoch-seconds timestamps and `start_time < end_time` validation.
- Capabilities `read/write/delete_maintenance_calendar`.
- Single-object-type-per-window rule and unique-title enforcement.

## Watch items for 5.x (verify before enabling writes)
1. Whether the **version path segment** must be set explicitly (the app can add
   `/vLatest` if required; see `constants.MAINTENANCE_API_PATH`).
2. **Recurring maintenance windows / pause durations** may become GA and change
   default payloads or list filtering (feature flag
   `itsi-si-recurring-maintenance-windows`). v1 ignores these.
3. Any change to **create/update response shape** (v1 tolerates `{"_key":...}`,
   a full object, or a list; `_extract_key` handles all three).
4. Any change to **delete semantics** (v1 handles 200/201/**204**).
5. New required or renamed **server-managed fields** (v1 strips a known set on
   edit; add to `_READONLY_FIELDS` if 5.x adds more).
6. RBAC/team model changes affecting which capability/team is required.

## How to validate on a live ITSI 5.x instance
Run the same suite in `VALIDATION_REPORT.md` (discovery → baseline → dry-run →
CRUD → idempotency → authz → errors) and record the exact 5.x release. The
injectable transport in `imw.client`/`imw.idempotency` lets the provided
integration harness run against 5.x with only credentials changed.
