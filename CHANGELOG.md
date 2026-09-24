# Changelog

All notable changes to **ITSI Maintenance Window Management** are documented here.
This project adheres to semantic versioning.

## [1.1.0] - 2026-09-24

### Changed
- **Renamed** the app to **ITSI Maintenance Window Management**
  (app id `itsi_maintenance_window_management`). The custom command
  (`itsimaintenance`) and alert action (`itsi_maintenance_action`) names are
  unchanged.
- **Raised limits:** `max_objects_per_window` 100 → **1000**;
  `max_rows_per_invocation` 500 → **2000**.
- **Reconciliation now scales** to any number of windows: `_reconcile_find`
  filters server-side by the (unique) title and only pages the full collection
  if the API ignores the filter (previously scanned just the first 500).

### Added
- **`request_id` now allows spaces** (still rejects tab/newline; 1–128 chars).
  Idempotency state is stored under a hashed, KV-safe `_key`, with the human
  `request_id` kept as a field.
- **Home dashboard** panels: update-window example + semantics, cancel vs delete
  guidance, scheduled alert-action guidance, an Authentication & privileges
  panel, and a live "entities currently in maintenance" table.
- **Example searches** in `docs/SAVED_SEARCH_EXAMPLES.md`: entities currently in
  maintenance (via `operative_maintenance_log`), a candidates-needing-maintenance
  anti-join, and an update example.
- **App icons** (`static/appIcon*`, `appserver/static/appIcon.png`).

## [1.0.0] - 2026-09-17

### Added
- **`itsimaintenance` custom search command** (chunked v2 protocol,
  `run_in_preview=false`, `local=true`) as the primary interactive interface:
  run a search and see per-request results inline. Reuses the same validated,
  idempotent engine as the alert action. Vendored `splunklib` 2.1.1 (Apache-2.0).
- **Start/landing dashboard** ("ITSI Maintenance Window Management - Home") with usage
  documentation and a live panel listing current maintenance windows, plus app
  navigation and default-view wiring.
- `itsi_maintenance.conf [safety]` (+ spec) for command safety controls;
  `server.conf [shclustering]` conf replication; reload triggers for custom conf.
- Modular alert action `itsi_maintenance_action` to create, list, validate,
  update, cancel and (optionally) delete ITSI `maintenance_calendar` windows via
  the supported `maintenance_services_interface` REST API.
- Strict input validation, grouping by `request_id`, deduplication, and
  auto-split of mixed entity/service requests into separate windows (ITSI
  requires a single object type per window).
- Dry-run mode (enabled by default) that validates and builds payloads without
  writing.
- App-owned KV Store idempotency/state collection (`itsi_mw_automation_state`)
  with deterministic payload hashing, duplicate/no-op detection, payload-conflict
  rejection, and reconciliation after uncertain writes.
- UTC epoch-seconds timestamp validation (matches the ITSI storage contract);
  rejects ambiguous local timestamps and millisecond values.
- Configurable safety controls: max rows/objects/duration/horizon, min lead
  time, allowed operations/object types, required title prefix, required
  change_id, protected-object deny-list, delete toggle (off by default).
- Structured, sanitized audit logging that never records session keys,
  authorization headers, passwords or cookies.
- Custom capabilities and example least-privilege roles.
- Unit tests (49) and an offline end-to-end alert-action test.

### Validated (live, ITSI 4.21.3 / Splunk 10.2.4)
- Endpoint, CRUD verbs, epoch-seconds timestamps, create response `{"_key":...}`,
  DELETE returns HTTP 204, unique-title enforcement (HTTP 409), 404 handling,
  entity/service resolution, idempotent no-op and payload conflict, auto-split,
  cancel via read-modify-write, and execution under the real `splunk.rest`
  transport via the production entry point.

### Known limitations
- ITSI 5.x: documentation-reviewed only; live validation pending.
- Recurring maintenance windows and pause durations are out of scope in v1.
- Search-head clustering is designed-for but not live-validated (no cluster in
  the test environment).
