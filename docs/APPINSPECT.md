# AppInspect

## Command
```
splunk-appinspect inspect itsi_maintenance_window_management-1.1.0.spl \
  --mode precert --included-tags cloud --output-file appinspect_cloud.json
```
- Tool: Splunk AppInspect **4.2.1**.
- Package built without macOS AppleDouble files: `COPYFILE_DISABLE=1 tar -czf ...`.

## Result (final)
```
error:           0
failure:         0
future_failure:  0
skipped:          0
not_applicable: 116
warning:         3
success:         123
Total:           242
```

## Remediations performed
| Finding | Action |
|---|---|
| `failure` files outside app dir (`._` AppleDouble) | Rebuilt tar with `COPYFILE_DISABLE=1`. |
| `warning`/`future_failure` python.version deprecated | `python.required = 3.9,3.13` in `alert_actions.conf` and `commands.conf`. |
| `warning` missing `[id]` stanza | Added `[id]` (name+version) to `app.conf`. |
| `failure` custom conf without reload trigger | Added `reload.itsi_maintenance = simple` to `app.conf [triggers]`. |
| `warning` custom conf replication (SHC) | Added `server.conf [shclustering] conf_replication_include.itsi_maintenance = true`. |
| self-referential warnings from packaged AppInspect report | Report kept outside the app package. |

## Remaining warnings (advisory; accepted)
1. **check_for_python_script_existence** — advisory Python 2/3 note. The app code
   is Python 3 only; the bulk of the flagged files are the vendored `splunklib`.
   Not a failure.
2. **check_collections_conf** — informational, *"No action required."*
3. **check_python_sdk_version** — flags vendored `splunklib` 2.1.1 and requests
   3.0.0+. **2.1.1 is the latest version published on PyPI** (`splunk-sdk`) and
   matches the version shipped inside Splunk's own first-party apps, so it cannot
   currently be satisfied. Re-vendor when a 3.x SDK is released. Not a failure.

## Manual-review considerations for Splunk Cloud vetting
- Custom alert action performing network I/O to **local splunkd only** via the
  supported `splunk.rest` interface (no external endpoints).
- App-owned KV Store collection (`itsi_mw_automation_state`) for idempotency.
- Custom capabilities in `authorize.conf`.

## Important
Passing local AppInspect does **not** guarantee Splunk Cloud approval. Final
acceptance is determined by Splunk Cloud app vetting. Re-run AppInspect with the
Cloud service (or the version Splunk requires at submission time) before
submitting.
