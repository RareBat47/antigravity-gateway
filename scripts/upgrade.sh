#!/usr/bin/env bash
# ==============================================================================
# Antigravity Gateway — Upgrade Script
# ==============================================================================
set -euo pipefail

INSTALL_DIR="/opt/antigravity-gateway"

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run upgrade.sh with sudo or as root." >&2
    exit 1
fi

echo "=== Upgrading Antigravity Gateway ==="
systemctl stop antigravity-gateway.service

cd "$INSTALL_DIR"
git pull origin main || true

"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r requirements.txt
"$INSTALL_DIR/.venv/bin/pip" install -e .

systemctl start antigravity-gateway.service
echo "✓ Upgrade complete and service restarted."
