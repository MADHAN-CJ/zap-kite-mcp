from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict
from urllib.parse import parse_qs, urlencode, urlparse

import anyio
import httpx
import uvicorn
from dotenv import load_dotenv
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.routes import build_metadata, cors_middleware
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Tool as MCPTool
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from zapkite.schema import reference

from . import pages
from .broker import Broker, Creds
from .config import SCOPE, ConfigError, Settings, load_settings
from .db import Database
from .gateway import Gateway, RunTokens
from .identity import Identity, IdentityError
from .mail import Mailer
from .oauth import ALL_SCOPES, LoginExpired, OAuthProvider
from .runner import Runner
from .watchers import BROKER_REASONS, Watchers

log = logging.getLogger("zap_kite_mcp")

RULES = """Run a Python 3 script in the /markets sandbox and return what it prints. Use it for ANY question about the user's Zerodha account (positions, holdings, funds, today's orders and trades, mutual funds, GTTs) or Indian market data (prices, depth, candles, option chains, expiries, instrument lookup) across NSE/BSE stocks and indices, NFO/BFO index and stock F&O, MCX commodities and CDS/BCD currency.

HOW TO USE
- Write a COMPLETE script that does `import zapkite as z`. It is pre-installed and read-only; the user's Kite session is already wired in through a local gateway, so never ask for, print or hard-code credentials. Standard library only (json, statistics, math, datetime, csv, sqlite3, collections); pandas/numpy are NOT installed.
- Do the computation IN the script and print ONLY the compact result (a small dict via json.dumps, or a few lines). NEVER print raw candle lists, full chains or whole holdings; every printed byte lands in your context. Aggregate, filter, round.
- Scripts can create, overwrite, or delete files in the signed-in user's persistent workspace. Files persist between calls; reuse saved data when useful. This tool changes workspace state even though access to Zerodha is read-only. Overwritten or deleted files may not be recoverable.
- Access is limited to the connected user's allowed Kite read endpoints and isolated workspace; arbitrary network destinations are unavailable. Watcher creation and email scheduling use the separate create_watcher tool.
- One question may need several scripts; call this tool once per script and compose the answer yourself.
- A failing script returns its traceback as an error. Fix the code and retry; if it keeps failing, tell the user plainly what could not be done.
- Errors explain themselves: TokenExpired means the user must log in to Zerodha again in the /markets app (sessions end every morning around 06:00 IST; call auth_status for the link). DataPlanMissing means the Kite Connect app lacks the market-data plan. CallBudgetExceeded means fetch less (batch quote keys, fewer strikes, wider intervals). RateLimited means Kite throttled the shared app key; wait a few seconds.
- IDS: quote keys are "EXCHANGE:TRADINGSYMBOL" ("NSE:INFY", "NFO:NIFTY25OCT24700CE", "MCX:GOLD25DECFUT"); z.resolve_symbol("TCS" | "NIFTY" | "GOLD" | "USDINR") picks the instrument to quote or chart (stock → NSE share, index → spot index, commodity/currency → nearest future). Option underlyings are plain names (NIFTY, BANKNIFTY, FINNIFTY, SENSEX, RELIANCE, GOLD, CRUDEOIL, USDINR). Candle intervals: 1, 3, 5, 10, 15, 30, 60 minutes or day.
- Kite has NO option-chain or greeks API: z.option_chain derives the chain from the instrument dump plus ONE batched quote and computes Black-76 IV/greeks (indicative). Expired option contracts are not available; z.continuous_futures gives rolling futures history.
- Hours (Mon–Fri): NSE/BSE/NFO/BFO 09:15–15:30, CDS/BCD 09:00–17:00, MCX 09:00–23:30 IST; check z.market_status(). Off-hours, quotes are the last traded price. Money is ₹.
- The library cannot place, modify or cancel orders. If asked to trade, say so; the user trades in Kite.

zapkite REFERENCE (exact signatures; z.<name>):
"""

