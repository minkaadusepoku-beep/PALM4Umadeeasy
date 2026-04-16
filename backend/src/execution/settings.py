"""
Runtime-resolved PALM runner configuration (ADR-005).

Precedence (high → low) for each field:

1. Row in ``palm_runner_config`` (edited from the admin UI)
2. ``PALM_RUNNER_MODE`` / ``PALM_REMOTE_URL`` / ``PALM_REMOTE_TOKEN`` env vars
3. Defaults (mode=stub, url/token empty)

We deliberately merge *per-field* rather than "DB wins if row exists" so an
operator can set a URL in the DB while still inheriting the token from a
systemd environment file, or vice versa.

The merged result is the single source of truth for ``run_palm()`` and for
the admin health panel.

This module is intentionally synchronous in the resolve path because it is
called from worker threads (``run_palm``). It still reads the DB, so we use
a short-lived sync SQLAlchemy engine behind the scenes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .. import config as global_config
from ..db.database import SQLALCHEMY_DATABASE_URL
from ..db.models import PalmRunnerConfig


VALID_MODES = ("stub", "remote", "local")


@dataclass(frozen=True)
class ResolvedRunnerConfig:
    """Effective runner settings after merging DB row with env defaults."""

    mode: str
    remote_url: str
    remote_token: str
    # Provenance — which source won for each field. Surfaced to the admin UI
    # so an operator can see whether the values come from the DB or the
    # environment.
    mode_source: str            # "db" | "env" | "default"
    remote_url_source: str      # "db" | "env" | "unset"
    remote_token_source: str    # "db" | "env" | "unset"

    @property
    def token_configured(self) -> bool:
        return bool(self.remote_token)


def _env_defaults() -> tuple[str, str, str]:
    """
    Read env vars fresh each call.

    We don't rely on the module-level constants in ``src.config`` here
    because the admin "reset to env" action should pick up whatever
    ``os.environ`` says *right now*, which is especially important in tests
    that use ``monkeypatch.setenv``.
    """
    mode = os.environ.get("PALM_RUNNER_MODE", "").strip().lower()
    url = os.environ.get("PALM_REMOTE_URL", "").strip()
    token = os.environ.get("PALM_REMOTE_TOKEN", "").strip()
    return mode, url, token


def _merge(row: Optional[PalmRunnerConfig]) -> ResolvedRunnerConfig:
    env_mode, env_url, env_token = _env_defaults()

    # --- mode ---
    if row is not None and row.mode:
        mode = row.mode.strip().lower()
        mode_source = "db"
    elif env_mode:
        mode = env_mode
        mode_source = "env"
    else:
        mode = "stub"
        mode_source = "default"

    if mode not in VALID_MODES:
        # Fall through to stub rather than crashing the app; /health will
        # still report the bad value so the operator notices.
        mode = "stub"
        mode_source = "default"

    # --- remote_url ---
    if row is not None and row.remote_url:
        remote_url = row.remote_url.strip()
        remote_url_source = "db"
    elif env_url:
        remote_url = env_url
        remote_url_source = "env"
    else:
        remote_url = ""
        remote_url_source = "unset"

    # --- remote_token ---
    if row is not None and row.remote_token:
        remote_token = row.remote_token
        remote_token_source = "db"
    elif env_token:
        remote_token = env_token
        remote_token_source = "env"
    else:
        remote_token = ""
        remote_token_source = "unset"

    return ResolvedRunnerConfig(
        mode=mode,
        remote_url=remote_url,
        remote_token=remote_token,
        mode_source=mode_source,
        remote_url_source=remote_url_source,
        remote_token_source=remote_token_source,
    )


# --- async read path (used by API endpoints + health) --------------------

async def load_config(db: AsyncSession) -> ResolvedRunnerConfig:
    """Read the single-row config (if any) and merge with env."""
    row = await _fetch_row(db)
    return _merge(row)


async def _fetch_row(db: AsyncSession) -> Optional[PalmRunnerConfig]:
    from sqlalchemy import select
    result = await db.execute(select(PalmRunnerConfig).order_by(PalmRunnerConfig.id.asc()))
    return result.scalars().first()


# --- sync read path (used from worker threads) ---------------------------

def load_config_sync() -> ResolvedRunnerConfig:
    """
    Synchronous read of the resolved config.

    ``run_palm`` is called from a background worker thread. Creating a new
    short-lived sync engine is the simplest way to hit the same SQLite
    database without blocking on the async engine. Any failure falls back
    to env-only settings so a broken DB can never silently stop the worker
    from running.
    """
    try:
        row = _fetch_row_sync()
    except Exception:
        row = None
    return _merge(row)


def _fetch_row_sync() -> Optional[PalmRunnerConfig]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    sync_url = _async_url_to_sync(SQLALCHEMY_DATABASE_URL)
    engine = create_engine(sync_url, future=True)
    try:
        with Session(engine) as session:
            result = session.execute(
                select(PalmRunnerConfig).order_by(PalmRunnerConfig.id.asc())
            )
            row = result.scalars().first()
            # Detach so the caller can read it after the session closes.
            if row is not None:
                session.expunge(row)
            return row
    finally:
        engine.dispose()


def _async_url_to_sync(url: str) -> str:
    # sqlite+aiosqlite:/// → sqlite:///
    # postgresql+asyncpg:// → postgresql://
    if "+aiosqlite" in url:
        return url.replace("+aiosqlite", "")
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "")
    return url


# --- write path -----------------------------------------------------------

async def save_config(
    db: AsyncSession,
    *,
    mode: Optional[str],
    remote_url: Optional[str],
    remote_token: Optional[str],
    actor_user_id: Optional[int],
) -> ResolvedRunnerConfig:
    """
    Upsert the single-row config.

    Pass ``None`` for a field to clear it (reverts that field to env/default).
    Pass an empty string to clear as well.
    """
    from datetime import datetime, timezone

    row = await _fetch_row(db)
    if row is None:
        row = PalmRunnerConfig()
        db.add(row)

    row.mode = (mode.strip().lower() if mode else None) or None
    row.remote_url = (remote_url.strip() if remote_url else None) or None
    row.remote_token = (remote_token if remote_token else None) or None
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by_user_id = actor_user_id

    if row.mode and row.mode not in VALID_MODES:
        raise ValueError(f"invalid mode {row.mode!r}; must be one of {VALID_MODES}")

    await db.flush()
    return _merge(row)
