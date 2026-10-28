#!/usr/bin/env bash
set -euo pipefail
# Required execution boundary; no unsandboxed fallback.
if ! command -v bwrap >/dev/null; then
  apt-get update
  apt-get install -y bubblewrap
fi
APP=/opt/zap-kite-mcp-prod
STATE=/var/lib/zapkiteprod
USER_NAME=zapkiteprod
REPO=https://github.com/MADHAN-CJ/zap-kite-mcp.git
export UV_PYTHON_INSTALL_DIR=$STATE/python
id -u "$USER_NAME" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$STATE" --shell /usr/sbin/nologin "$USER_NAME"
install -d -m 750 -o "$USER_NAME" -g "$USER_NAME" "$STATE" "$UV_PYTHON_INSTALL_DIR"
if [ ! -d "$APP/.git" ]; then
  git clone --quiet --branch prod "$REPO" "$APP"
fi
git config --global --add safe.directory "$APP"
chown -R "$USER_NAME:$USER_NAME" "$APP"
sudo -u "$USER_NAME" -H bash -c 'test -x ~/.local/bin/uv || curl --fail --silent --show-error --location https://astral.sh/uv/install.sh | sh'
sudo -u "$USER_NAME" -H bash -c "export UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR; cd $APP/mcp && ~/.local/bin/uv python install 3.12 && ~/.local/bin/uv sync --no-dev --frozen"
if [ ! -f "$APP/.env" ]; then
  umask 077
  cat > "$APP/.env" <<ENV
KITE_API_KEY=
KITE_API_SECRET=
DATABASE_URL=
ZAP_KITE_MCP_PUBLIC_URL=
ZAP_KITE_MCP_APP_URL=
ZAP_KITE_MCP_HOST=127.0.0.1
ZAP_KITE_MCP_PORT=8019
ZAP_KITE_MCP_STATE_DIR=$STATE
SESSION_SECRET=$(openssl rand -hex 32)
CREDS_ENCRYPTION_KEY=$(openssl rand -hex 32)
SWEEP_SECRET=$(openssl rand -hex 24)
RESEND_API_KEY=
EMAIL_FROM=
ENV
  chown "$USER_NAME:$USER_NAME" "$APP/.env"
  chmod 600 "$APP/.env"
fi
install -m 644 "$APP/deploy/zap-kite-mcp-prod.service" /etc/systemd/system/zap-kite-mcp-prod.service
install -d -m 700 /root/zap-kite-prod-deploy
install -m 755 "$APP/deploy/update-prod.sh" /root/zap-kite-prod-deploy/update-prod.sh
systemctl daemon-reload
echo "Production prepared, service not started. Fill $APP/.env, configure nginx/TLS, then run update-prod.sh."