AUTH_STATUS_DESCRIPTION = """\
Who is signed in and whether their Zerodha (Kite) session is usable right now.

Call this when run_python reports a TokenExpired or session problem, or when the user asks
about their connection. If the session is expired or not connected, relay the returned
`message` and `appUrl`: the user logs in to Zerodha from the /markets app, never by pasting
credentials into this chat.\
"""

CREATE_WATCHER_DESCRIPTION = """\
Create a market watcher: a background check that runs a Python script on a schedule during
that market's hours (NSE/BSE/NFO/BFO 09:15–15:30, CDS 09:00–17:00, MCX 09:00–23:30 IST,
Mon–Fri) with the user's Kite data, and EMAILS the user when its condition BECOMES true.
`market` is auto-detected from the script (MCX for commodities, CDS for currency, else NSE);
pass NSE, BSE, NFO, BFO, MCX, CDS or BCD to override. Use it when the user asks to be alerted,
notified or watched about a market condition (price level, indicator cross, OI change).

`script` runs in the same sandbox as run_python (`import zapkite as z`) once every
`check_every_minutes`, so KEEP IT CHEAP: one or two API calls, no loops over option chains.
Resolve keys ONCE now and hard-code them in the script. Its LAST printed line MUST be exactly
one JSON object: {"met": <bool>, "value": <current number, optional>, "detail": "<short note, optional>"}
Print nothing after that line. The script is validated with one immediate dry run; if the
output violates the contract, creation is rejected and the output is returned so you can fix
the script and retry.

Alert semantics (explain to the user): the first check is a BASELINE and never alerts; a
condition already true at creation must become false and then true again. One email per
not-met→met transition with a minimum gap between alerts; the watcher expires after
`expires_in_days`. When the user's Zerodha session expires, watchers pause and resume by
themselves after the next login.

You canNOT modify, pause, resume or cancel watchers; the user does that on the watchers page.
ALWAYS show the user the returned pageUrl after creating one.\
"""

LIST_WATCHERS_DESCRIPTION = """\
List every watcher of the signed-in user: status (ARMED / PAUSED / ERROR / EXPIRED / CANCELLED),
condition, last checked value and detail, alert history. Read-only. Pause, resume, cancel and
edit exist only on the watchers page; send the user the pageUrl when they ask for a change.\
"""

PROFILE_DESCRIPTION = """\
The signed-in /markets account: a stable opaque id plus the user's name and email. Hosts use
it to label which account is connected; prefer auth_status for anything about the Zerodha session.\
"""

NOT_SIGNED_IN = "Not signed in. Reconnect the /markets connector in your AI assistant."


@dataclass
class App:
    settings: Settings
    db: Database
    mailer: Mailer
    identity: Identity
    broker: Broker
    tokens: RunTokens
    gateway: Gateway
    runner: Runner
    watchers: Watchers
    provider: OAuthProvider

    def close(self) -> None:
        self.db.close()


def build_app(
    settings: Settings,
    *,
    kite_transport: httpx.AsyncBaseTransport | None = None,
    mail_client: httpx.Client | None = None,
    cimd_transport: httpx.AsyncBaseTransport | None = None,
) -> App:
    db = Database(settings.database_url)
    db.migrate()
    mailer = Mailer(settings, mail_client)
    identity = Identity(settings, db, mailer)
    broker = Broker(settings, db)
    tokens = RunTokens()
    gateway_url = f"http://{settings.host}:{settings.port}"
    runner = Runner(settings, tokens, gateway_url)
    watchers_ref: list[Watchers] = []

    def on_token_expired(user_id: str) -> None:
        if broker.mark_token_expired(user_id) and watchers_ref:
            watchers_ref[0].pause_for_broker(user_id, BROKER_REASONS["token_expired"])

    gateway = Gateway(settings, broker, tokens, on_token_expired, transport=kite_transport)
    watchers = Watchers(settings, db, broker, runner, mailer, identity)
    watchers_ref.append(watchers)
    cimd_http = httpx.AsyncClient(transport=cimd_transport) if cimd_transport else None
    provider = OAuthProvider(settings, db, cimd_http)
    return App(settings, db, mailer, identity, broker, tokens, gateway, runner, watchers, provider)


