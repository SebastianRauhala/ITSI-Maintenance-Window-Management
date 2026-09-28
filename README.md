# ITSI Maintenance Window Management

Create, inspect, update, cancel and (optionally) delete **ITSI maintenance
windows** (`maintenance_calendar` objects) from scheduled or ad hoc saved
searches, via a **modular alert action** that calls the **supported ITSI REST
API** on local splunkd.

- App ID: `itsi_maintenance_window_management`
- Primary target: Splunk Enterprise / Splunk Cloud with **ITSI 4.22**
  (developed and **live-validated on ITSI 4.21.3**; see limitations).
- Secondary target: **ITSI 5.x** — documentation-reviewed, live validation pending.

> **Safety first.** Writes are **dry-run by default** and destructive **delete is
> disabled by default**. Nothing is created or changed until you explicitly turn
> dry-run off.

---

## Two interfaces (same validated engine)

| Interface | Best for | How |
|---|---|---|
| **`itsimaintenance` custom command** (primary) | **Interactive** use — run a search and see per-row success/failure inline | `... \| itsimaintenance` |
| `itsi_maintenance_action` alert action | **Scheduled / unattended** automation with logged audit trail | Saved-search alert action |

Both call the same strictly-validated, idempotent engine, so behavior is
identical. The custom command is `chunked=true` with `run_in_preview=false`, so it
**does not fire during search preview** — combined with idempotency it is safe
for write operations.

### Quick start (custom command)
```spl
| makeresults | eval operation="list", request_id="ui-1" | itsimaintenance
```
```spl
| makeresults
| eval operation="create", request_id="CHG123",
       title="CHG123 - planned maintenance",
       object_key="<ENTITY_OR_SERVICE_KEY>", object_type="entity",
       start_time="1800000000", end_time="1800003600"
| itsimaintenance dry_run=false
```
Open the app to land on the **ITSI Maintenance Window Management - Home** dashboard,
which documents usage and shows current windows live.

---

## How it works

```
Saved search  ->  modular alert action (itsi_maintenance_action)
              ->  parse & validate result rows (strict)
              ->  authorize (runtime session key + ITSI capabilities)
              ->  idempotency check (app-owned KV Store)
              ->  runtime splunkd mgmt URI + ephemeral session key
              ->  ITSI maintenance_services_interface REST (create/list/update/cancel/delete)
              ->  reconcile response
              ->  sanitized audit record
              ->  clear success / failure exit code
```

The **`itsimaintenance` custom command** follows the identical flow but is driven
by an interactive search: it reads the piped rows, runs the same engine, and
emits one result row per request (with `result`, `error_category`,
`maintenance_window_keys`, ...). It obtains the session key and management URI
from the search context (`searchinfo`), runs only on the search head
(`local=true`), and never executes during preview (`run_in_preview=false`).

