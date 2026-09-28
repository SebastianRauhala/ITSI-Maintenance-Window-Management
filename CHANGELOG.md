# Changelog

All notable changes to **ITSI Maintenance Window Management** are documented here.
This project adheres to semantic versioning.

## [1.3.1] - 2026-09-28

### Fixed
- Removed `check_for_updates = 0` from `app.conf [package]` — Splunkbase
  vetting requires update checks to remain enabled for published apps.

## [1.3.0] - 2026-09-28

### Changed
- **Batched object resolution (major performance fix).** Verifying entity/service
  existence previously did **one REST GET per object** (~0.5s each), so a
  1000-object window spent ~8 minutes and a 3000-object window ~24 minutes just
  resolving — often exceeding search/command runtime. Resolution is now **batched**
  (`filter={"_key":{"$in":[…]}}`, ~200 keys per call). Measured live on 3081
  entities: a **1000-object create dropped from ~8 min to ~3 seconds**
  (50: 25s→1.5s, 150: 68s→1.7s). Missing keys still raise a precise
  `entity_not_found`/`service_not_found` listing the offenders.
- **Raised default limits:** `max_objects_per_window` 1000 → **5000**;
  `max_rows_per_invocation` 2000 → **5000** (ITSI handles 5000-object windows;
  a 1000-object create POST measured ~0.7s).

### Added
- Config `object_resolve_batch_size` (default 200) to tune the resolution batch
  size (keep it small enough to stay within REST URL-length limits).

## [1.2.1] - 2026-09-28

### Fixed
- **Custom command now accumulates rows across chunks and runs once.** Splunk can
  deliver a command's input in multiple chunks; the command previously processed
  each chunk independently, so a large `update` (a full replace) executed once
  per chunk and the last chunk overwrote the earlier objects — only a subset
  persisted, and duplicate result rows appeared for the same `request_id`. The
  command now waits for the final chunk (`self._finished`) before acting.
  (The alert action reads all results at once and was not affected.)

## [1.2.0] - 2026-09-28

### Added
- **Multiple object keys per row.** `object_key` (and `object_type`) may now be a
  **comma/whitespace-separated list** or a **multivalue field**, so a single
  result row can carry many entities/services (e.g.
  `object_key="k1,k2,k3", object_type="entity"`). A single `object_type` applies
  to all keys; a matching-length list assigns a type per key. This fixes
  `object_key has invalid characters or length` when passing many keys at once,
  and avoids splitting a large update across many rows.

## [1.1.1] - 2026-09-24

### Added
- **`static/appLogo.png` and `static/appLogo_2x.png`** so the app icon renders in
  the in-app navigation bar (Splunk looks for `appLogo.png` there; its absence
  produced a "No static asset … appLogo.png" warning). The launcher tile icon
  (`appIcon*`) was already present.

## [1.1.0] - 2026-09-24

### Changed
- **Renamed** the app to **ITSI Maintenance Window Management**
  (app id `itsi_maintenance_window_management`). The custom command
  (`itsimaintenance`) and alert action (`itsi_maintenance_action`) names are
  unchanged.
- **Author / license:** set author to Sebastian Rauhala; personal copyright;
  added `NOTICE` with a GenAI-built transparency note, a developer-supported /
  no-warranty disclaimer, and a Splunk/ITSI trademark acknowledgment.
- **Delete is now a single switch:** `enable_delete=true` alone enables the
  delete operation (no need to also add it to `allowed_operations`). ITSI's
  `delete_maintenance_calendar` capability remains the ultimate gate.
- **Simplified capabilities:** removed the never-enforced granular
  `read/create/update/delete_itsi_maintenance_windows`; kept a single
  `manage_itsi_maintenance_windows` (groups app admin + gates the KV state
  collection). Real enforcement is ITSI native capabilities + object RBAC.
- **Raised limits:** `max_objects_per_window` 100 → **1000**;
  `max_rows_per_invocation` 500 → **2000**; `max_duration_seconds` 7d → **90d**.
- **Reconciliation now scales** to any number of windows: `_reconcile_find`
  filters server-side by the (unique) title and only pages the full collection
  if the API ignores the filter (previously scanned just the first 500).
- Dashboard times now render in the **user's timezone** (`%Z`) instead of a
  hard-coded "UTC" label.

### Added
- **`request_id` now allows spaces** (still rejects tab/newline; 1–128 chars).
  Idempotency state is stored under a hashed, KV-safe `_key`, with the human
  `request_id` kept as a field.
- **Home dashboard** panels: update-window example + semantics, cancel vs delete
  guidance, scheduled alert-action guidance, an Authentication & privileges
  panel, a live "entities currently in maintenance" table, and a
  **Troubleshooting & logs** panel.
- **Example searches** in `docs/SAVED_SEARCH_EXAMPLES.md`: entities currently in
  maintenance (via `operative_maintenance_log`), a candidates-needing-maintenance
  anti-join, and an update example.
- **App icons** (`static/appIcon*`, `appserver/static/appIcon.png`).
- **Splunk-Web Set up page** (HTML/JS setup view) to edit the command's
  `[safety]` settings from the browser, including on **Splunk Cloud** (writes to
  `itsi_maintenance.conf [safety]` via the Splunk Web proxy). Registered via
  `app.conf [ui] setup_view` and a nav tab.

### Notes
- A classic `setup.xml` is **not permitted on Splunk Cloud** (fails AppInspect /
  misbehaves with SHC); the Set up page above uses the supported HTML/JS
  approach instead.

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
