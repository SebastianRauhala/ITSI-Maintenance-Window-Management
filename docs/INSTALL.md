# Install / Upgrade / Uninstall / Cleanup

## Prerequisites
- Splunk Enterprise or Splunk Cloud with ITSI installed (validated on 4.21.3).
- The account installing/running has the required capabilities (see `ROLES.md`).

## Install (Splunk Enterprise)
1. Install the package:
   - UI: **Apps → Manage Apps → Install app from file** → upload the `.spl`.
   - CLI: `splunk install app itsi_maintenance_window_management-1.0.0.spl`
2. **Restart splunkd** (required to register the alert action, the custom
   capabilities, and the KV Store collection `itsi_mw_automation_state`).
3. Confirm registration:
   ```
   | rest /services/alerts/alert_actions | search title=itsi_maintenance_action
   | rest /servicesNS/nobody/itsi_maintenance_window_management/storage/collections/config
     | search title=itsi_mw_automation_state
   ```
4. Assign the capabilities/roles (see `ROLES.md`).
5. **Keep dry-run ON** until you validate your environment (see `RUNBOOK.md`).

## Install (Splunk Cloud)
- Upload as a **private app** for vetting. AppInspect + Cloud vetting must pass
  (see `APPINSPECT.md`). A restart is orchestrated by the Cloud platform.
- Passing local AppInspect does **not** guarantee Cloud approval.

## Configure customer-specific settings
- **Alert action (Splunk Web, incl. Splunk Cloud):** the action's parameters
  (including `enable_delete`) are editable in the alert configuration UI when you
  add the action to a saved search — no backend access needed. Enabling delete
  there is the single switch.
- **Custom command settings:** the command reads `itsi_maintenance.conf
  [safety]`. On self-managed Splunk, put overrides in
  `etc/apps/itsi_maintenance_window_management/local/` (never in `default/`):
  ```
  [safety]
  enable_delete = true
  required_title_prefix = CHG
  require_change_id = true
  ```
  On **Splunk Cloud** (no filesystem access), an admin can edit the same stanza
  via the REST endpoint
  `/servicesNS/nobody/itsi_maintenance_window_management/configs/conf-itsi_maintenance/safety`
  (e.g., via the Admin Config Service / a REST call). A Splunk-Web setup view is
  planned (classic `setup.xml` is not permitted on Splunk Cloud).

## Upgrade
1. Install the new `.spl` over the existing app (same ID).
2. Restart splunkd.
3. `default/` is replaced; your `local/` overrides and the KV Store state
   collection are preserved. Verify with the registration queries above.

## Uninstall
1. Disable/delete the saved searches that use the alert action.
2. Remove the app: `splunk remove app itsi_maintenance_window_management` (or delete
   `etc/apps/itsi_maintenance_window_management`), then restart splunkd.
3. The KV Store collection is removed with the app. ITSI maintenance windows
   created by the app are **not** removed by uninstalling — clean them up first
   if desired (see Cleanup).

## Cleanup / rollback of test data
1. List windows created by your test request IDs (operation `list`) and note
   their `_key`s.
2. Cancel or delete future/active test windows via the app or the ITSI UI/REST.
3. Remove the test service `mw-auto-demo-service` and entity
   `mw-auto-demo-entity` via the ITSI UI/REST.
4. Remove app-owned idempotency records:
   `| outputlookup` is **not** used; delete via
   `DELETE /servicesNS/nobody/itsi_maintenance_window_management/storage/collections/data/itsi_mw_automation_state/<request_id>`.
5. Return write operations to dry-run if the app is not yet production-approved.

Rollback never modifies ITSI KV Store directly.
