# ADR-005: Windows Prep Workstation + Remote Linux PALM Worker

**Status:** Accepted
**Date:** 2026-04-16
**Author:** Minka Aduse-Poku

## Context

PALM is Fortran/MPI and compiles only on Linux. The primary development and consultancy workstation is Windows 11. Three deployment models were considered to let Windows-based consultants use the tool productively:

| Option | Windows side | Linux side | Tradeoff |
|---|---|---|---|
| A — Browser-only | Browser only | Everything (API, DB, PALM) | Simple but requires constant network + cloud cost |
| B — Windows prep + remote PALM | API, DB, translation, validation, post-processing, reporting, UI | PALM execution only | Full offline prep, thin Linux dependency, cheapest steady state |
| C — Offline briefcase + manual submit | Everything including file export | PALM only, files transferred manually | No network needed but clumsy UX |

Option B is the best fit: the consultant works entirely on Windows, and the Linux box becomes a thin, stateless PALM execution service. A single office Linux machine (or a cheap cloud VM) serves many Windows workstations, with Windows doing all scenario prep, validation, and result interpretation locally.

## Decision

**Split the pipeline at the `run_palm()` boundary.**

### Windows side (Python, cross-platform already)
- Frontend (Next.js)
- FastAPI backend
- Scenario CRUD, projects, users (SQLite or Postgres)
- Scenario validation (`validation/engine.py`)
- Translation layer (`translation/*`)
- Post-processing (`postprocessing/*`)
- Comparison engine, confidence propagation, report generation
- Job queue (SQLAlchemy-backed, already in place)
- Worker thread that runs the spine

### Linux side (new thin service)
- One FastAPI service (`linux_worker/`) with three endpoints:
  - `POST /runs` — accept a tar.gz of PALM inputs, enqueue, return `run_id`
  - `GET /runs/{id}` — poll status
  - `GET /runs/{id}/output` — download tar.gz of PALM outputs
- Behind the scenes, the Linux worker runs `mpirun palm <case>` in a sandboxed job directory
- Authenticates Windows clients via a Bearer token (shared secret)
- Stateless: everything lives in the job directory, cleaned up after the client downloads the result

### Protocol choice

HTTP + multipart for inputs, streaming download for outputs. Rationale:
- One protocol, one port. Easier firewall than SSH + rsync.
- Works from Windows without extra tools (SSH keys, PuTTY, etc.).
- Maps directly to the existing FastAPI patterns already used in the backend.

### Runner interface on the Windows side

`run_palm()` in `backend/src/execution/runner.py` becomes a dispatcher keyed on `PALM_RUNNER_MODE`:

| Mode | Behaviour | When to use |
|---|---|---|
| `stub` | Current synthetic NetCDF generator | Windows-only development, CI |
| `remote` | Package inputs, POST to Linux worker, poll, download outputs | Production on Windows with a Linux worker |
| `local` | Run `mpirun palm` directly in-process | Linux-only dev, or when everything is on one Linux box |

The default remains `stub` so existing tests and dev workflows are unaffected.

### Auth model (v1)

Shared Bearer token (`PALM_REMOTE_TOKEN` on both sides). Simple, sufficient for a solo-consultant or small-team deployment. Can be upgraded to mTLS or JWT later without protocol changes.

### File transfer format

Inputs packed as a tar.gz with a fixed layout:
```
<case_name>_p3d
<case_name>_static.nc
<case_name>_dynamic.nc
```

Outputs returned as a tar.gz of everything the Linux worker wrote, without prescribing names. The Windows side extracts into the job's `output_dir` and the spine proceeds as if PALM had run locally.

## Consequences

### Positive
- Windows consultants get a complete, offline-capable prep workstation.
- The Linux worker is small (< 300 lines) and stateless — easy to redeploy or scale horizontally.
- No database sync between machines; the only state flowing across is a job bundle.
- The post-processing and reporting pipelines stay on Windows, where they can read outputs directly and integrate with the UI.
- Easy migration path: later, the same Linux worker can sit behind a Celery/Redis queue for multi-tenant SaaS.
- Degrades gracefully: if the Linux worker is down, the user can still run in stub mode and review prep work offline.

### Negative
- Adds an HTTP round-trip (and a file transfer) on every real PALM run. For a typical 500 m × 500 m domain simulation, input bundles are < 50 MB and output bundles are < 500 MB — tolerable over LAN or VPN; noticeable over poor links.
- Two deployable units now: the Windows-side FastAPI app and the Linux worker. Both must version-match on the PALM input format.
- Security is shared-secret only in v1. Must be reviewed before exposing the Linux worker to the public internet.

### Obligations
- The Linux worker must report the exact PALM version and build flags in every response so the Windows side can embed them in reproducibility metadata.
- The Windows spine must not assume any Linux-side state beyond the output bundle: no side-channel logs, no shared filesystem.
- Input and output bundles are the contract. Any format change requires a versioned bump in the bundle manifest.

## Implementation Phases

**Phase A — Plumbing (this commit):**
- Runner refactor to dispatch by mode
- `remote_client.py` HTTP client skeleton
- Config env vars
- Linux worker FastAPI skeleton (with `mpirun palm` still stubbed until PALM is compiled)
- Tests for mode dispatch

**Phase B — PALM compilation on Linux:**
- Provision a Linux machine (ADR-001 exit criterion)
- Compile PALM, replace the `mpirun palm` stub in the Linux worker with the real call
- End-to-end test: Windows-submitted scenario runs on Linux and produces real PALM output

**Phase C — Hardening:**
- Request cancellation
- Client-side retry + resume for interrupted uploads
- Per-user rate limiting on the Linux worker
- TLS with Let's Encrypt if exposed to the internet

## References

- ADR-001: PALM Execution Environment (originally proposed WSL vs cloud VM; this ADR formalises the split)
- ADR-002: Static Driver Generation Strategy (keeps translation cross-platform on Windows)
- `backend/src/spine.py` — spine orchestrator (unaffected by this split)
- `backend/src/workers/queue.py` — existing SQLAlchemy queue (unaffected by this split)
