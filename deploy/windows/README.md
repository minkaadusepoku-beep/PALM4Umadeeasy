# PALM4Umadeeasy — Windows one-click launcher

Start the whole platform (FastAPI backend + Next.js frontend) with one action
and land in the browser on the scenario editor. No manual `uvicorn` / `npm run
dev` juggling.

## Files

| File                            | Purpose                                                  |
|---------------------------------|----------------------------------------------------------|
| `Start-PALM4Umadeeasy.bat`      | Double-clickable entry point. Wraps the PS1.             |
| `Start-PALM4Umadeeasy.ps1`      | The real launcher (backend + frontend + browser).        |
| `Stop-PALM4Umadeeasy.ps1`       | Stops whatever is listening on ports 8000 / 3000.        |

## First run

Prereqs on PATH:

- **Python 3.11+** (`python --version`)
- **Node.js 20+** (`node --version`)

Then:

1. Open the `deploy\windows\` folder in Explorer.
2. Double-click **`Start-PALM4Umadeeasy.bat`**.
3. Two minimised PowerShell windows appear (backend + frontend) and your
   default browser opens at `http://127.0.0.1:3000`.

The first frontend launch runs `npm ci` automatically (a few minutes). Every
subsequent launch starts in ~10 seconds.

## Normal use

- **Start**: double-click `Start-PALM4Umadeeasy.bat`.
- **Stop**: close the two minimised PowerShell windows, *or* run
  `Stop-PALM4Umadeeasy.ps1` from a PowerShell prompt.
- **Admin panel** (runner mode + worker status):
  `http://127.0.0.1:3000/admin`

Re-running the launcher while it's already up is safe — it detects occupied
ports and skips starting that component.

## Options

```powershell
# Hot-reload dev mode (default)
.\Start-PALM4Umadeeasy.ps1

# Production build (slower first launch, faster pages)
.\Start-PALM4Umadeeasy.ps1 -Mode prod

# Don't open the browser (headless / remote desktop)
.\Start-PALM4Umadeeasy.ps1 -NoBrowser

# Use different ports
.\Start-PALM4Umadeeasy.ps1 -BackendPort 8001 -FrontendPort 3001
```

Same flags work via the `.bat`:

```cmd
Start-PALM4Umadeeasy.bat -Mode prod
```

## Stopping

```powershell
# Interactive (asks before killing each process)
.\Stop-PALM4Umadeeasy.ps1

# Non-interactive
.\Stop-PALM4Umadeeasy.ps1 -Force

# Custom ports (must match what you started with)
.\Stop-PALM4Umadeeasy.ps1 -BackendPort 8001 -FrontendPort 3001 -Force
```

The stop script walks the child-process tree (uvicorn workers, `next dev`
children, the minimised host `powershell.exe`) so the port ends up free.

## Where simulations actually run

The launcher starts the **Windows backend**, which prepares PALM inputs. Where
PALM itself runs depends on `PALM_RUNNER_MODE` (see ADR-005):

- `stub` (default) — synthetic outputs, no real PALM. Good for UI work.
- `remote` — inputs are shipped over HTTPS to a Linux worker
  (`linux_worker/`). Set `PALM_REMOTE_URL` and `PALM_REMOTE_TOKEN`.
- `local` — in-process `mpirun palm`. Not supported on Windows.

The admin dashboard (`/admin`) shows the current mode, PALM version reported
by the worker, and whether the URL/token are configured.

## Troubleshooting

- **"Python is not on PATH"** — install Python 3.11+ from python.org and tick
  *Add Python to PATH*, then re-run.
- **"Node.js is not on PATH"** — install Node 20 LTS from nodejs.org, then
  re-run.
- **Frontend never becomes healthy** — un-minimise the frontend PowerShell
  window; Next.js prints the real error there (often a port conflict or a
  corrupted `frontend\node_modules`, which you can fix with
  `rm -r frontend\node_modules` followed by re-running the launcher).
- **Backend `/api/health` never goes green** — un-minimise the backend window;
  common causes are a stale `palm4u.db` schema (delete the file — it's
  re-created) or a Python dependency missing (`pip install -r
  backend\requirements.txt`).
- **"Running scripts is disabled on this system"** — the `.bat` wrapper
  already passes `-ExecutionPolicy Bypass`, so use it instead of invoking the
  `.ps1` directly.

## Optional: desktop / Start-menu shortcut

Right-click `Start-PALM4Umadeeasy.bat` → **Send to → Desktop (create
shortcut)**. Rename the shortcut to "PALM4Umadeeasy" and set a custom icon in
its Properties if you want.
