from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PORT = 8019
DEFAULT_PUBLIC_URL = f"http://127.0.0.1:{DEFAULT_PORT}"
MIN_SECRET_LEN = 32
SCOPE = "kite:read"


class ConfigError(RuntimeError):
    """A required setting is missing or malformed."""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError as e:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from e


def _secret(name: str) -> str:
    value = _env(name)
    if len(value) < MIN_SECRET_LEN:
        raise ConfigError(f"{name} must be set to at least {MIN_SECRET_LEN} characters")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    public_url: str
    app_url: str
    host: str
    port: int
    kite_api_key: str
    kite_api_secret: str
    kite_base_url: str
    kite_login_url: str
    session_secret: str
    creds_encryption_key: str
    resend_api_key: str
    email_from: str
    sweep_secret: str
    sweep_interval_s: int
    state_dir: Path
    script_timeout_s: int
    script_max_timeout_s: int
    max_output_bytes: int
    max_concurrent_runs: int
    call_budget: int
    watchers_max_armed: int
    watchers_min_gap_minutes: int
    dev_login_email: str
    dev_login_code: str
    risk_free_rate: str

    @property
    def mcp_url(self) -> str:
        return f"{self.public_url}/"

    @property
    def workspace_dir(self) -> Path:
        return self.state_dir / "workspace"

    @property
    def cache_dir(self) -> Path:
        return self.state_dir / "cache"


def load_settings() -> Settings:
    database_url = _env("DATABASE_URL")
    if not database_url:
        raise ConfigError("DATABASE_URL must be set")
    api_key, api_secret = _env("KITE_API_KEY"), _env("KITE_API_SECRET")
    if not api_key or not api_secret:
        raise ConfigError("KITE_API_KEY and KITE_API_SECRET must be set")
    state_dir = Path(_env("ZAP_KITE_MCP_STATE_DIR") or "~/.zap-kite-mcp").expanduser()
    return Settings(
        database_url=database_url,
        public_url=(_env("ZAP_KITE_MCP_PUBLIC_URL") or DEFAULT_PUBLIC_URL).rstrip("/"),
        app_url=(_env("ZAP_KITE_MCP_APP_URL") or "http://127.0.0.1:3019").rstrip("/"),
        host=_env("ZAP_KITE_MCP_HOST") or "127.0.0.1",
        port=_int("ZAP_KITE_MCP_PORT", DEFAULT_PORT),
        kite_api_key=api_key,
        kite_api_secret=api_secret,
        kite_base_url=(_env("KITE_BASE_URL") or "https://api.kite.trade").rstrip("/"),
        kite_login_url=_env("KITE_LOGIN_URL") or "https://kite.zerodha.com/connect/login",
        session_secret=_secret("SESSION_SECRET"),
        creds_encryption_key=_secret("CREDS_ENCRYPTION_KEY"),
        resend_api_key=_env("RESEND_API_KEY"),
        email_from=_env("EMAIL_FROM") or "Zap <no-reply@example.com>",
        sweep_secret=_env("SWEEP_SECRET"),
        sweep_interval_s=_int("SWEEP_INTERVAL_SECONDS", 60),
        state_dir=state_dir,
        script_timeout_s=_int("SCRIPT_TIMEOUT_SECONDS", 60),
        script_max_timeout_s=_int("SCRIPT_MAX_TIMEOUT_SECONDS", 180),
        max_output_bytes=_int("SCRIPT_MAX_OUTPUT_BYTES", 64 * 1024),
        max_concurrent_runs=_int("MAX_CONCURRENT_RUNS", 2),
        call_budget=_int("ZAPKITE_CALL_BUDGET", 40),
        watchers_max_armed=_int("WATCHERS_MAX_ARMED", 10),
        watchers_min_gap_minutes=_int("WATCHERS_MIN_GAP_MINUTES", 15),
        dev_login_email=_env("DEV_LOGIN_EMAIL").lower(),
        dev_login_code=_env("DEV_LOGIN_CODE"),
        risk_free_rate=_env("ZAPKITE_RISK_FREE_RATE"),
    )
