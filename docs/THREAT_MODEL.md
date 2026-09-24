# Threat Model

## Assets
- The ephemeral splunkd **session key** delivered to the alert action.
- ITSI maintenance state (windows that suppress alerting/notable events).
- Audit records.

## Trust boundaries
- Search results are **untrusted input** (they may be produced by any search the
  saved-search owner can run).
- The alert action runs inside splunkd with the owner's authorization.
- ITSI enforces its own capabilities and RBAC at the REST layer.

## Principal risks & mitigations

| Risk | Mitigation |
|---|---|
| Result rows injecting a malicious endpoint/host/URL | Endpoint, scheme, host, port and paths are **fixed constants** in `constants.py`; row data can never set them. Object keys are allow-listed (`[A-Za-z0-9._:-]`) and path-encoded. |
| Code/SPL/template injection via fields | Field values are treated strictly as data; nothing is `eval`/`exec`/templated/imported/shelled. |
| Session key leakage | Kept in memory only; never logged, indexed, returned, placed in URLs, or included in audit/debug output. `audit.py` scrubs sensitive keys defensively. |
| Credential theft | No username/password/permanent token stored or accepted. |
| TLS downgrade / MITM | Uses `splunk.rest` against the runtime mgmt URI; TLS verification is **never** disabled. |
| Privilege escalation | Runs with the caller's authorization; ITSI enforces `read/write/delete_maintenance_calendar` + object RBAC. Custom capabilities gate who may run the action. |
| Duplicate/replayed dispatch | Idempotency via app-owned KV Store keyed on `request_id` + payload hash; duplicate = no-op, changed payload = rejected. |
| Uncertain write (timeout after submit) | Marked `reconciliation_required`; the next run reconciles via GET/list before any re-create. Non-idempotent creates are never blindly retried. |
| Destructive delete | Disabled by default; separate capability; completed windows expire naturally. |
| Direct KV Store tampering with ITSI config | The app never writes ITSI KV Store or imports private ITSI modules; only the supported REST interface is used. |
| Denial of service via huge inputs | Bounded `max_rows`, `max_objects`, duration/horizon limits. |

## Out of scope
- Protecting against a fully-compromised Splunk admin (they can already change
  ITSI).
- Network controls between splunkd and ITSI (same host / platform-managed).
