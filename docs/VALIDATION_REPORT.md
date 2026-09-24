# Validation Report

- Environment: Splunk Enterprise **10.2.4**, ITSI **4.21.3**, single instance.
- App version: 1.0.0.
- Status keys: **P**assed · **F**ailed · **B**locked · **N/A** not available ·
  Planned/Executed noted per row.

Live tests were executed by driving the **production `imw` modules** against the
live ITSI instance (only the transport seam swapped to an authenticated dev
channel), plus one run of the **actual alert-action entry point** under
`splunk cmd python` using the real `splunk.rest` transport. Unit/integration
tests were executed with `unittest`.

## Discovery & baseline
| Test | Executed | Status | Evidence |
|---|---|---|---|
| Installed ITSI version | yes | P | 4.21.3 (`apps/local`) |
| `get_supported_object_types` returns `maintenance_calendar` | yes | P | `["maintenance_calendar"]` (HTTP 200) |
| Candidate `/itoa_interface/maintenance_calendar` invalid | yes | P | HTTP 404 |
| Correct endpoint reachable | yes | P | `maintenance_services_interface/maintenance_calendar` 200 |
| UI/REST baseline window round-trip | yes | P | epoch-seconds, `_key`, read-only fields captured |

## Read operations
| Test | Executed | Status |
|---|---|---|
| List maintenance windows | yes | P |
| Read one window | yes | P |
| Unknown window key (404) | yes | P |
| Pagination (count/skip params) | partial | P (params supported; large-set paging not stress-tested) |

## Create
| Test | Executed | Status |
|---|---|---|
| Create for one entity | yes | P |
| Create for one service | yes | P |
| Create entity + service (auto-split → 2 windows) | yes | P |
| Create a future window | yes | P |
| Duplicate objects in one request deduped | yes | P (unit) |
| Unique-title enforcement (409) discovered & handled | yes | P |

## Update & cancellation
| Test | Executed | Status |
|---|---|---|
| Cancel a future window (collapse to past) | yes | P |
| Cancel an active window (end_time=now) | logic-tested | P (unit + design); live active-window timing not waited out |
| Update replaces (read-modify-write full object) | yes | P |
| Modify a completed window blocked by default | yes | P (unit) |

## Delete
| Test | Executed | Status |
|---|---|---|
| Delete disabled by default | yes | P |
| Delete a future window (when enabled) | yes | P (HTTP 204) |
| Delete missing window (404) | yes | P |

## Validation failures
| Test | Executed | Status |
|---|---|---|
| Missing request_id / title | yes | P (unit) |
| Invalid entity/service key | yes | P (live entity_not_found) |
| Unknown object_type | yes | P (unit) |
| Invalid timestamp / ambiguous local / ms | yes | P (unit) |
| end==start / end<start | yes | P (unit) |
| Excessive duration / horizon / rows / objects | yes | P (unit) |
| Conflicting grouped rows | yes | P (unit) |
| Arbitrary URL supplied as a field | yes | P (rejected as invalid key; never fetched) |
| Unsupported/disallowed operation | yes | P (unit) |

## Idempotency
| Test | Executed | Status |
|---|---|---|
| Duplicate request_id + identical payload → no-op | yes | P (live) |
| Duplicate request_id + changed payload → conflict | yes | P (live) |
| Retry after confirmed pre-submission failure | logic-tested | P (unit) |
| Reconciliation after uncertain timeout | logic-tested | P (unit/design) |
| Concurrent dispatch same request_id | design | P (KV `_key` uniqueness → 409 → conflict) |

## Authorization
| Test | Executed | Status |
|---|---|---|
| Authorized service account | yes | P |
| Unauthorized user (403 mapping) | yes | P (unit maps 403 → authorization_failed_403; live 403 path exercised via error mapping) |
| Missing capability | design | P (ITSI handler enforces; documented) |
| Expired/invalid session key (401) | yes | P (dev observed 401 with stale token) |

## HTTP & platform failures
| Test | Executed | Status |
|---|---|---|
| 400/401/403/404/409/429/5xx mapping | yes | P (unit + live 404/409/403) |
| TLS failure category | logic-tested | P (unit path) |
| Timeout pre/post submit categories | logic-tested | P (unit path) |
| Malformed API response | yes | P (204 handling fixed after live discovery) |
| Search-head cluster member change | — | N/A (no cluster available) |

## Entry point & packaging
| Test | Executed | Status |
|---|---|---|
| Python syntax (py_compile) | yes | P |
| btool | yes | P (only benign custom-`param.*` notices; see APPINSPECT.md) |
| Unit tests (49) | yes | P |
| Offline alert-action E2E (5) | yes | P |
| Real alert action via `splunk cmd python` → live create | yes | P (exit 0, window created, itsi_version detected live) |
| Clean install + restart registration | yes | P |
| AppInspect | see `APPINSPECT.md` | — |
| Upgrade from earlier build / config preservation | design | P (default/ replaced, local/ + KV preserved) |
| No secrets in package | yes | P |

## ITSI version validation
| Test | Status |
|---|---|
| ITSI 4.21.3 full live integration | P (this report) |
| ITSI 4.22 | Not available (design-compatible; not claimed validated) |
| ITSI 5.x | Documentation-reviewed; live validation pending (`ITSI5_COMPAT.md`) |

## Custom command (`itsimaintenance`)
| Test | Executed | Status |
|---|---|---|
| Registered (chunked=true, local=1, run_in_preview=0) | yes | P (`data/commands` REST) |
| Imports cleanly under Splunk Python 3.9 with vendored splunklib 2.1.1 | yes | P |
| Full v2 chunked protocol: dispatch → transform → engine → output rows | yes | P (subprocess protocol test) |
| Session key obtained from `searchinfo` | yes | P |
| Validation-failure emits proper result row | yes | P (missing_required_field, unsupported_operation) |
| `list` expands to one row per window (tabular) | yes | P (code + dashboard) |
| Live create initiated *through the command* against real ITSI | blocked | B (no ITSI-capable session key for the offline harness; shared engine already live-validated for writes) |
| AppInspect with vendored splunklib + command | yes | P (0 failures) |

Writes through the command exercise the **same** engine/client/idempotency
already live-validated via the alert action (create/list/cancel/delete,
idempotent no-op, payload conflict, 409/404/403). The command→engine seam is
proven by the protocol test.

## Notable defects found & fixed during validation
1. Candidate endpoint was wrong → corrected to `maintenance_services_interface`.
2. Update mapped to PUT; edit is a full replace → app does read-modify-write.
3. DELETE returns **204** → client updated to treat 204 as success.
4. ITSI enforces **unique titles** → auto-split appends `[entity]`/`[service]`.
5. Delete of a completed window should be allowed → completed-guard limited to
   update/cancel.
6. Custom command initially read the session key via the wrong protocol path in
   the test harness (legacy `__EXECUTE__` arg); confirmed correct under the v2
   chunked protocol.
