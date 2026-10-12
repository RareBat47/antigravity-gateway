#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.config/systemd/user"

mkdir -p "${TARGET_DIR}"
cp "${SCRIPT_DIR}/antigravity-gateway.service" "${TARGET_DIR}/antigravity-gateway.service"

systemctl --user daemon-reload
systemctl --user enable antigravity-gateway
systemctl --user restart antigravity-gateway
loginctl enable-linger "${USER}"

echo "[SUCCESS] Antigravity Gateway is enabled as a 24/7 persistent background service."
echo "Status check: systemctl --user status antigravity-gateway"
