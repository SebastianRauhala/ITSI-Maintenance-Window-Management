# Runbook: Dry-run, Live Demo, Rollback

## A. Dry-run procedure (do this first, in every new environment)
1. Create/identify a test entity and service; record their `_key`s
   (see `RRUNBOOK` step B1–B2).
2. Create a disabled saved search producing rows with `dry_run="true"`
   (see `SAVED_SEARCH_EXAMPLES.md`).
3. Run it. Confirm the audit log shows `result=success dry_run=True` with the
   planned `object_keys`, `title`, `start_time`, `end_time`, and
   `planned_window_count`. No window is created.
4. Try a deliberately bad key and confirm `entity_not_found`/`service_not_found`.

## B. Live demonstration (only after dry-run passes)
1. **Create the test entity** (ITSI UI: Configuration → Entities → Create), or
   via the supported REST API. Title `mw-auto-demo-entity`, alias `host =
   mw-auto-demo-host`. Record its `_key` from the entity REST API.
2. **Create the test service** (ITSI UI: Configuration → Services → Create).
   Title `mw-auto-demo-service`. Record its `_key`.
3. **Baseline**: create a short future window through the UI/REST, GET it back,
   and confirm the schema matches `API_CONTRACT.md` (epoch seconds, `_key`,
   read-only fields). Remove it.
4. **Dry-run** the app for the entity, the service, and both grouped.
5. **Enable create** (`param.default_dry_run = false` or `dry_run="false"` in
   rows). Submit one short future window. Record the returned window `_key`.
6. Confirm it appears in the ITSI **Maintenance Windows** UI and via `GET`.
7. At the scheduled time, confirm the objects enter maintenance and leave at
   `end_time`.
8. **Update/cancel**: create another future window, then cancel it (sets
   end_time to now / collapses future window to the past). Confirm via UI/API.
9. **Idempotency**: resubmit the same `request_id` + payload → no duplicate
   (`result=noop`). Resubmit same `request_id` with changed data →
   `payload_conflict`.
10. **Authorization**: run as a user lacking `write_maintenance_calendar` →
    `authorization_failed_403`, no change.
11. Verify audit records contain no session key/authorization header.

## C. Rollback
- To stop all automation immediately: disable the saved searches, or set
  `param.default_dry_run = true` in `local/alert_actions.conf` and reload.
- To remove created windows: run `list`, then `cancel` (preferred) or, if
  enabled, `delete` each test window. Never edit ITSI KV Store directly.

## D. Exit codes
- `0` all requests succeeded or were idempotent no-ops.
- `1` at least one request failed (see per-request `error_category`).
- `2` no session key / bad payload.
- `3` pre-flight validation failed for the invocation.
- `4` unexpected internal error (details in server log only).
