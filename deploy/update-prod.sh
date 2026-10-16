#!/usr/bin/env bash
set -euo pipefail
APP=/opt/zap-kite-mcp-prod
export UV_PYTHON_INSTALL_DIR=/var/lib/zapkiteprod/python
UNIT=zap-kite-mcp-prod
PORT=$(grep '^ZAP_KITE_MCP_PORT=' "$APP/.env" | cut -d= -f2 || true)
PORT=${PORT:-8019}

git -C "$APP" fetch --quiet origin
git -C "$APP" checkout --quiet -B prod origin/prod
chown -R zapkiteprod:zapkiteprod "$APP"
sudo -u zapkiteprod -H bash -c "export UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR; cd $APP/mcp && ~/.local/bin/uv sync --no-dev --frozen"
sudo -u zapkiteprod -H "$APP/mcp/.venv/bin/python" - <<'PYCONFIG'
from dotenv import load_dotenv
import os
from urllib.parse import parse_qs, urlparse
from zap_kite_mcp.config import load_settings
load_dotenv("/opt/zap-kite-mcp-prod/.env", override=True)
settings = load_settings()
for key in ("ZAP_KITE_MCP_PUBLIC_URL", "ZAP_KITE_MCP_APP_URL", "RESEND_API_KEY", "EMAIL_FROM"):
    if not os.environ.get(key, "").strip():
        raise SystemExit(f"Missing production setting: {key}")
if not settings.public_url.startswith("https://") or not settings.app_url.startswith("https://"):
    raise SystemExit("Production public URLs must use HTTPS")
if settings.dev_login_email or settings.dev_login_code:
    raise SystemExit("Fixed development login is forbidden in production")
if settings.host != "127.0.0.1":
    raise SystemExit("Production MCP must bind to loopback behind nginx")
options = parse_qs(urlparse(settings.database_url).query).get("options", [])
if options != ["-csearch_path=prod"]:
    raise SystemExit("Production DATABASE_URL must select only the prod schema")
print("Production configuration validated")
PYCONFIG
install -m 644 "$APP/deploy/$UNIT.service" "/etc/systemd/system/$UNIT.service"
systemctl daemon-reload
systemctl enable "$UNIT"
systemctl restart "$UNIT"
READY=false
for attempt in {1..30}; do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/health" 2>/dev/null; then
    READY=true
    break
  fi
  sleep 1
done
if [ "$READY" != true ]; then
  systemctl status "$UNIT" --no-pager
  echo "MCP did not become healthy within the startup window" >&2
  exit 1
fi
systemctl is-active "$UNIT"
echo
git -C "$APP" log -1 --format='deployed %h %s'
