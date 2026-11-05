#!/usr/bin/env bash
# Operate the staging MCP box over SSH. The host is not committed: set DEPLOY_HOST
# (for example root@203.0.113.10) in your shell or in deploy/.host (git-ignored).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
HOST=${DEPLOY_HOST:-}
if [ -z "$HOST" ] && [ -f "$HERE/.host" ]; then
  HOST=$(tr -d '[:space:]' < "$HERE/.host")
fi
if [ -z "$HOST" ]; then
  echo "Set DEPLOY_HOST=user@host or write it to deploy/.host" >&2
  exit 2
fi

REMOTE_DIR=/root/zap-kite-mcp-deploy
case "${1:-}" in
  setup)
    scp "$HERE/setup-uat.sh" "$HERE/update.sh" "$HOST:$REMOTE_DIR/"
    ssh "$HOST" "bash $REMOTE_DIR/setup-uat.sh"
    ;;
  deploy)
    ssh "$HOST" "bash $REMOTE_DIR/update.sh"
    ;;
  logs)
    ssh "$HOST" 'journalctl -u zap-kite-mcp -n 100 --no-pager -o cat'
    ;;
  status)
    ssh "$HOST" 'systemctl status zap-kite-mcp --no-pager; curl -fsS http://127.0.0.1:8019/health; echo'
    ;;
  *)
    echo "usage: $0 setup|deploy|logs|status" >&2
    exit 2
    ;;
esac
