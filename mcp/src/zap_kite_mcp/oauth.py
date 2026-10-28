from __future__ import annotations

import ipaddress
import json
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
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

log = logging.getLogger("zap_kite_mcp.oauth")

TXN_TTL_S = 900
CODE_TTL_S = 300
ACCESS_TTL_S = 3600
REFRESH_TTL_S = 30 * 24 * 3600

OIDC_SCOPES = ("openid", "email")
ALL_SCOPES = (SCOPE, *OIDC_SCOPES)

CIMD_TTL_S = 3600
CIMD_MAX_BYTES = 64 * 1024
CIMD_TIMEOUT_S = 5.0


class LoginExpired(RuntimeError):
    """The authorization transaction is gone; the user must start again from the client."""


def _now() -> datetime:
    return datetime.now(UTC)


def _ts(seconds: int) -> datetime:
    return _now() + timedelta(seconds=seconds)


def same_resource(a: str | None, b: str) -> bool:
    """RFC 8707 resource comparison: scheme/host case-insensitive, trailing slash ignored."""
    if not a:
        return False
    pa, pb = urlparse(a), urlparse(b)
    return (
        pa.scheme.lower() == pb.scheme.lower()
        and pa.netloc.lower() == pb.netloc.lower()
        and pa.path.rstrip("/") == pb.path.rstrip("/")
        and not pa.query
        and not pa.fragment
    )


def is_cimd_client_id(client_id: str) -> bool:
    """A Client ID Metadata Document id is an https URL with a host name, no fragment."""
    p = urlparse(client_id)
    if p.scheme != "https" or not p.hostname or p.fragment or "@" in p.netloc:
        return False
    host = p.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return True
    return False


class OAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """SDK provider: the SDK validates the protocol (PKCE, DCR, redirects); this stores state.

    Clients come from dynamic registration (stored in Postgres) or from a Client ID Metadata
    Document fetched from the client_id URL (ChatGPT's preferred method); CIMD clients are
    public clients (`none`) and are cached in memory for an hour. Every client may request any
    of our scopes, whatever it registered with, so clients registered before a scope existed
    keep working.
    """

    def __init__(
        self, settings: Settings, db: Database, http: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._db = db
        self._http = http or httpx.AsyncClient(timeout=CIMD_TIMEOUT_S, follow_redirects=False)
        self._cimd: dict[str, tuple[float, OAuthClientInformationFull]] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = self._db.one("SELECT data FROM oauth_clients WHERE client_id = %s", (client_id,))
        if row:
            client = OAuthClientInformationFull.model_validate(row["data"])
            client.scope = " ".join(ALL_SCOPES)
            return client
        if is_cimd_client_id(client_id):
            return await self._client_from_cimd(client_id)
        return None

    async def _client_from_cimd(self, client_id: str) -> OAuthClientInformationFull | None:
        cached = self._cimd.get(client_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            r = await self._http.get(client_id, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            log.warning("CIMD fetch failed for %s: %s", client_id, e)
            return None
        if r.status_code != 200 or len(r.content) > CIMD_MAX_BYTES:
            log.warning("CIMD rejected for %s: status %s", client_id, r.status_code)
            return None
        try:
            doc = r.json()
        except ValueError:
            return None
        client = _client_from_document(client_id, doc)
        if client is None:
            log.warning("CIMD document for %s is not usable", client_id)
            return None
        self._cimd[client_id] = (time.monotonic() + CIMD_TTL_S, client)
        return client

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
        scopes = list(params.scopes or [])
        if SCOPE not in scopes:
            scopes.insert(0, SCOPE)
        payload = {
            "client_id": client.client_id,
            "state": params.state,
            "scopes": scopes,
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
            client.client_id,
            authorization_code.subject or "",
            authorization_code.scopes,
            authorization_code.resource,
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
        data = row["data"]
        return self._issue(
            client.client_id, data["subject"], scopes or data["scopes"], data.get("resource")
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._db.one(
            "SELECT data, expires_at FROM oauth_tokens WHERE token_hash = %s AND kind = 'access' "
            "AND NOT revoked AND expires_at > now()",
            (token_hash(token),),
        )
        if row is None:
            return None
        resource = row["data"].get("resource")
        if resource and not same_resource(resource, self._settings.mcp_url):
            log.warning("access token issued for another resource: %s", resource)
            return None
        return AccessToken(
            token=token,
            client_id=row["data"]["client_id"],
            scopes=row["data"]["scopes"],
            expires_at=int(row["expires_at"].timestamp()),
            resource=resource,
            subject=row["data"]["subject"],
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self._db.execute(
            "UPDATE oauth_tokens SET revoked = true WHERE pair = "
            "(SELECT pair FROM oauth_tokens WHERE token_hash = %s)",
            (token_hash(token.token),),
        )

    def _issue(
        self, client_id: str, subject: str, scopes: list[str], resource: str | None
    ) -> OAuthToken:
        access, refresh, pair = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            secrets.token_hex(8),
        )
        data = Jsonb(
            {"client_id": client_id, "subject": subject, "scopes": scopes, "resource": resource}
        )
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
            raise LoginExpired(
                "Login session expired. Go back to your AI assistant and connect again."
            )
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
        return construct_redirect_uri(
            t["redirect_uri"], code=code, state=t["state"], iss=self._settings.public_url
        )


def _client_from_document(client_id: str, doc: Any) -> OAuthClientInformationFull | None:
    if not isinstance(doc, dict) or doc.get("client_id") != client_id:
        return None
    uris = doc.get("redirect_uris")
    if not isinstance(uris, list) or not uris or not all(isinstance(u, str) for u in uris):
        return None
    if any(urlparse(u).scheme != "https" for u in uris):
        return None
    methods = doc.get("token_endpoint_auth_methods_supported") or [
        doc.get("token_endpoint_auth_method", "none")
    ]
    if "none" not in methods:
        return None
    grants = doc.get("grant_types") or ["authorization_code", "refresh_token"]
    if "authorization_code" not in grants:
        return None
    try:
        return OAuthClientInformationFull(
            client_id=client_id,
            client_secret=None,
            redirect_uris=uris,
            token_endpoint_auth_method="none",
            grant_types=[g for g in grants if g in ("authorization_code", "refresh_token")],
            response_types=["code"],
            scope=" ".join(ALL_SCOPES),
            client_name=doc.get("client_name") or None,
            client_uri=doc.get("client_uri") or None,
            logo_uri=doc.get("logo_uri") or None,
            application_type="web",
        )
    except ValueError:
        return None
