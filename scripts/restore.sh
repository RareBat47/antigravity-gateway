#!/usr/bin/env bash
# ==============================================================================
# Antigravity Gateway — Restore Script
# ==============================================================================
set -euo pipefail

BACKUP_ARCHIVE="${1:-}"
TARGET_DIR="${2:-/opt/antigravity-gateway}"

if [ -z "$BACKUP_ARCHIVE" ] || [ ! -f "$BACKUP_ARCHIVE" ]; then
    echo "Usage: sudo ./scripts/restore.sh <path-to-backup.tar.gz> [target_dir]" >&2
    exit 1
fi

echo "Stopping service before restoring..."
systemctl stop antigravity-gateway.service || true

echo "Restoring from $BACKUP_ARCHIVE to $TARGET_DIR..."
mkdir -p "$TARGET_DIR"
tar -xzf "$BACKUP_ARCHIVE" -C "$TARGET_DIR"

chown -R antigravity:antigravity "$TARGET_DIR" || true
chmod 700 "$TARGET_DIR/data" || true
if [ -f "$TARGET_DIR/.env" ]; then chmod 600 "$TARGET_DIR/.env"; fi

systemctl start antigravity-gateway.service || true
echo "✓ Restore completed and service restarted."