def broker_message(reason: str, app_url: str) -> str:
    return {
        "not_connected": f"Zerodha is not connected to this /markets account yet. Open {app_url} and log in to Zerodha, then try again.",
        "token_expired": f"The Zerodha session has expired (Kite sessions end every morning). Open {app_url} and log in to Zerodha again, then try again.",
        "disconnected": f"Zerodha was disconnected from this /markets account. Open {app_url} and log in to Zerodha again, then try again.",
    }[reason]


class Sweeper(threading.Thread):
    def __init__(self, watchers: Watchers, interval_s: int) -> None:
        super().__init__(name="watcher-sweeper", daemon=True)
        self._watchers = watchers
        self._interval = max(5, interval_s)
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._watchers.sweep()
            except Exception:
                log.exception("sweep crashed")

    def stop(self) -> None:
        self._stop.set()


class AuthStatus(TypedDict):
    signedIn: bool
    email: str | None
    broker: str | None
    kiteUserId: str | None
    sessionExpiresAt: str | None
    appUrl: str | None
    message: str | None


class WatcherCreated(TypedDict):
    created: bool
    error: str | None
    watcher: dict[str, Any] | None


class WatcherList(TypedDict):
    watchers: list[dict[str, Any]]
    pageUrl: str
    managing: str


class Profile(TypedDict):
    id: str
    name: NotRequired[str | None]
    email: NotRequired[str | None]


OAUTH_SCHEME = {"securitySchemes": [{"type": "oauth2", "scopes": [SCOPE]}]}
PROFILE_TOOL = "profile"


class KiteServer(MCPServer[Any]):
    """MCPServer whose profile tool publishes the closed object schema ChatGPT requires."""

    async def list_tools(self) -> list[MCPTool]:
        tools = await super().list_tools()
        for tool in tools:
            if tool.name == PROFILE_TOOL and tool.output_schema is not None:
                tool.output_schema["additionalProperties"] = False
        return tools


def _is_openai_host(ctx: Context[Any, Any]) -> bool:
    meta = ctx.request_context.meta or {}
    return any(str(key).startswith("openai/") for key in meta)


