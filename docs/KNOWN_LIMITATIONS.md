# Known Limitations

1. **ITSI version**: live-validated on **ITSI 4.21.3** only. The primary target
   4.22 is design-compatible but not live-validated here. ITSI 5.x is
   documentation-reviewed only (`ITSI5_COMPAT.md`).
2. **Recurring maintenance windows** and **pause durations** are out of scope in
   v1. Requests containing `recurrence_options`/`pause_durations` are not
   produced by the app; only simple fixed start/end windows are created.
3. **Mixed-object windows** are not supported by ITSI. A request mixing entities
   and services is auto-split into separate windows with disambiguated titles.
4. **Unique titles**: ITSI enforces globally-unique window titles. Two distinct
   requests using the same title will collide (HTTP 409). Use unique,
   change-referenced titles.
5. **Search-head clustering** is designed-for (state in replicated KV Store) but
   **not live-validated** (no cluster in the test environment).
6. **`sendalert` in-splunkd invocation** was validated via the production entry
   point run under `splunk cmd python` with the real `splunk.rest` transport;
   invocation through the Splunk scheduler/alert-manager should be confirmed in
   your environment as part of the live demo (`RUNBOOK.md`).
7. **Active-window cancel timing** was validated by logic/design and by cancel of
   future windows; waiting out a live active window was not performed.
8. **Splunk Cloud approval** is determined by Splunk's vetting; passing local
   AppInspect does not guarantee approval.
9. **Summary-index auditing** is optional and off by default; the app logs to a
   rotating file (`itsi_maintenance_window_management.log`). Enable a summary index only
   if one exists/approved.
10. **Vendored `splunklib` is 2.1.1** (the latest `splunk-sdk` on PyPI, matching
    Splunk's first-party apps). AppInspect advises 3.0.0+, which is not yet
    published; re-vendor when available.
11. **Live create *initiated through the custom command*** against real ITSI was
    not run in this environment (no ITSI-capable session key for the offline
    protocol harness). The command→engine seam is validated by the chunked
    protocol test, and the underlying write path is live-validated via the alert
    action, which shares the identical engine.
