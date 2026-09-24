# Saved-search Examples

> Replace `<ENTITY_KEY>` / `<SERVICE_KEY>` with real ITSI object `_key`s and
> `<UTC_START>` / `<UTC_END>` with epoch seconds (or ISO-8601 with `Z`/offset).
> Keep `dry_run="true"` until validated.

## 1. Dry-run create (entity + service, auto-split into two windows)
```spl
| makeresults
| eval operation="create", request_id="MW-DEMO-001", group_id="MW-DEMO-001",
       change_id="CHG-DEMO-001", requested_by="itsi-maintenance-test",
       title="CHG-DEMO-001 - ITSI maintenance automation test",
       comment="Temporary live validation window",
       object_key="<ENTITY_KEY>", object_type="entity",
       start_time="<UTC_START>", end_time="<UTC_END>", dry_run="true"
| append [
    | makeresults
    | eval operation="create", request_id="MW-DEMO-001", group_id="MW-DEMO-001",
           change_id="CHG-DEMO-001", requested_by="itsi-maintenance-test",
           title="CHG-DEMO-001 - ITSI maintenance automation test",
           comment="Temporary live validation window",
           object_key="<SERVICE_KEY>", object_type="service",
           start_time="<UTC_START>", end_time="<UTC_END>", dry_run="true" ]
| fields operation request_id group_id change_id requested_by title comment
         object_key object_type start_time end_time dry_run
```
Attach the alert action: **Save As → Alert → Add Actions → ITSI Maintenance
Automation**. Keep the action param `default_dry_run = true`.

## 2. List current windows
```spl
| makeresults | eval operation="list", request_id="MW-LIST-001"
```

## 3. Cancel a window
```spl
| makeresults
| eval operation="cancel", request_id="MW-CANCEL-001",
       maintenance_window_key="<WINDOW_KEY>", dry_run="false"
```

## 4. Delete a window (only if delete is enabled)
```spl
| makeresults
| eval operation="delete", request_id="MW-DELETE-001",
       maintenance_window_key="<WINDOW_KEY>", dry_run="false"
```

## 5. Update a window (full replace — resupply ALL objects)
```spl
| makeresults
| eval operation="update", request_id="CHG123-update-1",
       maintenance_window_key="<WINDOW_KEY>",
       title="CHG123 - planned maintenance",
       object_key="<ENTITY_OR_SERVICE_KEY>", object_type="entity",
       start_time="<EPOCH_START>", end_time="<EPOCH_END_NEW>",
       dry_run="true"
| itsimaintenance
```
Update replaces the whole window, so include every object that should remain
(one row per object, all sharing the same `request_id` / `maintenance_window_key`
/ `title` / `start_time` / `end_time`). Works on active/future windows only.

## 6. Report: entities currently in maintenance
Use the ITSI runtime lookup `operative_maintenance_log` (authoritative). The
entity `in_maintenance` flag is unreliable, so do not depend on it.
```spl
| inputlookup operative_maintenance_log
| where maintenance_object_type="entity" AND start_time<=now() AND end_time>=now()
| rename maintenance_object_key as entity_key
| lookup itsi_entities _key as entity_key OUTPUT title as entity_title
| table entity_key entity_title start_time end_time calendar_origin
```
`calendar_origin` is the maintenance window `_key`. Swap `entity` → `service` for
services.

## 7. Automation: put entities into maintenance, skipping those already covered
Anti-join your candidate entities against the active `operative_maintenance_log`,
then pipe the survivors to the command (start in dry-run). Replace the candidate
source with your own list/asset search.
```spl
``` candidate entities that SHOULD be in maintenance (example: all entities) ```
| inputlookup itsi_entities
| fields _key title
| rename _key as object_key
| eval object_type="entity"

``` drop entities that already have an ACTIVE maintenance window ```
| search NOT
    [ | inputlookup operative_maintenance_log
      | where maintenance_object_type="entity" AND end_time>=now()
      | rename maintenance_object_key as object_key
      | fields object_key ]

``` build one grouped window for the remaining entities ```
| eval operation="create",
       request_id="MAINT-DAILY-" . strftime(now(),"%Y%m%d"),
       group_id=request_id,
       title="Planned maintenance " . strftime(now(),"%Y-%m-%d"),
       start_time=tostring(now()), end_time=tostring(now()+3600),
       dry_run="true"
| table operation request_id group_id title object_key object_type start_time end_time dry_run
| itsimaintenance
```
Flip to `| itsimaintenance dry_run=false` once the plan looks right. For a
window per entity instead, set a unique `request_id` **and** unique `title` per
entity (ITSI enforces unique titles). Mind `max_objects_per_window` for grouped
windows.

## Notes
- `request_id` is the idempotency key. Reusing it with the **same** payload is a
  safe no-op; reusing it with **different** data is rejected.
- For scheduled use, set `enableSched = 1` and a cron schedule, and ensure the
  saved search is owned by a least-privilege service account (see `ROLES.md`).
- The example saved searches shipped in `default/savedsearches.conf` are
  **disabled** and use dry-run.
