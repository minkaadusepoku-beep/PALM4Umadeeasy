# linux_worker — remote PALM execution service

Thin FastAPI service that accepts PALM input bundles from the Windows-side
PALM4Umadeeasy backend, runs PALM, and returns the outputs. See
`docs/decisions/ADR-005-windows-prep-linux-worker.md` for the architectural
decision behind this split.

## Status

**Phase A — plumbing.** `mpirun palm` is stubbed: the worker copies the input
`_static.nc` into the job directory and renames it as a placeholder output so
the end-to-end wire protocol can be tested without a compiled PALM. Phase B
swaps the stub for the real `mpirun palm` call once PALM is compiled on the
Linux host (ADR-001).

## Endpoints

| Method | Path                  | Purpose                                         |
|--------|-----------------------|-------------------------------------------------|
| POST   | `/runs`               | Upload a tar.gz of PALM inputs, enqueue the run |
| GET    | `/runs/{id}`          | Poll status + reproducibility metadata          |
| GET    | `/runs/{id}/output`   | Stream a tar.gz of PALM outputs                 |
| GET    | `/health`             | Liveness check                                  |

## Auth

Every endpoint except `/health` requires
`Authorization: Bearer $PALM_WORKER_TOKEN`. The same token must be set as
`PALM_REMOTE_TOKEN` on the Windows client (ADR-005 §Auth model v1).

## Config

Environment variables:

| Variable              | Default                       | Purpose                                            |
|-----------------------|-------------------------------|----------------------------------------------------|
| `PALM_WORKER_TOKEN`   | **required**                  | Shared bearer token.                               |
| `PALM_WORKER_JOBDIR`  | `/var/lib/palm_worker/jobs`   | Root for per-run scratch directories.              |
| `PALM_WORKER_MODE`    | `stub`                        | `stub` (Phase A) or `mpirun` (Phase B).            |
| `PALM_BINARY`         | `palm`                        | PALM executable (used when mode is `mpirun`).      |
| `PALM_MPI_NP`         | `4`                           | Ranks for `mpirun -np`.                            |
| `PALM_VERSION_LABEL`  | `23.10`                       | Reported back to the client for reproducibility.   |
| `PALM_BUILD_FLAGS`    | `""`                          | Free-form build-flag string echoed to the client.  |

## Run (dev)

```
cd linux_worker
pip install -r requirements.txt
export PALM_WORKER_TOKEN=dev-shared-secret
uvicorn main:app --host 0.0.0.0 --port 8765
```

## Client side

Point the Windows backend at this worker:

```
set PALM_RUNNER_MODE=remote
set PALM_REMOTE_URL=http://<linux-host>:8765
set PALM_REMOTE_TOKEN=dev-shared-secret
```
