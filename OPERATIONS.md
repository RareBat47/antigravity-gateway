# Operations and Deployment Guide — Antigravity Gateway

This document provides operational instructions for installing, configuring, running, monitoring, and maintaining the Antigravity Multi-Account Gateway.

---

## 1. Systemd Deployment on Linux

### Automated Installation
```bash
sudo ./scripts/install.sh
```

The script will:
1. Create a dedicated system user `antigravity`.
2. Deploy the application into `/opt/antigravity-gateway`.
3. Set up a Python virtual environment and install dependencies.
4. Apply secure permissions (`0750` for application, `0700` for data, `0600` for secrets).
5. Install and enable the systemd service `/etc/systemd/system/antigravity-gateway.service`.

### Managing the Service
```bash
# Start service
sudo systemctl start antigravity-gateway

# Stop service
sudo systemctl stop antigravity-gateway

# Restart service
sudo systemctl restart antigravity-gateway

# View real-time logs
sudo journalctl -u antigravity-gateway -f
```

---

## 2. Backup and Disaster Recovery

### Creating a Backup
```bash
sudo ./scripts/backup.sh /opt/antigravity-gateway /var/backups/antigravity
```
Backs up `data/gateway.db`, `data/vault.enc`, `data/vault.key`, `.env`, and `config.yaml` to a secure timestamped tarball.

### Restoring from Backup
```bash
sudo ./scripts/restore.sh /var/backups/antigravity/antigravity_backup_YYYYMMDD_HHMMSS.tar.gz
```

---

## 3. Remote Network Architectures (Windows PC ↔ Azure VM)

### Deployment Mode A (Gateway on Local Windows PC, Hermes on Azure)
1. Run gateway locally on Windows:
   ```powershell
   d:\Unlimited\AGY\.venv\Scripts\python.exe -m uvicorn agw.main:app --host 127.0.0.1 --port 8999
   ```
2. Establish a secure tunnel via Cloudflare Tunnel or Tailscale:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8999
   ```
3. In Azure VM Hermes `config.yaml`, set `base_url: https://your-tunnel.example.com/v1`.

### Deployment Mode B (Gateway and Hermes on Azure VM)
1. Deploy gateway directly onto Azure VM via `sudo ./scripts/install.sh`.
2. Run OAuth flow via manual code exchange:
   - On Windows PC browser, open the OAuth auth URL obtained from `agw accounts login`.
   - Copy the authorization code from the browser redirect URL and paste it into the remote terminal.
3. Configure Hermes on the same VM to connect via loopback: `base_url: http://127.0.0.1:8999/v1`.
