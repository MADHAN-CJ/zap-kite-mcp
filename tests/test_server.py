from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import psycopg
import pytest
import uvicorn

from zap_kite_mcp import server as srv
from zap_kite_mcp.config import load_settings

from .fake_kite import ACCESS_TOKEN, API_KEY, API_SECRET, TODAY, FakeKite

TEST_DB = os.environ.get(
    "ZAP_KITE_MCP_TEST_DATABASE_URL", "postgresql://localhost/zap_kite_mcp_test"
)
DEV_EMAIL, DEV_CODE = "dev@example.com", "123456"
TABLES = (
    "watcher_fires",
    "watchers",
    "oauth_tokens",
    "oauth_codes",
    "oauth_txns",
    "oauth_clients",
    "broker_connections",
    "otps",
    "users",
)


def _db_available() -> bool:
    try:
        psycopg.connect(TEST_DB, connect_timeout=3).close()
        return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason=f"no Postgres at {TEST_DB}")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Harness:
    def __init__(self, tmp: Path) -> None:
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.fake = FakeKite()
        env = {
            "DATABASE_URL": TEST_DB,
            "ZAP_KITE_MCP_PUBLIC_URL": self.base,
            "ZAP_KITE_MCP_APP_URL": "https://web.example",
            "ZAP_KITE_MCP_HOST": "127.0.0.1",
            "ZAP_KITE_MCP_PORT": str(self.port),
            "KITE_API_KEY": API_KEY,
            "KITE_API_SECRET": API_SECRET,
            "KITE_BASE_URL": "https://fake.kite.test",
            "SESSION_SECRET": secrets.token_hex(32),
            "CREDS_ENCRYPTION_KEY": secrets.token_hex(32),
            "SWEEP_SECRET": "sweep-secret-for-tests",
            "ZAP_KITE_MCP_STATE_DIR": str(tmp / "state"),
            "DEV_LOGIN_EMAIL": DEV_EMAIL,
            "DEV_LOGIN_CODE": DEV_CODE,
            "WATCHERS_MIN_GAP_MINUTES": "0",
            "ZAPKITE_TODAY": TODAY.isoformat(),
            "RESEND_API_KEY": "",
        }
        self._old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        self.settings = load_settings()
        self.app = srv.build_app(self.settings, kite_transport=self.fake.transport())
        mcp = srv.build_server(self.app)
        asgi = mcp.streamable_http_app(
            stateless_http=True,
            json_response=True,
            transport_security=srv.transport_security(self.settings),
            host=self.settings.host,
        )
        for name in ("mcp", "uvicorn", "zap_kite_mcp"):
            logging.getLogger(name).setLevel(logging.WARNING)
        self._server = uvicorn.Server(
            uvicorn.Config(asgi, host="127.0.0.1", port=self.port, log_level="warning")
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                if httpx.get(f"{self.base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise RuntimeError("server did not boot")

    def reset_db(self) -> None:
        self.app.db.execute("TRUNCATE " + ", ".join(TABLES) + " CASCADE")
        self.app.mailer.sent.clear()
        self.fake.calls.clear()
        self.fake.token_valid = True
        self.fake.data_plan = True

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)
        self.app.close()
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(scope="module")
def harness(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Harness]:
    h = Harness(tmp_path_factory.mktemp("zkm"))
    yield h
    h.stop()


@pytest.fixture
def h(harness: Harness) -> Harness:
    harness.reset_db()
    return harness


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def oauth_login(h: Harness, email: str = DEV_EMAIL) -> str:
    """Run DCR → authorize → email/OTP pages → code → token; return the access token."""
    return str(oauth_tokens(h, email)["access_token"])


def oauth_tokens(h: Harness, email: str = DEV_EMAIL) -> dict[str, Any]:
    web = httpx.Client(base_url=h.base, follow_redirects=False, timeout=10)
    reg = web.post(
        "/register",
        json={
            "client_name": "test",
            "redirect_uris": ["https://client.example/cb"],
            "grant_types": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert reg.status_code == 201, reg.text
    client_id = reg.json()["client_id"]
    verifier, challenge = _pkce()
    auth = web.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://client.example/cb",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "xyz",
            "scope": "kite:read",
        },
    )
    assert auth.status_code == 302, auth.text
    login_url = auth.headers["location"]
    txn = parse_qs(urlparse(login_url).query)["txn"][0]
    assert "Connect Claude" in web.get(login_url).text
    r = web.post("/login/email", data={"txn": txn, "email": email})
    assert r.status_code == 200 and "login code" in r.text
    r = web.post("/login/otp", data={"txn": txn, "code": DEV_CODE})
    assert r.status_code == 302, r.text
    cb = urlparse(r.headers["location"])
    assert cb.netloc == "client.example"
    q = parse_qs(cb.query)
    assert q["state"] == ["xyz"]
    tok = web.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": q["code"][0],
            "redirect_uri": "https://client.example/cb",
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert tok.status_code == 200, tok.text
    body: dict[str, Any] = tok.json()
    assert body["token_type"].lower() == "bearer" and body.get("refresh_token")
    body["client_id"] = client_id
    return body


class Mcp:
    def __init__(self, base: str, token: str) -> None:
        self.url = f"{base}/mcp"
        self.h = httpx.Client(timeout=120)
        self.token = token
        self.n = 0
        self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        )

    def rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.n += 1
        r = self.h.post(
            self.url,
            json={"jsonrpc": "2.0", "id": self.n, "method": method, "params": params},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200, f"{method}: {r.status_code} {r.text[:300]}"
        body: dict[str, Any] = r.json()
        return body

    def tool(self, name: str, **args: Any) -> tuple[str, bool]:
        res = self.rpc("tools/call", {"name": name, "arguments": args})["result"]
        text = "".join(c.get("text", "") for c in res.get("content", []))
        return text, bool(res.get("isError"))

    def tools(self) -> list[str]:
        return [t["name"] for t in self.rpc("tools/list", {})["result"]["tools"]]


def user_id_of(h: Harness, email: str = DEV_EMAIL) -> str:
    row = h.app.db.one(
        "INSERT INTO users (email) VALUES (%s) ON CONFLICT (email) DO UPDATE SET email = excluded.email "
        "RETURNING id",
        (email,),
    )
    assert row
    return str(row["id"])


def connect_kite(h: Harness, email: str = DEV_EMAIL) -> str:
    """What the web app's callback does after Zerodha redirects back: store the session."""
    user_id = user_id_of(h, email)
    h.app.broker.store_session(user_id, "AB1234", "Test User", ACCESS_TOKEN)
    h.app.watchers.resume_after_reconnect(user_id)
    return user_id


def sweep(h: Harness, **body: Any) -> dict[str, Any]:
    r = httpx.post(
        f"{h.base}/internal/sweep",
        headers={"x-sweep-secret": "sweep-secret-for-tests"},
        json={"force": True, **body},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


# ---------------------------------------------------------------- tests


def test_health_and_oauth_metadata(h: Harness) -> None:
    assert httpx.get(f"{h.base}/health").json()["ok"] is True
    meta = httpx.get(f"{h.base}/.well-known/oauth-authorization-server").json()
    assert meta["issuer"].rstrip("/") == h.base
    assert meta["registration_endpoint"] == f"{h.base}/register"
    prm = httpx.get(f"{h.base}/.well-known/oauth-protected-resource/mcp").json()
    assert prm["resource"] == f"{h.base}/mcp"
    assert httpx.post(f"{h.base}/mcp", json={}).status_code == 401


def test_oauth_login_and_tools_before_connecting(h: Harness) -> None:
    mcp = Mcp(h.base, oauth_login(h))
    assert mcp.tools() == ["run_python", "auth_status", "create_watcher", "list_watchers"]
    status = json.loads(mcp.tool("auth_status")[0])
    assert (
        status["signedIn"] and status["email"] == DEV_EMAIL and status["broker"] == "not_connected"
    )
    assert status["appUrl"] == "https://web.example"
    text, is_error = mcp.tool("run_python", code="print(1)")
    assert not is_error and "not connected" in text and "https://web.example" in text
    text, _ = mcp.tool(
        "create_watcher", symbol="TCS", label="x", script="print('{\"met\": false}')"
    )
    assert "not connected" in text


def test_kite_connect_and_run_python_through_gateway(h: Harness) -> None:
    connect_kite(h)
    mcp = Mcp(h.base, oauth_login(h))
    status = json.loads(mcp.tool("auth_status")[0])
    assert status["broker"] == "active" and status["kiteUserId"] == "AB1234"

    code = (
        "import os, json, zapkite as z\n"
        "print(json.dumps({'user': z.profile()['user_id'], 'tcs': z.ltp_of('TCS'),"
        " 'leak': [k for k in os.environ if k.startswith('KITE')], 'gw': 'ZAPKITE_GATEWAY_URL' in os.environ}))"
    )
    text, is_error = mcp.tool("run_python", code=code)
    assert not is_error, text
    out = json.loads(text.split("--- stdout ---\n")[1].strip())
    assert out == {"user": "AB1234", "tcs": 3500.0, "leak": [], "gw": True}
    upstream = [r for r in h.fake.calls if r.url.path == "/quote/ltp"]
    assert upstream and upstream[-1].headers["Authorization"] == f"token {API_KEY}:{ACCESS_TOKEN}"

    text, is_error = mcp.tool("run_python", code="import zapkite as z\nz.nope()")
    assert is_error and "AttributeError" in text

    text, is_error = mcp.tool(
        "run_python",
        code="import zapkite as z\nc=z.option_chain('NIFTY', strikes_around=2)\nprint(len(c['strikes']), c['strikes'][2]['ce']['iv'] is not None)",
    )
    assert not is_error and "5 True" in text


def test_gateway_rejects_bad_tokens_and_writes(h: Harness) -> None:
    r = httpx.get(f"{h.base}/kite/user/profile")
    assert r.status_code == 401 and r.json()["error_type"] == "TokenException"
    token = h.app.tokens.issue("00000000-0000-0000-0000-000000000000")
    r = httpx.get(f"{h.base}/kite/orders/regular", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403 and "TokenException" in r.text
    r = httpx.post(f"{h.base}/kite/orders/regular", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 405
    r = httpx.get(f"{h.base}/kite/session/token", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403 and "not a read endpoint" in r.text


def test_token_expiry_marks_connection_and_pauses_watchers(h: Harness) -> None:
    connect_kite(h)
    mcp = Mcp(h.base, oauth_login(h))
    text, _ = mcp.tool(
        "create_watcher",
        symbol="TCS",
        label="TCS above 3400",
        script="import zapkite as z, json\nltp=z.ltp_of('NSE:TCS')\nprint(json.dumps({'met': ltp > 3400, 'value': ltp}))",
    )
    created = json.loads(text)
    assert created["status"] == "ARMED" and created["alreadyMet"] is True

    h.fake.token_valid = False
    text, is_error = mcp.tool("run_python", code="import zapkite as z\nprint(z.funds())")
    assert is_error and "TokenExpired" in text and "log in to Zerodha again" in text
    assert json.loads(mcp.tool("auth_status")[0])["broker"] == "token_expired"
    listed = json.loads(mcp.tool("list_watchers")[0])["watchers"]
    assert listed[0]["status"] == "PAUSED" and listed[0]["pausedBy"] == "broker"

    report = sweep(h)
    assert report["expiryMails"] == 1
    assert h.app.mailer.sent[-1]["subject"].startswith("Zap watchers paused")
    assert sweep(h)["expiryMails"] == 0

    h.fake.token_valid = True
    connect_kite(h)
    listed = json.loads(mcp.tool("list_watchers")[0])["watchers"]
    assert listed[0]["status"] == "ARMED" and listed[0]["pausedBy"] is None
    assert json.loads(mcp.tool("auth_status")[0])["broker"] == "active"


def test_watcher_lifecycle(h: Harness) -> None:
    connect_kite(h)
    mcp = Mcp(h.base, oauth_login(h))
    script = (
        "import zapkite as z, json\n"
        "ltp = z.ltp_of('NSE:INFY')\n"
        "print(json.dumps({'met': ltp > 1600, 'value': ltp, 'detail': 'infy'}))"
    )
    bad, _ = mcp.tool("create_watcher", symbol="INFY", label="bad", script="print('hello')")
    assert bad.startswith("Watcher NOT created")
    text, _ = mcp.tool(
        "create_watcher",
        symbol="INFY",
        label="INFY above 1600",
        script=script,
        check_every_minutes=1,
    )
    w = json.loads(text)
    assert w["status"] == "ARMED" and w["alreadyMet"] is False and w["market"] == "NSE"
    assert w["pageUrl"] == "https://web.example"
    wid = w["id"]

    gold, _ = mcp.tool(
        "create_watcher",
        symbol="GOLD",
        label="gold",
        script="import json, zapkite as z\nprint(json.dumps({'met': z.ltp_of('MCX:GOLD25DECFUT') > 1}))",
    )
    assert json.loads(gold)["market"] == "MCX" and json.loads(gold)["alreadyMet"] is True

    h.app.db.execute("UPDATE watchers SET last_checked_at = now() - interval '1 hour'")
    report = sweep(h)
    assert report["checked"] == 2 and report["fired"] == 0

    h.fake.prices["NSE:INFY"] = 1650.0
    h.app.db.execute("UPDATE watchers SET last_checked_at = now() - interval '1 hour'")
    report = sweep(h)
    assert report["fired"] == 1
    mail = h.app.mailer.sent[-1]
    assert (
        mail["to"] == DEV_EMAIL and "INFY above 1600" in mail["subject"] and "1650" in mail["text"]
    )

    h.app.db.execute("UPDATE watchers SET last_checked_at = now() - interval '1 hour'")
    assert sweep(h)["fired"] == 0
    h.fake.prices["NSE:INFY"] = 1500.0
    h.app.db.execute("UPDATE watchers SET last_checked_at = now() - interval '1 hour'")
    sweep(h)
    h.fake.prices["NSE:INFY"] = 1700.0
    h.app.db.execute("UPDATE watchers SET last_checked_at = now() - interval '1 hour'")
    assert sweep(h)["fired"] == 1

    listed = {x["id"]: x for x in json.loads(mcp.tool("list_watchers")[0])["watchers"]}
    assert listed[wid]["alertCount"] == 2 and len(listed[wid]["recentAlerts"]) == 2

    h.app.db.execute("UPDATE watchers SET status = 'CANCELLED' WHERE id = %s", (wid,))
    h.app.db.execute("UPDATE watchers SET error_count = 0")
    h.app.db.execute("UPDATE watchers SET script = 'raise SystemExit(3)' WHERE status = 'ARMED'")
    for _ in range(5):
        h.app.db.execute("UPDATE watchers SET last_checked_at = now() - interval '1 hour'")
        sweep(h)
    errored = h.app.db.one("SELECT status, status_reason FROM watchers WHERE id != %s", (wid,))
    assert errored and errored["status"] == "ERROR" and "5 times" in errored["status_reason"]
    assert json.loads(mcp.tool("list_watchers")[0])["watchers"][0]["status"] in (
        "ERROR",
        "CANCELLED",
    )


def test_disconnected_connection_blocks_tools(h: Harness) -> None:
    user_id = connect_kite(h)
    h.app.db.execute(
        "UPDATE broker_connections SET status = 'disconnected', access_token_enc = NULL WHERE user_id = %s",
        (user_id,),
    )
    mcp = Mcp(h.base, oauth_login(h))
    assert json.loads(mcp.tool("auth_status")[0])["broker"] == "disconnected"
    text, is_error = mcp.tool("run_python", code="print(1)")
    assert not is_error and "disconnected" in text and "https://web.example" in text


def test_refresh_token_rotation(h: Harness) -> None:
    web = httpx.Client(base_url=h.base, follow_redirects=False, timeout=10)
    first = oauth_tokens(h)
    assert Mcp(h.base, first["access_token"]).tools()
    r = web.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "client_id": first["client_id"],
        },
    )
    assert r.status_code == 200, r.text
    second = r.json()
    assert second["access_token"] != first["access_token"]
    assert Mcp(h.base, second["access_token"]).tools()
    stale = httpx.post(
        f"{h.base}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={
            "Authorization": f"Bearer {first['access_token']}",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert stale.status_code == 401
    replay = web.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "client_id": first["client_id"],
        },
    )
    assert replay.status_code == 400
