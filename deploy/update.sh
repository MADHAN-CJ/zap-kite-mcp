#!/usr/bin/env bash
# Redeploy the latest origin/main. Run as root on the box (npm run deploy does this over ssh).
# /opt/zap-kite-mcp is disposable: it is reset hard to origin/main; .env is git-ignored and survives.
set -euo pipefail
APP=/opt/zap-kite-mcp
export UV_PYTHON_INSTALL_DIR=/var/lib/zapkite/python
UNIT=zap-kite-mcp
PORT=$(grep '^ZAP_KITE_MCP_PORT=' "$APP/.env" | cut -d= -f2 || true)
PORT=${PORT:-8019}

git -C "$APP" fetch --quiet origin
git -C "$APP" reset --hard --quiet origin/main
chown -R zapkite:zapkite "$APP"
sudo -u zapkite -H bash -c "export UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR; cd $APP && ~/.local/bin/uv sync --no-dev --frozen"
install -m 644 "$APP/deploy/$UNIT.service" "/etc/systemd/system/$UNIT.service"
systemctl daemon-reload
systemctl restart "$UNIT"
sleep 2
systemctl is-active "$UNIT"
curl -fsS "http://127.0.0.1:$PORT/health"
echo
git -C "$APP" log -1 --format='deployed %h %s'
