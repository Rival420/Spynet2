#!/usr/bin/env bash
# Install or update Spynet as a systemd service on a Raspberry Pi (or any
# Debian/Ubuntu box). Run from a checkout of the repo:
#
#     sudo ./deploy/install.sh
#
# Idempotent: re-run it after `git pull` to upgrade.
set -euo pipefail

APP_DIR=/opt/spynet
DATA_DIR=/var/lib/spynet
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE=spynet

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

echo "==> Installing system packages"
apt-get install -y -qq python3 python3-venv python3-pip rsync >/dev/null

echo "==> Creating service user and directories"
id -u spynet >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin spynet
mkdir -p "$APP_DIR" "$DATA_DIR"

if [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  echo "==> Copying code to $APP_DIR"
  rsync -a --delete \
    --exclude .git --exclude node_modules --exclude .venv --exclude '*.db*' \
    --exclude __pycache__ "$SRC_DIR/" "$APP_DIR/"
fi

# Keep an old database from the pre-2026 layout if one is lying around.
if [[ -f "$SRC_DIR/spynet.db" && ! -f "$DATA_DIR/spynet.db" ]]; then
  echo "==> Migrating existing spynet.db to $DATA_DIR"
  cp "$SRC_DIR/spynet.db" "$DATA_DIR/spynet.db"
fi

echo "==> Python environment"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "==> Dashboard"
if [[ -f "$APP_DIR/spynet/dist/index.html" ]]; then
  echo "    using prebuilt spynet/dist"
elif command -v npm >/dev/null 2>&1 && [[ "$(node -e 'process.stdout.write(String(parseInt(process.versions.node)))')" -ge 18 ]]; then
  echo "    building with $(node --version) (this takes a few minutes on a Pi)"
  (cd "$APP_DIR/spynet" && npm install --no-audit --no-fund --silent && npm run build --silent)
else
  echo "    WARNING: no spynet/dist and no Node >= 18. Build on another machine"
  echo "    with 'make build' and copy spynet/dist here, or run 'make deploy'."
fi

chown -R root:root "$APP_DIR"
chmod -R a+rX "$APP_DIR"
chown -R spynet:spynet "$DATA_DIR"
chmod 750 "$DATA_DIR"

echo "==> systemd unit"
install -m 644 "$APP_DIR/deploy/$SERVICE.service" "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable --quiet "$SERVICE"
systemctl restart "$SERVICE"
sleep 2

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if systemctl is-active --quiet "$SERVICE"; then
  echo
  echo "Spynet is running. Open http://${IP:-<pi-ip>}:5000"
  echo "Logs: journalctl -u $SERVICE -f"
else
  echo "Service failed to start. Check: journalctl -u $SERVICE -n 50" >&2
  exit 1
fi
