#!/usr/bin/env bash
# ==============================================================================
# Antigravity Gateway — Uninstall Script
# ==============================================================================
set -euo pipefail

SYSTEMD_FILE="/etc/systemd/system/antigravity-gateway.service"
INSTALL_DIR="/opt/antigravity-gateway"

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run uninstall.sh with sudo or as root." >&2
    exit 1
fi

echo "Stopping service..."
systemctl stop antigravity-gateway.service || true
systemctl disable antigravity-gateway.service || true

if [ -f "$SYSTEMD_FILE" ]; then
    rm -f "$SYSTEMD_FILE"
    systemctl daemon-reload
fi

echo "Antigravity Gateway service removed."
read -p "Do you also want to delete all configuration and database files in $INSTALL_DIR? (y/N): " -r CONFIRM
if [[ $CONFIRM =~ ^[Yy]$ ]]; then
    rm -rf "$INSTALL_DIR"
    echo "Removed $INSTALL_DIR"
fi
echo "Uninstall complete."
