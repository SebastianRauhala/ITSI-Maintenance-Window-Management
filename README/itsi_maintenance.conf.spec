#   ITSI Maintenance Window Management - itsi_maintenance.conf.spec
#
# Safety controls for the itsimaintenance custom search command.

[safety]

default_dry_run = <boolean>
* When true, validate and build payloads but perform no writes. Default: true

enable_delete = <boolean>
* Enable the destructive delete operation. Default: false

allow_cancel_active = <boolean>
* Allow cancelling a currently-active window. Default: true

allow_modify_completed = <boolean>
* Allow update/cancel of a completed window. Default: false

require_change_id = <boolean>
* Require a change_id on write operations. Default: false

auto_split_mixed = <boolean>
* Auto-split mixed entity+service requests into separate windows. Default: true

max_rows_per_invocation = <integer>
* Maximum result rows processed per invocation. Default: 2000

max_objects_per_window = <integer>
* Maximum objects per maintenance window. Default: 1000

max_duration_seconds = <integer>
* Maximum maintenance-window duration in seconds. Default: 604800

max_future_horizon_seconds = <integer>
* Maximum future scheduling distance in seconds. Default: 31536000

min_lead_seconds = <integer>
* Minimum lead time before a window may start, in seconds. Default: 0

max_title_length = <integer>
* Maximum title length. Default: 256

max_comment_length = <integer>
* Maximum comment length. Default: 1024

max_request_id_length = <integer>
* Maximum request_id length. Default: 128

allowed_operations = <comma-separated list>
* Subset of validate,list,create,update,cancel,delete permitted. 
* Default: validate,list,create,update,cancel

allowed_object_types = <comma-separated list>
* Subset of entity,service permitted. Default: entity,service

required_title_prefix = <string>
* If set, every window title must start with this prefix. Default: empty

protected_object_keys = <comma-separated list>
* Object keys that may never be placed into maintenance. Default: empty

summary_index = <string>
* Optional summary index for audit records. Default: empty
