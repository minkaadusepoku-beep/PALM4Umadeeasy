"""Audit logging for security-relevant actions."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditLog
from ..monitoring.logging_config import request_id_var

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    detail: str = "",
    ip_address: str = "",
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
        request_id=request_id_var.get(""),
    )
    db.add(entry)
    await db.flush()
    logger.info(
        "AUDIT: user=%s action=%s resource=%s/%s detail=%s",
        user_id, action, resource_type, resource_id, detail,
    )
