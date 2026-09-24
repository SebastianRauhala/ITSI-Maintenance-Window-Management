# Roles & Capabilities

## Capabilities defined by this app (`authorize.conf`)
- `manage_itsi_maintenance_windows`
- `read_itsi_maintenance_windows`
- `create_itsi_maintenance_windows`
- `update_itsi_maintenance_windows`
- `delete_itsi_maintenance_windows`

These gate **who may own/run** the saved searches that invoke the alert action.
They are app-level authorization; they do **not** replace ITSI's own checks.

## Native ITSI capabilities enforced at the REST layer
The ITSI handler checks these against the **runtime session key**:
- `read_maintenance_calendar` (GET)
- `write_maintenance_calendar` (POST/PUT)
- `delete_maintenance_calendar` (DELETE)

Additionally, ITSI object **RBAC** requires the caller to have `write`
permission on each **service** in a window; entities use the Global/default
security group. Unauthorized access returns **HTTP 403**.

## Least-privilege service account (recommended)
1. Create a dedicated service account (e.g. `svc-itsi-maint`).
2. Create a role, e.g. `itsi_maintenance_manager` (shipped example), granting:
   - `manage_/read_/create_/update_itsi_maintenance_windows` (this app),
   - `read_maintenance_calendar`, `write_maintenance_calendar` (ITSI),
   - membership in the ITSI team(s) that own the target services with **write**,
   - `schedule_search` and the ability to run the scheduled saved search.
3. **Do not** grant `delete_maintenance_calendar` or
   `delete_itsi_maintenance_windows` unless deletion is genuinely required.
4. Own the scheduled saved searches with this account; restrict who may edit
   them (write permission on the saved search) and who may run the alert action.

## Admin is NOT required
Live validation shows create/update/cancel/delete succeed with the native
`read/write/delete_maintenance_calendar` capabilities plus team write access; no
`admin` role is required. If a future ITSI release requires more, document the
exact capability gap before granting it.

## Verifying authorization failures
Run the app as a user lacking `write_maintenance_calendar` (or lacking team
write): the operation returns a controlled failure with
`error_category=authorization_failed_403` and no change is made.
