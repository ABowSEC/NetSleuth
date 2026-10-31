# NetSleuth tray

A notification-area icon that runs the NetSleuth backend for you.

- **Start:** `run.bat` from the repo root, after `setup.bat` has been run once. No administrator rights are needed unless Npcap was installed in admin-only mode.
- **Menu:**
  - live status ("12 here now · 2 not recognised")
  - Open dashboard
  - Pause/Resume monitoring
  - Network interface
  - new-device notifications
  - Start with Windows
  - logs
  - Restart
  - Quit
- **Supervision** (`supervisor.py`):
  - Starts `python -m netsleuth --headless --exit-on-stdin-close`.
  - Waits for `/api/v1/health`, then restarts with backoff if the backend crashes.
  - Gives up after 5 crashes in 10 minutes.
  - Never retries configuration errors: exit codes 2, 3 and 4.
- **Stopping:** the tray closes the backend's stdin and the backend shuts down cleanly. A backend that hangs is killed together with its child processes. If the tray itself dies, the pipe closes and the backend exits too, so nothing is left running.
- **Files:** everything lives in `%LOCALAPPDATA%\NetSleuth`:
  - `tray.json`: interface, port, notifications
  - `run\backend.pid`, `run\tray.lock`
  - `logs\tray.log`, `logs\backend.log`, `logs\backend-stderr.log`

Tests: `python -m pytest tray`. They drive the supervisor against `tests/fake_backend.py`, which behaves like the real backend from the outside.
