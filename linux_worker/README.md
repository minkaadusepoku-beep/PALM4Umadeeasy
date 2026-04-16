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
| GET    | `/health`             | Liveness check (unauthenticated)                |

## Auth

Every endpoint except `/health` requires
`Authorization: Bearer $PALM_WORKER_TOKEN`. The same token must be set as
`PALM_REMOTE_TOKEN` on the Windows client (ADR-005 §Auth model v1).

## Config

| Variable              | Default                       | Purpose                                            |
|-----------------------|-------------------------------|----------------------------------------------------|
| `PALM_WORKER_TOKEN`   | **required**                  | Shared bearer token. `openssl rand -hex 32`.       |
| `PALM_WORKER_JOBDIR`  | `/var/lib/palm-worker/jobs`   | Per-run scratch directories.                       |
| `PALM_WORKER_MODE`    | `stub`                        | `stub` (Phase A) or `mpirun` (Phase B).            |
| `PALM_BINARY`         | `palm`                        | PALM executable (used when mode is `mpirun`).      |
| `PALM_MPI_NP`         | `4`                           | Ranks for `mpirun -np`.                            |
| `PALM_VERSION_LABEL`  | `23.10`                       | Reported back to the client for reproducibility.   |
| `PALM_BUILD_FLAGS`    | `""`                          | Free-form build-flag string echoed to the client.  |

## Deployment

Two supported paths. Pick the one that matches how the Linux host is managed.

### Option 1 — systemd (bare-metal / VM)

```sh
# On the Linux host, from a checkout of the repo:
sudo bash linux_worker/deploy/install.sh
sudo $EDITOR /etc/palm-worker/worker.env     # set PALM_WORKER_TOKEN
sudo systemctl start palm-worker
sudo systemctl status palm-worker --no-pager
curl -s http://127.0.0.1:8765/health
```

`install.sh` is idempotent — re-running it upgrades the code in `/opt/palm-worker`
and preserves `/etc/palm-worker/worker.env`.

Production exposure: put nginx + Let's Encrypt in front of port 8765 and
restrict with a firewall rule or VPN (ADR-005 Phase C).

### Option 2 — Docker Compose

```sh
cp linux_worker/deploy/.env.example linux_worker/deploy/.env
$EDITOR linux_worker/deploy/.env             # set PALM_WORKER_TOKEN
docker compose -f linux_worker/deploy/docker-compose.yml up -d --build
docker compose -f linux_worker/deploy/docker-compose.yml logs -f palm-worker
curl -s http://127.0.0.1:8765/health
```

The compose file binds port 8765 to loopback only. Expose publicly only via a
reverse proxy with TLS.

### Phase B — activating real PALM

Both deployment paths start in `stub` mode (Phase A). To run real PALM:

1. Compile PALM on the host (systemd path) or derive a new image `FROM
   palm4u/linux-worker:latest` with OpenMPI + the compiled PALM binary
   (Docker path). See `palm/compile.md`.
2. Set `PALM_WORKER_MODE=mpirun` and `PALM_BINARY=/path/to/palm` in the
   env file / compose env.
3. Restart the service. No code changes on either side.

## Dev

```sh
cd linux_worker
pip install -r requirements.txt
export PALM_WORKER_TOKEN=dev-shared-secret
uvicorn linux_worker.main:app --host 0.0.0.0 --port 8765
```

## Client side (Windows)

Point the Windows backend at this worker:

```
set PALM_RUNNER_MODE=remote
set PALM_REMOTE_URL=http://<linux-host>:8765
set PALM_REMOTE_TOKEN=<same value as PALM_WORKER_TOKEN>
```

Then restart the Windows backend. The admin dashboard (`/admin`) surfaces the
runner mode and whether the URL/token are configured.

## Layout

```
linux_worker/
├── __init__.py
├── config.py                 env-driven config
├── main.py                   FastAPI app (endpoints, auth, job registry)
├── runner.py                 stub + mpirun palm
├── requirements.txt          runtime deps (fastapi, uvicorn, python-multipart)
├── Dockerfile                minimal image, non-root
├── .dockerignore
└── deploy/
    ├── install.sh            systemd install script (Debian/Ubuntu)
    ├── docker-compose.yml    Compose file for Docker path
    ├── .env.example          Compose env template
    └── systemd/
        ├── palm-worker.service
        └── worker.env.example
```