def build_server(app: App) -> KiteServer:
    s = app.settings
    description = RULES + reference(brief=True)

    server = KiteServer(
        "slash-markets-kite",
        instructions=(
            "/markets Kite sandbox: answer Zerodha account and Indian market questions by writing "
            "Python against `zapkite` and running it with run_python. Print only compact results."
        ),
        auth_server_provider=app.provider,
        auth=AuthSettings(
            issuer_url=s.public_url,  # type: ignore[arg-type]
            resource_server_url=s.mcp_url,  # type: ignore[arg-type]
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=list(ALL_SCOPES), default_scopes=list(ALL_SCOPES)
            ),
            required_scopes=[SCOPE],
            validate_token_resource=False,
        ),
    )
    run_gate = anyio.Semaphore(s.max_concurrent_runs)

    def subject() -> str | None:
        access = get_access_token()
        return access.subject if access and access.subject else None

    @server.tool(
        name="run_python",
        title="Run Python against Zerodha data",
        description=description,
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=False,
        ),
        meta=OAUTH_SCHEME,
        structured_output=False,
    )
    async def run_python(code: str, ctx: Context[Any, Any], timeout_seconds: int = 0) -> str:
        """code: the complete Python script. timeout_seconds: wall-clock limit (default 60, max 180; hosts with a shorter tool timeout, such as ChatGPT, are capped at about 50 s, so keep scripts cheap)."""
        user_id = subject()
        if user_id is None:
            return NOT_SIGNED_IN
        if not code.strip():
            raise ToolError("Empty script. Pass the complete Python source in `code`.")
        creds = await anyio.to_thread.run_sync(app.broker.creds, user_id)
        if not isinstance(creds, Creds):
            return broker_message(creds, s.app_url)
        timeout = timeout_seconds or s.script_timeout_s
        if _is_openai_host(ctx):
            timeout = min(timeout, s.script_timeout_openai_s)
        async with run_gate:
            result = await anyio.to_thread.run_sync(app.runner.run, user_id, code, timeout)
        text = result.text()
        after = await anyio.to_thread.run_sync(app.broker.creds, user_id)
        if not isinstance(after, Creds):
            text += f"\n\n[{broker_message(after, s.app_url)}]"
        if result.exit_code != 0:
            raise ToolError(text)
        return text

    @server.tool(
        name="auth_status",
        title="Zerodha connection status",
        description=AUTH_STATUS_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        meta=OAUTH_SCHEME,
    )
    async def auth_status() -> AuthStatus:
        user_id = subject()
        if user_id is None:
            return AuthStatus(
                signedIn=False,
                email=None,
                broker=None,
                kiteUserId=None,
                sessionExpiresAt=None,
                appUrl=s.app_url,
                message=NOT_SIGNED_IN,
            )
        email = await anyio.to_thread.run_sync(app.identity.email_of, user_id)
        conn = await anyio.to_thread.run_sync(app.broker.connection, user_id)
        return AuthStatus(
            signedIn=True,
            email=email,
            broker=conn.status,
            kiteUserId=conn.kite_user_id,
            sessionExpiresAt=conn.expires_at.isoformat() if conn.expires_at else None,
            appUrl=s.app_url,
            message=None if conn.status == "active" else broker_message(conn.status, s.app_url),
        )

    @server.tool(
        name=PROFILE_TOOL,
        title="Signed-in /markets account",
        description=PROFILE_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        meta={**OAUTH_SCHEME, "openai/profile": True},
    )
    async def profile() -> Profile:
        user_id = subject()
        if user_id is None:
            raise ToolError(NOT_SIGNED_IN)
        email = await anyio.to_thread.run_sync(app.identity.email_of, user_id)
        conn = await anyio.to_thread.run_sync(app.broker.connection, user_id)
        return Profile(id=user_id, name=conn.user_name, email=email)

    @server.tool(
        name="create_watcher",
        title="Create a market watcher",
        description=CREATE_WATCHER_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        meta=OAUTH_SCHEME,
    )
    async def create_watcher(
        symbol: str,
        label: str,
        script: str,
        check_every_minutes: int = 1,
        expires_in_days: int = 30,
        market: str = "auto",
    ) -> WatcherCreated:
        user_id = subject()
        if user_id is None:
            return WatcherCreated(created=False, error=NOT_SIGNED_IN, watcher=None)
        async with run_gate:
            result = await anyio.to_thread.run_sync(
                app.watchers.create,
                user_id,
                symbol,
                label,
                script,
                check_every_minutes,
                expires_in_days,
                market,
            )
        if isinstance(result, str):
            return WatcherCreated(created=False, error=result, watcher=None)
        return WatcherCreated(created=True, error=None, watcher=result)

    @server.tool(
        name="list_watchers",
        title="List market watchers",
        description=LIST_WATCHERS_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        meta=OAUTH_SCHEME,
    )
    async def list_watchers() -> WatcherList:
        user_id = subject()
        if user_id is None:
            raise ToolError(NOT_SIGNED_IN)
        rows = await anyio.to_thread.run_sync(app.watchers.list_for, user_id)
        return WatcherList(
            watchers=rows, pageUrl=s.app_url, managing="page only; you cannot modify watchers"
        )

    def page(title: str, body: str, status: int = 200) -> HTMLResponse:
        return HTMLResponse(pages.shell(title, body, s.app_url), status_code=status)

    expired_page: Callable[[], HTMLResponse] = lambda: page(  # noqa: E731
        "Sign in",
        pages.error_box("Login session expired. Go back to your AI assistant and connect again."),
        400,
    )

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "service": "zap-kite-mcp", "mcp": s.mcp_url})

    @server.custom_route("/userinfo", methods=["GET", "POST"])
    async def userinfo(request: Request) -> JSONResponse:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        access = await app.provider.load_access_token(token) if token else None
        if access is None or not access.subject:
            return JSONResponse(
                {"error": "invalid_token"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )
        email = await anyio.to_thread.run_sync(app.identity.email_of, access.subject)
        return JSONResponse({"sub": access.subject, "email": email, "email_verified": True})

    @server.custom_route("/.well-known/openai-apps-challenge", methods=["GET"])
    async def openai_apps_challenge(_: Request) -> PlainTextResponse:
        if not s.openai_apps_challenge:
            return PlainTextResponse("not configured", status_code=404)
        return PlainTextResponse(s.openai_apps_challenge)

    @server.custom_route("/login", methods=["GET"])
    async def login(request: Request) -> HTMLResponse:
        txn_id = request.query_params.get("txn", "")
        t = app.provider.txn(txn_id)
        if t is None:
            return expired_page()
        hidden = pages.hidden("txn", txn_id)
        if t.get("email"):
            return page(
                "Sign in", pages.otp_form(f"{s.public_url}/login/otp", t["email"], hidden=hidden)
            )
        return page(
            "Sign in",
            pages.email_form(
                f"{s.public_url}/login/email",
                "Connect your AI assistant to your /markets account",
                "Read-only: the assistant can analyse your Zerodha account but can never trade.",
                hidden=hidden,
            ),
        )

    @server.custom_route("/login/email", methods=["POST"])
    async def login_email(request: Request) -> HTMLResponse:
        form = await request.form()
        txn_id, email = str(form.get("txn") or ""), str(form.get("email") or "")
        if app.provider.txn(txn_id) is None:
            return expired_page()
        hidden = pages.hidden("txn", txn_id)
        try:
            await anyio.to_thread.run_sync(app.identity.request_otp, email)
        except IdentityError as e:
            body = pages.email_form(
                f"{s.public_url}/login/email",
                "Connect your AI assistant to your /markets account",
                "Read-only: the assistant can analyse your Zerodha account but can never trade.",
                pages.error_box(str(e)),
                hidden,
            )
            return page("Sign in", body, 400)
        norm = email.strip().lower()
        app.provider.txn_set_email(txn_id, norm)
        return page("Sign in", pages.otp_form(f"{s.public_url}/login/otp", norm, hidden=hidden))

    @server.custom_route("/login/otp", methods=["POST"])
    async def login_otp(request: Request) -> Response:
        form = await request.form()
        txn_id, code = str(form.get("txn") or ""), str(form.get("code") or "")
        t = app.provider.txn(txn_id)
        if t is None or not t.get("email"):
            return expired_page()
        hidden = pages.hidden("txn", txn_id)
        try:
            verified = await anyio.to_thread.run_sync(app.identity.verify_otp, t["email"], code)
            redirect = app.provider.finish_login(txn_id, verified[0])
        except IdentityError as e:
            body = pages.otp_form(
                f"{s.public_url}/login/otp", t["email"], pages.error_box(str(e)), hidden
            )
            return page("Sign in", body, 400)
        except LoginExpired:
            return expired_page()
        return RedirectResponse(redirect, status_code=302)

    @server.custom_route("/kite/{path:path}", methods=["GET"])
    async def kite_gateway(request: Request) -> Response:
        return await app.gateway.handle(request)

    @server.custom_route("/internal/sweep", methods=["POST"])
    async def internal_sweep(request: Request) -> JSONResponse:
        import hmac

        secret = s.sweep_secret
        if not secret or not hmac.compare_digest(request.headers.get("x-sweep-secret", ""), secret):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = json.loads(await request.body() or b"{}")
        except ValueError:
            body = {}
        force = bool(body.get("force"))
        gap = body.get("min_gap_minutes")
        report = await anyio.to_thread.run_sync(
            app.watchers.sweep, force, int(gap) if force and gap is not None else None
        )
        return JSONResponse(report)

    return server


def transport_security(settings: Settings) -> TransportSecuritySettings:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*"]
    netloc = urlparse(settings.public_url).netloc
    if netloc and not netloc.startswith(("127.0.0.1", "localhost")):
        hosts += [netloc, f"{netloc}:*"]
        origins += [f"https://{netloc}", f"http://{netloc}"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins
    )


class _IssOnRedirect:
    """Add RFC 9207 `iss` to the error redirects the SDK's /authorize sends back to a client."""

    def __init__(self, app: ASGIApp, issuer: str, own_prefix: str) -> None:
        self._app = app
        self._issuer = issuer
        self._own_prefix = own_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_iss(message: Message) -> None:
            if message["type"] == "http.response.start" and 300 <= message["status"] < 400:
                headers = MutableHeaders(scope=message)
                location = headers.get("location")
                if (
                    location
                    and not location.startswith(self._own_prefix)
                    and "iss" not in parse_qs(urlparse(location).query)
                ):
                    joiner = "&" if "?" in location else "?"
                    headers["location"] = location + joiner + urlencode({"iss": self._issuer})
            await send(message)

        await self._app(scope, receive, send_with_iss)


def build_asgi(server: KiteServer, s: Settings) -> Starlette:
    """The Starlette app: the SDK's streamable HTTP + OAuth routes, with the authorization
    server metadata extended for ChatGPT (CIMD, public clients, `iss`, UserInfo) and `iss`
    added to authorization error redirects."""
    asgi = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        max_request_body_size=512 * 1024,
        transport_security=transport_security(s),
        host=s.host,
    )
    auth = server.settings.auth
    assert auth is not None
    base = build_metadata(
        auth.issuer_url,
        auth.service_documentation_url,
        auth.client_registration_options or ClientRegistrationOptions(),
        auth.revocation_options or RevocationOptions(),
    )
    metadata = base.model_dump(mode="json", by_alias=True, exclude_none=True)
    metadata.update(
        {
            "token_endpoint_auth_methods_supported": [
                "none",
                "client_secret_post",
                "client_secret_basic",
            ],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
            "userinfo_endpoint": f"{s.public_url}/userinfo",
        }
    )

    async def serve_metadata(_: Request) -> JSONResponse:
        return JSONResponse(metadata, headers={"Cache-Control": "public, max-age=3600"})

    for route in asgi.router.routes:
        if not isinstance(route, Route):
            continue
        if route.path == "/.well-known/oauth-authorization-server":
            route.app = cors_middleware(serve_metadata, ["GET", "OPTIONS"])
        elif route.path == "/authorize":
            route.app = _IssOnRedirect(route.app, s.public_url, f"{s.public_url}/login")
    return asgi


