# Third-Party Notices

This application (`itsi_maintenance_window_management`) bundles **no third-party
libraries**. It uses only:

- The Python 3 standard library (shipped with Splunk Enterprise / Splunk Cloud).
- Splunk-provided modules available at runtime inside splunkd:
  - `splunk.rest` (Splunk SDK for Python, provided by the platform; not bundled).

No binaries, shared objects, wheels, or vendored packages are included. No code
is executed via `subprocess`, `os.system`, shells, or `curl`.

Therefore there are no third-party license obligations introduced by this app
beyond the app's own Apache-2.0 license (see `LICENSE`).
