from __future__ import annotations

import logging

import httpx

from .config import Settings

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


class Mailer:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=15.0)
        self.sent: list[dict[str, str]] = []

    def send(self, to: str, subject: str, text: str) -> bool:
        if not self._settings.resend_api_key:
            log.warning("RESEND_API_KEY unset; email to %s not sent: %s", to, subject)
            self.sent.append({"to": to, "subject": subject, "text": text})
            return True
        try:
            r = self._client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {self._settings.resend_api_key}"},
                json={
                    "from": self._settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
        except httpx.HTTPError as e:
            log.error("email send failed: %s", e)
            return False
        if r.status_code >= 400:
            log.error("email send rejected: %s %s", r.status_code, r.text[:200])
            return False
        return True
