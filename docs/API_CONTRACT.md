# Validated ITSI maintenance_calendar REST Contract

**Evidence legend:** `[SRC]` confirmed by reading installed ITSI 4.21.3 source ·
`[LIVE]` confirmed by live call on Splunk 10.2.4 / ITSI 4.21.3 · `[DOC]`
documented.

## Environment where this was validated
- Splunk Enterprise **10.2.4** (single instance). `[LIVE]`
- ITSI **4.21.3** (`itsi` and `SA-ITOA` apps). `[LIVE]`
- Handlers run under Python **3.9** (`restmap.conf: python.version = python3.9`). `[SRC]`

> The task's primary target is ITSI 4.22. This environment is 4.21.3, so all
> live results are labelled for 4.21.3. 4.22 is expected to be identical (same
> `maintenance_services` package) but is **not** claimed as live-validated.

## Endpoint

```
/servicesNS/nobody/SA-ITOA/maintenance_services_interface/maintenance_calendar
```
- Owner **must** be `nobody` — the provider rejects any other owner
  (`"Maintenance objects can only exist at app level (owner=\"nobody\")"`). `[SRC]`
- An optional version path segment is accepted:
  `/maintenance_services_interface/vLatest/maintenance_calendar` or
  `/v<itsi_version>/...`. The app uses the unversioned path. `[SRC]`
- The task's candidate `/itoa_interface/maintenance_calendar` is **wrong** — it
  returns HTTP 404. `[LIVE]`

## CRUD operations

| Operation | Method + Path | Success | Notes |
|---|---|---|---|
| List | `GET .../maintenance_calendar` | 200, JSON array | RBAC-filtered `[SRC][LIVE]` |
| Read one | `GET .../maintenance_calendar/<key>` | 200, JSON object | 404 if missing `[LIVE]` |
| Count | `GET .../maintenance_calendar/count` | 200, `{"count":N}` | `[SRC]` |
| Create | `POST .../maintenance_calendar` | 200, `{"_key":"..."}` | body form field `data` `[LIVE]` |
| Update | `PUT .../maintenance_calendar/<key>` | 200, `{"_key":"..."}` | full replace (`op.edit`) `[SRC][LIVE]` |
| Delete | `DELETE .../maintenance_calendar/<key>` | **204 No Content** | `[LIVE]` |

Native ITSI capabilities enforced by the handler: `read_maintenance_calendar`
(GET), `write_maintenance_calendar` (POST/PUT), `delete_maintenance_calendar`
(DELETE). `[SRC]`

## Request encoding

- Content-Type `application/x-www-form-urlencoded`. `[SRC]`
- Body carries a single field **`data`** whose value is a **JSON string** of the
  window object (`passPayload=true`; provider reads `kwargs.get('data')`). `[SRC][LIVE]`
- `_key` is carried in the **URL path** for read/update/delete; never in the
  collection POST body. `[SRC][LIVE]`

## Object schema (create/update payload)

```json
{
  "title": "CHG0001234 - Planned maintenance",
  "comment": "optional",
  "objects": [ { "_key": "<entity-or-service _key>", "object_type": "entity" } ],
  "start_time": 1789644679,
  "end_time":   1789648279
}
```

- `start_time`/`end_time` are **UTC epoch seconds** (numeric; float-coercible).
  Not ISO-8601, not milliseconds. ITSI validates `start_time < end_time`. `[SRC][LIVE]`
- `objects` is a non-empty list; each element must be **exactly**
  `{"_key","object_type"}` with `object_type` in `{entity, service}`. `[SRC]`
- **A window must be a single object type** (all entities or all services). ITSI
  RBAC inspects only `objects[0]`; mixing is unsupported. The app auto-splits. `[SRC]`
- **Titles must be globally unique.** Creating a second window with an existing
  title returns **HTTP 409** `"Duplicate object name(s) found: <title>"`. The app
  disambiguates auto-split titles with a `[entity]`/`[service]` suffix. `[LIVE]`

## GET response — server-managed (read-only) fields

Observed on a live GET (do **not** send these on create/update; ITSI recomputes):
`object_type`, `mod_source`, `mod_timestamp`, `_version` (e.g. `4.21.3`),
`identifying_name`, `sec_grp_list`, `_user` (`nobody`), `can_edit`, `_key`. `[LIVE]`

Example live GET response:
```json
{
  "title": "MW-AUTO-BASELINE - UI-created test",
  "comment": "baseline schema capture",
  "objects": [ { "_key": "4094bf26-...-062e93da2804", "object_type": "entity" } ],
  "start_time": 1789644679,
  "end_time": 1789648279,
  "mod_source": "unknown",
  "object_type": "maintenance_calendar",
  "mod_timestamp": "2026-09-17T10:31:20.755414+00:00",
  "_version": "4.21.3",
  "identifying_name": "mw-auto-baseline - ui-created test",
  "sec_grp_list": ["default_itsi_security_group"],
  "_user": "nobody",
  "_key": "6aabc179f2dd8ec1e0062d73",
  "can_edit": true
}
```

## Error responses

JSON body with a `message` field, e.g. `{"message": "Duplicate object name(s)
found: DUPTEST. Please rename the object(s) before proceeding."}`. HTTP status
carries the category (400/401/403/404/409/429/5xx). `[LIVE]`

## Cancel vs delete semantics (app policy, validated)

- **Cancel** = read-modify-write PUT that ends the window now
  (active → `end_time=now`; future → collapse to the past
  `start=now-1, end=now`), preserving `start_time < end_time`. `[LIVE]`
- **Delete** is a hard removal (HTTP 204), disabled by default. A window with a
  valid `end_time` expires naturally; delete is not the normal expiry path. `[LIVE]`

## Additional fields present in 4.21.x (out of scope for v1)

`recurrence_options` (+ `time_zone`, `adjusted_start_date`), `pause_durations`.
Recurring windows are gated behind the `itsi-si-recurring-maintenance-windows`
feature flag. `[SRC]`
