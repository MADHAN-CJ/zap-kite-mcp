from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

from zapkite.config import IST, now_ist

from .config import Settings
from .crypto import decrypt, encrypt
from .db import Database

TOKEN_EXPIRY_HOUR_IST = 6

Reason = Literal["not_connected", "token_expired", "disconnected"]


@dataclass(frozen=True)
class Creds:
    user_id: str
    kite_user_id: str
    access_token: str


@dataclass(frozen=True)
class Connection:
    status: str
    kite_user_id: str | None
    user_name: str | None
    connected_at: datetime | None
    expires_at: datetime | None


def next_token_expiry(now: datetime | None = None) -> datetime:
    """Kite sessions end at about 06:00 IST on the next calendar day."""
    current = (now or now_ist()).astimezone(IST)
    candidate = datetime.combine(current.date(), time(TOKEN_EXPIRY_HOUR_IST), IST)
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate


class Broker:
    def __init__(self, settings: Settings, db: Database) -> None:
        self._settings = settings
        self._db = db

    def store_session(
        self, user_id: str, kite_user_id: str, user_name: str | None, token: str
    ) -> None:
        """Persist a Kite session the way the web app does after the Zerodha callback."""
        self._db.execute(
            "INSERT INTO broker_connections "
            "(user_id, kite_user_id, user_name, access_token_enc, status, connected_at, "
            "expires_at, updated_at) VALUES (%s, %s, %s, %s, 'active', now(), %s, now()) "
            "ON CONFLICT (user_id) DO UPDATE SET kite_user_id = excluded.kite_user_id, "
            "user_name = excluded.user_name, access_token_enc = excluded.access_token_enc, "
            "status = 'active', connected_at = now(), expires_at = excluded.expires_at, "
            "token_mail_sent_on = NULL, updated_at = now()",
            (
                user_id,
                kite_user_id,
                user_name,
                encrypt(self._settings.creds_encryption_key, token),
                next_token_expiry(),
            ),
        )

    def creds(self, user_id: str) -> Creds | Reason:
        row = self._db.one(
            "SELECT kite_user_id, access_token_enc, status FROM broker_connections "
            "WHERE user_id = %s",
            (user_id,),
        )
        if row is None:
            return "not_connected"
        if row["status"] != "active" or not row["access_token_enc"]:
            return "token_expired" if row["status"] == "token_expired" else "disconnected"
        token = decrypt(self._settings.creds_encryption_key, str(row["access_token_enc"]))
        return Creds(user_id, str(row["kite_user_id"]), token)

    def connection(self, user_id: str) -> Connection:
        row = self._db.one(
            "SELECT status, kite_user_id, user_name, connected_at, expires_at "
            "FROM broker_connections WHERE user_id = %s",
            (user_id,),
        )
        if row is None:
            return Connection("not_connected", None, None, None, None)
        return Connection(
            str(row["status"]),
            row["kite_user_id"],
            row["user_name"],
            row["connected_at"],
            row["expires_at"],
        )

    def mark_token_expired(self, user_id: str) -> bool:
        changed = self._db.execute(
            "UPDATE broker_connections SET status = 'token_expired', access_token_enc = NULL, "
            "updated_at = now() WHERE user_id = %s AND status = 'active'",
            (user_id,),
        )
        return changed > 0

    def users_to_notify_of_expiry(self) -> list[tuple[str, str]]:
        rows = self._db.query(
            "SELECT b.user_id, u.email FROM broker_connections b JOIN users u ON u.id = b.user_id "
            "WHERE b.status = 'token_expired' AND (b.token_mail_sent_on IS NULL OR "
            "b.token_mail_sent_on < (now() AT TIME ZONE 'Asia/Kolkata')::date) "
            "AND EXISTS (SELECT 1 FROM watchers w WHERE w.user_id = b.user_id "
            "AND w.status = 'PAUSED' AND w.paused_by = 'broker')"
        )
        return [(str(r["user_id"]), str(r["email"])) for r in rows]

    def record_expiry_mail(self, user_id: str) -> None:
        self._db.execute(
            "UPDATE broker_connections "
            "SET token_mail_sent_on = (now() AT TIME ZONE 'Asia/Kolkata')::date WHERE user_id = %s",
            (user_id,),
        )
