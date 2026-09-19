# Security Policy and Architecture — Antigravity Gateway

This document details the security posture, authentication barriers, data protection mechanisms, and privacy guarantees implemented in the Antigravity Multi-Account Gateway.

---

## 1. Core Security Guarantees

1. **Zero Secret Leakage**:
   - The application enforces a custom logging filter (`RedactingLogger`) on Python's root logger.
   - Any log string matching patterns for `Bearer <token>`, `refresh_token`, `access_token`, `client_secret`, authorization `code=`, or `code_verifier` is automatically redacted before writing to stdout or disk.
2. **Encrypted Token Vault**:
   - OAuth refresh tokens are **never** stored in plaintext.
   - Refresh tokens are encrypted using **Fernet AES-256-GCM** and saved in an isolated file (`data/vault.enc`).
   - The encryption key is read from the `GATEWAY_ENCRYPTION_KEY` environment variable or auto-generated at `data/vault.key` with strict `0600` filesystem permissions.
3. **Decoupled Metadata Database**:
   - The SQLite database (`data/gateway.db`) stores only anonymized/safe identifiers (masked emails like `use***@gmail.com`, internal account IDs like `acc-12ab34cd`, project IDs, and request metrics).
4. **Legitimate OAuth Authorization**:
   - The gateway uses standard Google OAuth 2.0 PKCE (RFC 7636) authorization for accounts authorized by the user.
   - No token forging, header manipulation to defeat quotas, or unauthorized provider circumvention is performed.

---

## 2. Authentication Boundaries

The gateway enforces two separate cryptographic bearer token boundaries:

```
[ Client Request ] ──► Header: "Authorization: Bearer GATEWAY_API_KEY"
                   ├──► GET  /v1/models
                   └──► POST /v1/chat/completions

[ Admin Request ]  ──► Header: "Authorization: Bearer ADMIN_API_KEY"
                   ├──► GET    /admin/accounts
                   ├──► POST   /admin/accounts
                   ├──► DELETE /admin/accounts/{id}
                   ├──► POST   /admin/accounts/{id}/refresh
                   ├──► GET    /admin/health
                   └──► GET    /admin/usage
```

- Public endpoints (`/health` and `/`) return only high-level health information without sensitive metadata.
- Unauthenticated requests to `/v1/*` or `/admin/*` receive HTTP 401 Unauthorized.

---

## 3. Remote Server & Azure VM Hardening

When deploying on a remote Azure VM or exposing the service over the internet:

1. **Never bind unauthenticated ports to `0.0.0.0` on the public internet.**
2. **Use a Secure Tunnel**:
   - Recommended: **Cloudflare Tunnel** (`cloudflared`) or **Tailscale** private mesh network.
   - Alternative: SSH reverse port forwarding (`ssh -R 8999:localhost:8999 user@azure-vm`).
3. **Run as Dedicated Non-Root User**:
   - The provided `install.sh` and `antigravity-gateway.service` configure a dedicated unprivileged user `antigravity` with restricted filesystem privileges (`ProtectSystem=strict`, `PrivateTmp=true`).
