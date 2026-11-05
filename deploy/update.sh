#!/usr/bin/env bash
# Redeploy the latest origin/dev. Run as root on the box (npm run deploy does this over ssh).
# /opt/zap-kite-mcp is disposable: it is reset hard to origin/dev; .env is git-ignored and survives.
set -euo pipefail
# Needs bubblewrap >= 0.8.0 (--disable-userns); Ubuntu 24.04 ships 0.9.0, 22.x only 0.6.
bwrap --unshare-all --unshare-user --disable-userns --ro-bind / / /bin/true 2>/dev/null \
  || { echo "Install bubblewrap >= 0.8.0 with --disable-userns support before deploying" >&2; exit 1; }
APP=/opt/zap-kite-mcp
export UV_PYTHON_INSTALL_DIR=/var/lib/zapkite/python
UNIT=zap-kite-mcp
PORT=$(grep '^ZAP_KITE_MCP_PORT=' "$APP/.env" | cut -d= -f2 || true)
PORT=${PORT:-8019}

git -C "$APP" fetch --quiet origin
git -C "$APP" checkout --quiet -B dev origin/dev
chown -R zapkite:zapkite "$APP"
sudo -u zapkite -H bash -c "export UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR; cd $APP/mcp && ~/.local/bin/uv sync --no-dev --frozen"
install -m 644 "$APP/deploy/$UNIT.service" "/etc/systemd/system/$UNIT.service"
systemctl daemon-reload
systemctl restart "$UNIT"
# Startup includes migrations; wait for readiness rather than assuming two seconds.
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
