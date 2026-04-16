# PALM4Umadeeasy Linux worker (ADR-005)
#
# Two-stage build: a slim Debian base plus the worker package.
# In Phase A (PALM_WORKER_MODE=stub) no PALM/MPI runtime is required.
# In Phase B, derive a second image FROM this one that adds OpenMPI and the
# compiled PALM binary (PALM compilation is out of scope for this image —
# see palm/compile.md).

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# -- deps ---------------------------------------------------------------------
FROM base AS deps

WORKDIR /app
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

# -- runtime ------------------------------------------------------------------
FROM base AS runtime

# Non-root user for the service. UID 10001 is arbitrary but stable across
# rebuilds so bind-mounted volumes keep correct ownership.
RUN groupadd --system --gid 10001 palmworker \
 && useradd  --system --uid 10001 --gid palmworker --home /app --shell /usr/sbin/nologin palmworker

# Job scratch dir. Persist this as a named volume in production so the
# container can be rebuilt without losing in-flight runs.
RUN mkdir -p /var/lib/palm-worker/jobs \
 && chown -R palmworker:palmworker /var/lib/palm-worker

COPY --from=deps /install /usr/local
WORKDIR /app

# Copy the worker package. Keep this last so code edits don't invalidate the
# dep layer.
COPY __init__.py config.py main.py runner.py ./linux_worker/

USER palmworker

# Sensible defaults; override at runtime.
ENV PALM_WORKER_JOBDIR=/var/lib/palm-worker/jobs \
    PALM_WORKER_MODE=stub

EXPOSE 8765

# Simple container healthcheck — hits /health (unauthenticated).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    r=urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3); \
    sys.exit(0 if r.status==200 else 1)" || exit 1

CMD ["uvicorn", "linux_worker.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
