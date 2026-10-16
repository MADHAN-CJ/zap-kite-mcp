#!/usr/bin/env bash
# One-time setup on the shared uat box (run as root): service user, clone, venv, state dir,
# systemd unit, .env skeleton with fresh secrets, nginx reminder. Re-runnable.
set -euo pipefail
APP=/opt/zap-kite-mcp
export UV_PYTHON_INSTALL_DIR=/var/lib/zapkite/python
REPO=https://github.com/MADHAN-CJ/zap-kite-mcp.git
USER_NAME=zapkite
STATE=/var/lib/zapkite
NGINX_SITE=/etc/nginx/sites-available/staging-kite-mcp
PUBLIC_URL=${ZAP_KITE_MCP_PUBLIC_URL:-https://staging-kite-mcp.slash.markets}
APP_URL=${ZAP_KITE_MCP_APP_URL:-https://staging-kite-app.slash.markets}

id -u "$USER_NAME" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$USER_NAME"
mkdir -p "$STATE" && chown "$USER_NAME:$USER_NAME" "$STATE" && chmod 750 "$STATE"

if [ ! -d "$APP/.git" ]; then
  git clone --quiet --branch dev "$REPO" "$APP"
fi
git config --global --add safe.directory "$APP"
chown -R "$USER_NAME:$USER_NAME" "$APP"

sudo -u "$USER_NAME" -H bash -c 'command -v ~/.local/bin/uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh'
mkdir -p "$UV_PYTHON_INSTALL_DIR" && chown "$USER_NAME:$USER_NAME" "$UV_PYTHON_INSTALL_DIR"
sudo -u "$USER_NAME" -H bash -c "export UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR; cd $APP/mcp && ~/.local/bin/uv python install 3.12 && ~/.local/bin/uv sync --no-dev --frozen"

if [ ! -f "$APP/.env" ]; then
  cat > "$APP/.env" <<ENV
KITE_API_KEY=
KITE_API_SECRET=
DATABASE_URL=
ZAP_KITE_MCP_PUBLIC_URL=$PUBLIC_URL
ZAP_KITE_MCP_APP_URL=$APP_URL
ZAP_KITE_MCP_HOST=127.0.0.1
ZAP_KITE_MCP_PORT=8019
ZAP_KITE_MCP_STATE_DIR=$STATE
SESSION_SECRET=$(openssl rand -hex 32)
CREDS_ENCRYPTION_KEY=$(openssl rand -hex 32)
SWEEP_SECRET=$(openssl rand -hex 24)
RESEND_API_KEY=
EMAIL_FROM=Slash Markets <login-link@codeongrass.com>
ENV
  chown "$USER_NAME:$USER_NAME" "$APP/.env" && chmod 600 "$APP/.env"
  echo "wrote $APP/.env; fill KITE_API_KEY, KITE_API_SECRET, DATABASE_URL, RESEND_API_KEY"
fi

install -m 644 "$APP/deploy/zap-kite-mcp.service" /etc/systemd/system/zap-kite-mcp.service
systemctl daemon-reload

if [ ! -f "$NGINX_SITE" ]; then
  echo "nginx: configure staging-kite-mcp.slash.markets as a dedicated HTTP site, issue its certificate with certbot --nginx, then use $APP/deploy/staging-nginx.conf"
fi

if grep -q '^KITE_API_KEY=.\+' "$APP/.env" && grep -q '^DATABASE_URL=.\+' "$APP/.env"; then
  systemctl enable --now zap-kite-mcp
  sleep 2 && systemctl is-active zap-kite-mcp && curl -fsS http://127.0.0.1:8019/health && echo
else
  echo "fill $APP/.env, then: systemctl enable --now zap-kite-mcp"
fi
