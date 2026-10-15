from __future__ import annotations

import re
import secrets

from .config import Settings
from .crypto import otp_hash
from .db import Database
from .mail import Mailer

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OTP_TTL_S = 600
OTP_COOLDOWN_S = 45


class IdentityError(RuntimeError):
    """A login failure whose message is safe to show on the page."""


class Identity:
    def __init__(self, settings: Settings, db: Database, mailer: Mailer) -> None:
        self._settings = settings
        self._db = db
        self._mailer = mailer

    def _is_dev(self, email: str) -> bool:
        s = self._settings
        return bool(s.dev_login_email and s.dev_login_code) and email == s.dev_login_email

    def request_otp(self, raw_email: str) -> None:
        email = raw_email.strip().lower()
        if not EMAIL_RE.match(email):
            raise IdentityError("Enter a valid email address.")
        if self._is_dev(email):
            return
        recent = self._db.one(
            "SELECT id FROM otps WHERE email = %s "
            "AND created_at > now() - make_interval(secs => %s)",
            (email, OTP_COOLDOWN_S),
        )
        if recent:
            raise IdentityError("A code was just sent. Wait a moment before requesting another.")
        code = f"{secrets.randbelow(900000) + 100000}"
        self._db.execute(
            "INSERT INTO otps (email, code_hash, expires_at) "
            "VALUES (%s, %s, now() + make_interval(secs => %s))",
            (email, otp_hash(self._settings.session_secret, code, email), OTP_TTL_S),
        )
        ok = self._mailer.send(
            email,
            f"{code} is your Zap login code",
            f"Your Zap login code is {code}. It expires in 10 minutes.\n\n"
            "If you didn't request it, ignore this email.",
        )
        if not ok:
            raise IdentityError("Could not send the login code. Try again in a moment.")

    def verify_otp(self, raw_email: str, raw_code: str) -> tuple[str, str]:
        email, code = raw_email.strip().lower(), raw_code.strip()
        if self._is_dev(email):
            ok = secrets.compare_digest(code, self._settings.dev_login_code)
        else:
            ok = bool(
                self._db.query(
                    "UPDATE otps SET consumed_at = now() WHERE email = %s AND code_hash = %s "
                    "AND consumed_at IS NULL AND expires_at > now() RETURNING id",
                    (email, otp_hash(self._settings.session_secret, code, email)),
                )
            )
        if not ok:
            raise IdentityError("Invalid or expired code.")
        row = self._db.one(
            "INSERT INTO users (email) VALUES (%s) "
            "ON CONFLICT (email) DO UPDATE SET email = excluded.email RETURNING id, email",
            (email,),
        )
        assert row is not None
        return str(row["id"]), str(row["email"])

    def email_of(self, user_id: str) -> str | None:
        row = self._db.one("SELECT email FROM users WHERE id = %s", (user_id,))
        return str(row["email"]) if row else None
