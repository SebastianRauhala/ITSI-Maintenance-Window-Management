# Architecture & Data Flow

## Components

| File | Responsibility |
|---|---|
| `bin/itsi_maintenance_action.py` | Modular alert-action entry point (`--execute`, stdin JSON, gzip results, exit codes). |
| `bin/itsimaintenance.py` | Interactive custom search command (chunked v2, EventingCommand) — same engine, inline results. |
| `bin/lib/splunklib/` | Vendored Splunk SDK for Python 2.1.1 (Apache-2.0), used only by the custom command. || `bin/imw/constants.py` | Fixed, non-overridable endpoint/security constants. |
| `bin/imw/config.py` | Parses bounded safety controls from alert params. |
| `bin/imw/validate.py` | Strict row parsing, grouping, dedup, auto-split, payload build. |
| `bin/imw/timeutil.py` | UTC epoch-seconds parsing/validation. |
| `bin/imw/client.py` | ITSI REST client over `splunk.rest.simpleRequest` (injectable transport). |
| `bin/imw/idempotency.py` | App-owned KV Store state + deterministic payload hashing. |
| `bin/imw/engine.py` | Orchestration per operation, reconciliation, error mapping. |
| `bin/imw/audit.py` | Structured, sanitized logging. |
| `bin/imw/version.py` | Best-effort ITSI version detection. |
| `bin/imw/errors.py` | Typed error categories. |

## Data flow

1. Splunk dispatches the saved search; the alert action receives a JSON payload
   on stdin containing `session_key`, `server_uri`, `results_file`,
   `configuration`, and search context.
2. `itsi_maintenance_action.py` reads the gzipped results into row dicts.
3. `Settings` builds bounded safety controls from `configuration`.
4. `Engine.run` calls `validate.normalize_and_group`:
   - normalize/sanitize each field (data only, never evaluated),
   - group by `request_id`, enforce identical window attributes,
   - dedup objects, enforce limits, validate timestamps,
   - build ITSI payloads (auto-split by object type).
5. Per group, the engine:
   - resolves entity/service `_key`s (read-only GET),
   - checks idempotency state (KV Store),
   - for writes: reserves `request_id`, reconciles, calls ITSI, records keys,
   - maps any failure to a typed category,
   - emits a sanitized audit record.
6. The entry point returns exit `0` (all success/no-op) or non-zero.

## State machine (per request_id)

`received → validating → validated → submitting → {succeeded | failed |
reconciliation_required}`; duplicates resolve to `succeeded` (no-op) or a
`payload_conflict` failure.

## Search-head clustering

State lives in the replicated KV Store collection `itsi_mw_automation_state`, so
idempotency is consistent across members. No local file is authoritative.
(Designed-for; not live-validated — no cluster in the test environment.)

## Diagram

```
+-------------+     stdin JSON      +---------------------------+
| splunkd     | ------------------> | itsi_maintenance_action   |
| (scheduler) |  session_key,uri    |  parse gzip results       |
+-------------+  results_file       +------------+--------------+
                                                 |
                                                 v
          +--------------------+   validate  +---------+  idempotency  +-----------------+
          | Settings (limits)  |----------->| Engine  |-------------->| KV Store state  |
          +--------------------+            +----+----+               | (app-owned)     |
                                                 |                    +-----------------+
                                                 v
                                    +----------------------------+
                                    | MaintenanceClient          |
                                    | splunk.rest.simpleRequest  |
                                    +-------------+--------------+
                                                  v
                        /servicesNS/nobody/SA-ITOA/maintenance_services_interface/
                                      maintenance_calendar (ITSI REST)
```
