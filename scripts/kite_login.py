"""Obtain a Kite access token for local development without the web app.

Usage: uv run python scripts/kite_login.py
Prints the Kite login URL; after logging in, paste the URL Zerodha redirected you to (or just
its request_token). The script exchanges it and writes KITE_ACCESS_TOKEN into .env.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from live_smoke import load_env

LOGIN_URL = "https://kite.zerodha.com/connect/login"
BASE_URL = "https://api.kite.trade"


def exchange(api_key: str, api_secret: str, request_token: str) -> dict[str, str]:
    checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()
    r = httpx.post(
        f"{BASE_URL}/session/token",
        data={"api_key": api_key, "request_token": request_token, "checksum": checksum},
        headers={"X-Kite-Version": "3"},
        timeout=20,
    )
    body = r.json()
    if r.status_code != 200 or body.get("status") != "success":
        raise SystemExit(f"token exchange failed: {r.status_code} {body}")
    data: dict[str, str] = body["data"]
    return data


def write_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    kept = [ln for ln in lines if not ln.startswith(f"{key}=")]
    kept.append(f"{key}={value}")
    path.write_text("\n".join(kept) + "\n")


def main() -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_env(env_path)
    api_key, api_secret = os.environ.get("KITE_API_KEY", ""), os.environ.get("KITE_API_SECRET", "")
    if not api_key or not api_secret:
        print("KITE_API_KEY and KITE_API_SECRET must be set in .env")
        return 2
    print(f"1. Open:  {LOGIN_URL}?v=3&api_key={api_key}")
    print("2. Log in. Zerodha redirects to the app's redirect URL (a 404 there is fine).")
    raw = input("3. Paste the redirected URL or the request_token: ").strip()
    token = raw
    if raw.startswith("http"):
        token = parse_qs(urlparse(raw).query).get("request_token", [""])[0]
    if not token:
        print("no request_token found")
        return 2
    data = exchange(api_key, api_secret, token)
    write_env(env_path, "KITE_ACCESS_TOKEN", data["access_token"])
    print(f"connected as {data.get('user_id')} ({data.get('user_name')}); token saved to .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