The **validated** ITSI REST contract (ITSI 4.21.3) is documented in
[`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). The endpoint is
`/servicesNS/nobody/SA-ITOA/maintenance_services_interface/maintenance_calendar`
(owner `nobody` is mandatory).

## Input contract (result rows)

Each row is a record. Required for **every** row: `operation`, `request_id`.

| Field | Required for | Notes |
|---|---|---|
| `operation` | all | one of `validate,list,create,update,cancel,delete` (subject to allow-list) |
| `request_id` | all | idempotency key; letters/digits/`. _ : -` and spaces, 1–128 chars (tab/newline not allowed). Stored internally under a hashed KV key. |
| `title` | create/update | globally unique in ITSI |
| `object_key` | create/update | opaque ITSI entity/service `_key`. May be a **list** (comma/whitespace-separated, or a multivalue field) to include many objects in one row. |
| `object_type` | create/update | `entity` or `service`. A single value applies to all `object_key`s in the row; or supply a matching-length list (one type per key). |
| `start_time` | create/update | UTC epoch seconds (or ISO-8601 with `Z`/offset) |
| `end_time` | create/update | must be > start_time |
| `maintenance_window_key` | update/cancel/delete | opaque ITSI window `_key` |
| `comment`, `group_id`, `change_id`, `requested_by`, `dry_run` | optional | |

Rows sharing a `request_id` are **grouped** into one logical request; window
attributes must match across the group. A group containing **both** entities and
services is **auto-split** into one entity window and one service window (ITSI
does not support mixed windows), each given a distinct title.

See [`docs/SAVED_SEARCH_EXAMPLES.md`](docs/SAVED_SEARCH_EXAMPLES.md).

## Install

See [`docs/INSTALL.md`](docs/INSTALL.md). In short: install the app, restart
splunkd (registers the alert action, capabilities and KV Store collection),
grant the capabilities to a least-privilege role, and keep dry-run on until you
have validated your environment.

## Safety controls (alert action params)

Configured in `default/alert_actions.conf` or per saved search via
`action.itsi_maintenance_action.param.<name>`:

`default_dry_run`, `enable_delete`, `allow_cancel_active`,
`allow_modify_completed`, `require_change_id`, `auto_split_mixed`,
`max_rows_per_invocation`, `max_objects_per_window`, `max_duration_seconds`,
`max_future_horizon_seconds`, `min_lead_seconds`, `allowed_operations`,
`allowed_object_types`, `required_title_prefix`, `protected_object_keys`,
`object_resolve_batch_size`, `summary_index`.

On Splunk Cloud, the command's settings are editable from the **Set up** page
(no backend access needed); the alert action's parameters are editable in the
alert configuration UI.

## Entities and services

Both ITSI object types are supported and validated:

- **Entities** and **services** can each be placed into a maintenance window
  (`object_type = entity | service`).
- A window is **one object type** (ITSI does not support mixed windows). A single
  request that lists **both** entities and services is **auto-split** into one
  entity window and one service window (distinct titles), sharing the same
  `request_id`.
- `create`, `update` (full replace), `cancel`, and `delete` all work identically
  for service and entity windows.

## Scale & performance

Object existence is verified in **batched** REST calls
(`object_resolve_batch_size`, default 200), not one call per object. Measured on
a 3081‑entity ITSI 4.21.3 instance:

| Window size | Create time |
|---|---|
| 1,000 objects | ~3 s |
| 2,000 objects | ~7 s |
| 3,000 objects | ~8.5 s |

Guidance for large maintenance runs:

- Default limits: `max_objects_per_window` = **5000**, `max_rows_per_invocation`
  = **5000** (tune via Set up / conf). One window ≤ 5000 objects is the sweet
  spot; beyond that, split by service/site.
- Prefer the **single‑row multi‑key** form — collapse keys with
  `| stats values(object_key) as object_key | eval object_key=mvjoin(object_key,",")`
  — so the whole request is one row (avoids per‑row overhead and multi‑chunk
  handling).

## Security

- Uses only the **ephemeral runtime session key** (in memory only) against the
  **runtime management URI**. No stored credentials/tokens; nothing hard-coded
  (host/port/URL). See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).
- **Never** modifies ITSI KV Store directly and never imports private ITSI
  modules. All changes go through the supported ITSI REST interface.
- No `subprocess`/`os.system`/shell/`curl`; TLS verification is never disabled.
- Endpoint/security constants are fixed in code and cannot be overridden by
  search results or configuration.

## Documentation

- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — validated ITSI 4.21.3 contract
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture & data flow
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — threat model
- [`docs/ROLES.md`](docs/ROLES.md) — roles & capabilities
- [`docs/INSTALL.md`](docs/INSTALL.md) — install / upgrade / uninstall / cleanup
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — dry-run, live demo, rollback
- [`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md) — test matrix & evidence
- [`docs/ITSI5_COMPAT.md`](docs/ITSI5_COMPAT.md) — ITSI 5.x compatibility analysis
- [`docs/APPINSPECT.md`](docs/APPINSPECT.md) — AppInspect command & remediation
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md)

## Tests

```
python3 -m unittest discover -s tests/unit -p "test_*.py"
python3 -m unittest discover -s tests/integration -p "test_*.py"
```

## Author, support & license

- **Author:** Sebastian Rauhala &lt;serauhal@cisco.com&gt;
- **Built with generative AI** (human-reviewed). See `docs/VALIDATION_REPORT.md`.
- **Developer-supported, no warranty.** Provided "AS IS" with no guarantees of
  fitness, availability, or support. Validate in a non-production environment
  first. See [`NOTICE`](NOTICE) for the full disclaimer.
- **Trademarks:** Splunk and Splunk IT Service Intelligence (ITSI) are trademarks
  of Splunk LLC, a Cisco company. This is an independent project and is **not** an
  official Splunk or Cisco product, nor endorsed by them.
- **License:** Apache-2.0 — see [`LICENSE`](LICENSE),
  [`NOTICE`](NOTICE) and [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)
  (bundles the Apache-2.0 Splunk SDK for Python).
