"""Optional v2 app delivery. Watcher evaluation remains owned by this service."""

from __future__ import annotations

import logging
import os

import httpx

from .db import Database

log = logging.getLogger(__name__)


def app_delivery_enabled(db: Database) -> bool:
    row = db.one("SELECT to_regclass('eve.notification_control') AS table_name")
    if not row or not row["table_name"]:
        return False
    control = db.one("SELECT enabled FROM eve.notification_control WHERE id = 1")
    return bool(control and control["enabled"])


def wake_app_delivery() -> None:
    """Best-effort immediate drain; the app cron retries durable jobs independently."""
    url = os.environ.get("NOTIFICATION_WORKER_URL", "").strip()
    secret = os.environ.get("NOTIFICATION_WORKER_SECRET", "").strip()
    if not url or not secret:
        return
    if not url.startswith("https://") or len(secret) < 32:
        log.warning("Notification worker requires HTTPS and a 32-character secret")
        return
    try:
        response = httpx.post(url, headers={"Authorization": f"Bearer {secret}"}, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError:
        log.warning("Notification wake failed; queued mail will retry through the app cron")
