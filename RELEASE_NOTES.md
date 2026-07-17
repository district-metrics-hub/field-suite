# v0.2.5

- Fixes the Python runtime so it is fully self-contained: the dashboard's dependencies now install into the app's own runtime instead of relying on a machine-wide Python. This resolves "the server won't start" on a clean machine.
- The runtime now self-repairs: if an update ever leaves it incomplete, simply launching the dashboard rebuilds it automatically (offline) — no manual steps.

Also included:
- Self-applying updates (the old server is stopped and the new one starts automatically) with no-cache so a new version always loads.
- The dashboard shows its installed version, and the update pill clears once you're current.
- License enforcement on a fresh install (machine-bound lock screen until activated).