def serve(app: App) -> None:
    server = build_server(app)
    s = app.settings
    sweeper = Sweeper(app.watchers, s.sweep_interval_s)
    sweeper.start()
    log.info("zap-kite-mcp on http://%s:%s/  public %s", s.host, s.port, s.mcp_url)
    try:
        _run_http(server, s)
    finally:
        sweeper.stop()


def _run_http(server: KiteServer, s: Settings) -> None:
    uvicorn.run(build_asgi(server, s), host=s.host, port=s.port, log_level="info")


def _env_file(explicit: str | None) -> str:
    if explicit:
        return explicit
    for candidate in (Path(".env"), Path("..") / ".env"):
        if candidate.is_file():
            return str(candidate)
    return ".env"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zap-kite-mcp")
    parser.add_argument(
        "--env-file",
        default=None,
        help="KEY=VALUE file to load first (default: .env, then ../.env)",
    )
    parser.add_argument("--migrate", action="store_true", help="apply migrations and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_dotenv(_env_file(args.env_file), override=False)
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"zap-kite-mcp: {e}", file=sys.stderr)
        return 2
    if args.migrate:
        db = Database(settings.database_url)
        applied = db.migrate()
        db.close()
        print("applied: " + (", ".join(applied) or "nothing"))
        return 0
    app = build_app(settings)
    try:
        serve(app)
    finally:
        app.close()
    return 0
