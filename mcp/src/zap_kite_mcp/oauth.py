from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from psycopg.types.json import Jsonb

from .config import SCOPE, Settings
from .crypto import token_hash
from .db import Database

TXN_TTL_S = 900
CODE_TTL_S = 300
ACCESS_TTL_S = 3600
REFRESH_TTL_S = 30 * 24 * 3600


class LoginExpired(RuntimeError):
    """The authorization transaction is gone; the user must start again from the client."""


def _now() -> datetime:
    return datetime.now(UTC)


def _ts(seconds: int) -> datetime:
    return _now() + timedelta(seconds=seconds)


class OAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """SDK provider: the SDK validates the protocol (PKCE, DCR, redirects); this stores state."""

    def __init__(self, settings: Settings, db: Database) -> None:
        self._settings = settings
        self._db = db

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = self._db.one("SELECT data FROM oauth_clients WHERE client_id = %s", (client_id,))
        return OAuthClientInformationFull.model_validate(row["data"]) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._db.execute(
            "INSERT INTO oauth_clients (client_id, data) VALUES (%s, %s) "
            "ON CONFLICT (client_id) DO UPDATE SET data = excluded.data",
            (client_info.client_id, Jsonb(json.loads(client_info.model_dump_json()))),
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        txn = secrets.token_urlsafe(24)
        payload = {
            "client_id": client.client_id,
            "state": params.state,
            "scopes": params.scopes or [SCOPE],
            "code_challenge": params.code_challenge,
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "resource": params.resource,
        }
        self._db.execute(
            "INSERT INTO oauth_txns (txn_id, params, expires_at) VALUES (%s, %s, %s)",
            (txn, Jsonb(payload), _ts(TXN_TTL_S)),
        )
        return f"{self._settings.public_url}/login?txn={txn}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        row = self._db.one(
            "SELECT data FROM oauth_codes WHERE code = %s AND expires_at > now()",
            (authorization_code,),
        )
        if row is None:
            return None
        code = AuthorizationCode.model_validate(row["data"])
        return code if code.client_id == client.client_id else None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self._db.execute("DELETE FROM oauth_codes WHERE code = %s", (authorization_code.code,))
        return self._issue(
            client.client_id, authorization_code.subject or "", authorization_code.scopes
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        row = self._db.one(
            "SELECT data, expires_at FROM oauth_tokens WHERE token_hash = %s AND kind = 'refresh' "
            "AND NOT revoked AND expires_at > now()",
            (token_hash(refresh_token),),
        )
        if row is None or row["data"].get("client_id") != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=row["data"]["scopes"],
            expires_at=int(row["expires_at"].timestamp()),
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        row = self._db.one(
            "SELECT data, pair FROM oauth_tokens WHERE token_hash = %s AND kind = 'refresh'",
            (token_hash(refresh_token.token),),
        )
        if row is None:
            raise LoginExpired("refresh token unknown")
        self._db.execute("UPDATE oauth_tokens SET revoked = true WHERE pair = %s", (row["pair"],))
        return self._issue(
            client.client_id, row["data"]["subject"], scopes or row["data"]["scopes"]
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._db.one(
            "SELECT data, expires_at FROM oauth_tokens WHERE token_hash = %s AND kind = 'access' "
            "AND NOT revoked AND expires_at > now()",
            (token_hash(token),),
        )
        if row is None:
            return None
        return AccessToken(
            token=token,
            client_id=row["data"]["client_id"],
            scopes=row["data"]["scopes"],
            expires_at=int(row["expires_at"].timestamp()),
            subject=row["data"]["subject"],
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self._db.execute(
            "UPDATE oauth_tokens SET revoked = true WHERE pair = "
            "(SELECT pair FROM oauth_tokens WHERE token_hash = %s)",
            (token_hash(token.token),),
        )

    def _issue(self, client_id: str, subject: str, scopes: list[str]) -> OAuthToken:
        access, refresh, pair = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            secrets.token_hex(8),
        )
        data = Jsonb({"client_id": client_id, "subject": subject, "scopes": scopes})
        self._db.execute(
            "INSERT INTO oauth_tokens (token_hash, kind, data, pair, expires_at) VALUES "
            "(%s, 'access', %s, %s, %s), (%s, 'refresh', %s, %s, %s)",
            (
                token_hash(access),
                data,
                pair,
                _ts(ACCESS_TTL_S),
                token_hash(refresh),
                data,
                pair,
                _ts(REFRESH_TTL_S),
            ),
        )
        self._db.execute("DELETE FROM oauth_tokens WHERE expires_at < now() - interval '1 day'")
        self._db.execute("DELETE FROM oauth_txns WHERE expires_at < now()")
        self._db.execute("DELETE FROM oauth_codes WHERE expires_at < now()")
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL_S,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )

    def txn(self, txn_id: str) -> dict[str, Any] | None:
        row = self._db.one(
            "SELECT params, email FROM oauth_txns WHERE txn_id = %s AND expires_at > now()",
            (txn_id,),
        )
        if row is None:
            return None
        return {**row["params"], "email": row["email"]}

    def txn_set_email(self, txn_id: str, email: str) -> None:
        self._db.execute("UPDATE oauth_txns SET email = %s WHERE txn_id = %s", (email, txn_id))

    def finish_login(self, txn_id: str, user_id: str) -> str:
        """Mint the authorization code for a verified user and return the client redirect URL."""
        t = self.txn(txn_id)
        if t is None:
            raise LoginExpired("Login session expired. Go back to Claude and connect again.")
        code = secrets.token_urlsafe(32)
        model = AuthorizationCode(
            code=code,
            scopes=t["scopes"],
            expires_at=int(_ts(CODE_TTL_S).timestamp()),
            client_id=t["client_id"],
            code_challenge=t["code_challenge"],
            redirect_uri=t["redirect_uri"],
            redirect_uri_provided_explicitly=t["redirect_uri_provided_explicitly"],
            resource=t.get("resource"),
            subject=user_id,
        )
        self._db.execute(
            "INSERT INTO oauth_codes (code, data, expires_at) VALUES (%s, %s, %s)",
            (code, Jsonb(json.loads(model.model_dump_json())), _ts(CODE_TTL_S)),
        )
        self._db.execute("DELETE FROM oauth_txns WHERE txn_id = %s", (txn_id,))
        return construct_redirect_uri(t["redirect_uri"], code=code, state=t["state"])
