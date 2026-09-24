#   ITSI Maintenance Window Management - alert_actions.conf.spec
#
# Declares the custom parameters for the itsi_maintenance_action modular alert
# action so configuration validation (btool / splunk validate) recognizes them.

[itsi_maintenance_action]

param.default_dry_run = <boolean>
* When true, validate and build payloads but perform no create/update/cancel/delete.
* Default: true

param.enable_delete = <boolean>
* Enable the destructive delete operation. Disabled by default.
* Default: false

param.allow_cancel_active = <boolean>
* Allow cancelling a currently-active maintenance window (sets end_time to now).
* Default: true

param.allow_modify_completed = <boolean>
* Allow update/cancel of a completed (past end_time) window.
* Default: false

param.require_change_id = <boolean>
* Require a change_id on all write operations.
* Default: false

param.auto_split_mixed = <boolean>
* Auto-split a request that mixes entities and services into separate windows.
* Default: true

param.max_rows_per_invocation = <integer>
* Maximum number of result rows processed per invocation.
* Default: 2000

param.max_objects_per_window = <integer>
* Maximum number of objects allowed in a single maintenance window.
* Default: 1000

param.max_duration_seconds = <integer>
* Maximum allowed maintenance-window duration, in seconds.
* Default: 7776000

param.max_future_horizon_seconds = <integer>
* Maximum allowed scheduling distance into the future, in seconds.
* Default: 31536000

param.min_lead_seconds = <integer>
* Minimum required lead time before a window may start, in seconds.
* Default: 0

param.max_title_length = <integer>
* Maximum allowed title length.
* Default: 256

param.max_comment_length = <integer>
* Maximum allowed comment length.
* Default: 1024

param.max_request_id_length = <integer>
* Maximum allowed request_id length.
* Default: 128

param.allowed_operations = <comma-separated list>
* Subset of validate,list,create,update,cancel,delete permitted at runtime.
* Default: validate,list,create,update,cancel

param.allowed_object_types = <comma-separated list>
* Subset of entity,service permitted at runtime.
* Default: entity,service

param.required_title_prefix = <string>
* If set, every window title must start with this prefix.
* Default: empty (no prefix required)

param.protected_object_keys = <comma-separated list>
* Object keys that may never be placed into maintenance.
* Default: empty

param.summary_index = <string>
* Optional summary index for audit records. Must already exist / be approved.
* Default: empty (file logging only)
