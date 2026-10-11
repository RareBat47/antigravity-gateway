#!/usr/bin/env bash
# ==============================================================================
# Antigravity Gateway — Linux Production Installation Script
# ==============================================================================
set -euo pipefail

INSTALL_DIR="/opt/antigravity-gateway"
SERVICE_USER="antigravity"
SYSTEMD_FILE="/etc/systemd/system/antigravity-gateway.service"

echo "=== Installing Antigravity Multi-Account Gateway ==="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run install.sh with sudo or as root." >&2
    exit 1
fi

# 1. Create dedicated system user if not present
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    echo "Creating system user: $SERVICE_USER..."
    useradd -r -s /bin/false -d "$INSTALL_DIR" -m "$SERVICE_USER"
fi

# 2. Copy source files to /opt/antigravity-gateway
echo "Copying application files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"

# 3. Create virtual environment
echo "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv .venv
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r requirements.txt
"$INSTALL_DIR/.venv/bin/pip" install -e .

# 4. Prepare directories and permissions
mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/docs" "$INSTALL_DIR/logs"

if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "Created $INSTALL_DIR/.env from template."
fi

# Set restrictive permissions
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR/data"
chmod 600 "$INSTALL_DIR/.env"

# 5. Install systemd service
echo "Installing systemd unit..."
cp "$INSTALL_DIR/systemd/antigravity-gateway.service" "$SYSTEMD_FILE"
systemctl daemon-reload
systemctl enable antigravity-gateway.service

echo ""
echo "=== Installation Complete! ==="
echo "1. Edit your secrets in: $INSTALL_DIR/.env"
echo "2. Start the gateway: sudo systemctl start antigravity-gateway"
echo "3. Check logs: sudo journalctl -u antigravity-gateway -f"
echo "4. Admin dashboard: http://YOUR-IP:8999/admin/dashboard"
