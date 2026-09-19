#!/usr/bin/env bash
# ==============================================================================
# Antigravity Gateway — Backup Script
# ==============================================================================
set -euo pipefail

INSTALL_DIR="${1:-/opt/antigravity-gateway}"
BACKUP_DEST="${2:-/var/backups/antigravity}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="antigravity_backup_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DEST"

echo "Creating backup of Antigravity Gateway state..."
cd "$INSTALL_DIR"

tar -czf "${BACKUP_DEST}/${ARCHIVE_NAME}" \
    --exclude="data/*.db-journal" \
    --exclude="data/*.db-wal" \
    --exclude="data/*.db-shm" \
    data/ .env config.yaml 2>/dev/null || tar -czf "${BACKUP_DEST}/${ARCHIVE_NAME}" data/ .env 2>/dev/null

chmod 600 "${BACKUP_DEST}/${ARCHIVE_NAME}"
echo "✓ Backup saved to: ${BACKUP_DEST}/${ARCHIVE_NAME}"
