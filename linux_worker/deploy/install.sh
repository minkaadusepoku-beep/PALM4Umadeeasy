#!/usr/bin/env bash
# Install the PALM4Umadeeasy Linux worker on a Debian/Ubuntu host.
#
# What this does (idempotent — safe to re-run on upgrades):
#   1. Creates the palmworker system user and /opt/palm-worker layout.
#   2. Copies linux_worker/ into /opt/palm-worker and sets up a venv.
#   3. Installs the systemd unit + a stub /etc/palm-worker/worker.env on
#      first install (preserved on upgrade).
#   4. Reloads systemd and enables the service without starting it, so the
#      operator can edit worker.env first. A final instruction prints the
#      remaining steps.
#
# Does NOT:
#   - Compile PALM. That's a separate step documented in palm/compile.md.
#   - Open a firewall port. Configure your firewall (ufw, iptables, cloud
#     security group) separately — default port is 8765.
#   - Install TLS. For production internet exposure, front this with nginx
#     + Let's Encrypt (ADR-005 Phase C).
#
# Usage (from a checkout of the repo, on the Linux host):
#   sudo bash linux_worker/deploy/install.sh

set -euo pipefail

: "${PALM_WORKER_USER:=palmworker}"
: "${PALM_WORKER_HOME:=/opt/palm-worker}"
: "${PALM_WORKER_ENV_DIR:=/etc/palm-worker}"
: "${PALM_WORKER_STATE_DIR:=/var/lib/palm-worker}"
: "${PYTHON_BIN:=python3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"  # linux_worker/

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must run as root (use sudo)." >&2
  exit 1
fi

echo ">>> Ensuring system user '${PALM_WORKER_USER}' exists..."
if ! id -u "${PALM_WORKER_USER}" >/dev/null 2>&1; then
  useradd --system \
          --home "${PALM_WORKER_HOME}" \
          --shell /usr/sbin/nologin \
          --user-group \
          "${PALM_WORKER_USER}"
fi

echo ">>> Ensuring directories..."
install -d -m 0755 -o "${PALM_WORKER_USER}" -g "${PALM_WORKER_USER}" "${PALM_WORKER_HOME}"
install -d -m 0750 -o root -g "${PALM_WORKER_USER}" "${PALM_WORKER_ENV_DIR}"
install -d -m 0750 -o "${PALM_WORKER_USER}" -g "${PALM_WORKER_USER}" "${PALM_WORKER_STATE_DIR}"

echo ">>> Syncing worker source to ${PALM_WORKER_HOME}/linux_worker..."
install -d -m 0755 -o "${PALM_WORKER_USER}" -g "${PALM_WORKER_USER}" "${PALM_WORKER_HOME}/linux_worker"
# Use rsync if available (faster, preserves), otherwise cp.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
        --exclude='__pycache__' \
        --exclude='deploy' \
        "${WORKER_SRC}/" "${PALM_WORKER_HOME}/linux_worker/"
else
  cp -r "${WORKER_SRC}/." "${PALM_WORKER_HOME}/linux_worker/"
fi
chown -R "${PALM_WORKER_USER}:${PALM_WORKER_USER}" "${PALM_WORKER_HOME}/linux_worker"

echo ">>> Creating virtualenv at ${PALM_WORKER_HOME}/venv..."
if [[ ! -d "${PALM_WORKER_HOME}/venv" ]]; then
  sudo -u "${PALM_WORKER_USER}" "${PYTHON_BIN}" -m venv "${PALM_WORKER_HOME}/venv"
fi
sudo -u "${PALM_WORKER_USER}" "${PALM_WORKER_HOME}/venv/bin/pip" install --upgrade pip >/dev/null
sudo -u "${PALM_WORKER_USER}" "${PALM_WORKER_HOME}/venv/bin/pip" install -r "${WORKER_SRC}/requirements.txt"

echo ">>> Installing systemd unit..."
install -m 0644 \
        "${SCRIPT_DIR}/systemd/palm-worker.service" \
        /etc/systemd/system/palm-worker.service

if [[ ! -f "${PALM_WORKER_ENV_DIR}/worker.env" ]]; then
  echo ">>> First install: seeding ${PALM_WORKER_ENV_DIR}/worker.env from example..."
  install -m 0640 -o root -g "${PALM_WORKER_USER}" \
          "${SCRIPT_DIR}/systemd/worker.env.example" \
          "${PALM_WORKER_ENV_DIR}/worker.env"
else
  echo ">>> Preserving existing ${PALM_WORKER_ENV_DIR}/worker.env (upgrade)."
fi

echo ">>> Reloading systemd and enabling the service..."
systemctl daemon-reload
systemctl enable palm-worker.service >/dev/null

cat <<EOF

======================================================================
Install complete.

Next steps (manual):

  1. Edit the shared secret and mode:
       sudo \$EDITOR ${PALM_WORKER_ENV_DIR}/worker.env

     At minimum set PALM_WORKER_TOKEN to a long random value:
       openssl rand -hex 32

     Phase A (HTTP protocol only): leave PALM_WORKER_MODE=stub.
     Phase B (real PALM):           set PALM_WORKER_MODE=mpirun and
                                    point PALM_BINARY at the compiled PALM.

  2. Start the service:
       sudo systemctl start palm-worker
       sudo systemctl status palm-worker --no-pager
       curl -s http://127.0.0.1:8765/health

  3. On the Windows backend (.env or shell):
       PALM_RUNNER_MODE=remote
       PALM_REMOTE_URL=http://<this-host>:8765
       PALM_REMOTE_TOKEN=<same value as PALM_WORKER_TOKEN above>

  4. (Production) Put nginx + TLS in front of port 8765 and
     restrict firewall access to the Windows client. See
     docs/decisions/ADR-005-windows-prep-linux-worker.md Phase C.

======================================================================
EOF
