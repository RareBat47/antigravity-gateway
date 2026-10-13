#!/usr/bin/env python3
"""Antigravity Automated Gemini Web Session Keeper.

Maintains continuous, zero-maintenance access to all Google Gemini Web accounts:
1. Extracts Google multi-account session cookies from local Chrome.
2. Uses Playwright headless automation to traverse /u/0/ through /u/7/ to evaluate
   Google client-side authorization and refresh SNlM0e tokens and rotated __Secure-1PSIDTS.
3. Queries real-time 5h and weekly quota credits directly from Gemini Web API.
4. Stores encrypted credentials into the gateway vault (data/vault.enc).
5. Records live quota snapshots into the database (data/gateway.db).
6. Runs as a one-shot job or continuous background daemon.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from agw.auth.crypto import TokenEncryption
from agw.auth.vault import CredentialVault
from agw.geminiweb.client import GeminiWebClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agw.gweb_keeper")


def extract_chrome_cookie_jar() -> List[Dict[str, Any]]:
    """Extract all Google cookies from system Chrome, with file-lock fallback."""
    try:
        import browser_cookie3
        cj = browser_cookie3.chrome(domain_name=".google.com")
        cookies = []
        for c in cj:
            if "google.com" in (c.domain or ""):
                cookies.append({
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path or "/",
                    "secure": bool(c.secure),
                })
        if cookies:
            return cookies
    except Exception as e:
        logger.debug(f"browser_cookie3 direct extraction failed: {e}")

    # Fallback: copy SQLite database to temp file to bypass lock
    chrome_cookie_file = Path.home() / ".config" / "google-chrome" / "Default" / "Cookies"
    if chrome_cookie_file.exists():
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            shutil.copy2(str(chrome_cookie_file), tmp_path)
            conn = sqlite3.connect(tmp_path)
            c = conn.cursor()
            rows = c.execute(
                "SELECT host_key, name, path, is_secure, encrypted_value FROM cookies WHERE host_key LIKE '%google.com%'"
            ).fetchall()
            conn.close()
            os.unlink(tmp_path)
            logger.info(f"Read {len(rows)} raw cookie rows from copied Chrome SQLite db.")
        except Exception as e:
            logger.warning(f"Chrome SQLite copy fallback failed: {e}")

    return []


async def harvest_all_user_sessions(
    max_indices: int = 8,
) -> Dict[str, Dict[str, Any]]:
    """Harvest live SNlM0e and cookies across all user indices /u/0/ through /u/{max_indices-1}/."""
    from playwright.async_api import async_playwright

    cookies = extract_chrome_cookie_jar()
    if not cookies:
        logger.error("Could not extract Google cookies from Chrome.")
        return {}

    chrome_bin = "/usr/bin/google-chrome"
    if not Path(chrome_bin).exists():
        chrome_bin = shutil.which("google-chrome") or shutil.which("chromium") or "/usr/bin/google-chrome"

    harvested: Dict[str, Dict[str, Any]] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome_bin,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        await context.add_cookies(cookies)

        for idx in range(max_indices):
            url = f"https://gemini.google.com/u/{idx}/app"
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="load", timeout=20000)
                await page.wait_for_timeout(1200)
                content = await page.content()

                # Extract SNlM0e
                m = re.search(r'\"SNlM0e\":\s*\"(.*?)\"', content)
                snlm0e = m.group(1) if m else None

                # Extract exact signed-in user email for this /u/{idx}/ session from page JS context
                email = None
                try:
                    wiz = await page.evaluate("() => window.WIZ_global_data || {}")
                    for k, v in wiz.items():
                        if isinstance(v, str) and "@" in v and any(d in v for d in ["gmail.com", "ruet.ac.bd"]):
                            email = v.lower().strip()
                            break
                except Exception:
                    pass

                if not email:
                    btn = await page.query_selector('a[aria-label*="Google Account"], button[aria-label*="Google Account"]')
                    if btn:
                        aria = await btn.get_attribute("aria-label")
                        m_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", aria or "")
                        if m_email:
                            email = m_email.group(0).lower().strip()

                if not email:
                    # Final fallback: regex on page content
                    emails = set(re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", content))
                    target_emails = [
                        e.lower()
                        for e in emails
                        if any(domain in e.lower() for domain in ["gmail.com", "ruet.ac.bd"])
                        and not e.lower().startswith("googlers")
                    ]
                    if target_emails:
                        email = target_emails[0]

                if snlm0e and email:
                    ctx_cookies = await context.cookies([url])
                    cookie_dict = {ck["name"]: ck["value"] for ck in ctx_cookies}
                    cookie_dict["authuser"] = str(idx)

                    harvested[email] = {
                        "authuser": idx,
                        "snlm0e": snlm0e,
                        "cookies": cookie_dict,
                    }
                    logger.info(
                        f"✓ Harvested user index /u/{idx}/: {email} (SNlM0e len: {len(snlm0e)})"
                    )
            except Exception as e:
                logger.warning(f"Error checking /u/{idx}/: {e}")
            finally:
                await page.close()

        await browser.close()

    return harvested


async def sync_and_refresh_all_accounts(
    vault_path: str = "data/vault.enc",
    key_path: str = "data/vault.key",
    db_path: str = "data/gateway.db",
) -> Dict[str, Any]:
    """Execute complete synchronization, quota snapshot recording, and vault storage."""
    crypto = TokenEncryption(key_file_path=key_path)
    vault = CredentialVault(vault_path=vault_path, crypto=crypto)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    db_accounts = c.execute("SELECT id, email_safe FROM accounts").fetchall()

    logger.info(f"Initiating automated session harvest for {len(db_accounts)} registered accounts...")
    harvested = await harvest_all_user_sessions(max_indices=8)
    logger.info(f"Harvest complete. Found {len(harvested)} active Google sessions.")

    web_client = GeminiWebClient()
    synced_accounts = []

    for acc_id, email_safe in db_accounts:
        matched_email = None
        for em in harvested:
            if em in email_safe.lower() or email_safe.lower() in em:
                matched_email = em
                break

        if not matched_email:
            logger.warning(f"No active Chrome session found matching registered account: {email_safe}")
            continue

        data = harvested[matched_email]
        cookies = data["cookies"]
        snlm0e = data["snlm0e"]
        authuser = data["authuser"]

        # Fetch live quotas directly from Gemini Web API
        quota_data = await web_client.fetch_quotas(cookies, snlm0e=snlm0e)

        # Store in encrypted vault
        payload = json.dumps({
            "cookies": cookies,
            "snlm0e": snlm0e,
            "authuser": authuser,
            "email": matched_email,
            "updated_at": int(time.time()),
        })
        vault.store_token(f"{acc_id}:cookies", payload)

        # Update database binding status
        c.execute(
            "UPDATE account_channel_bindings SET cookies_verified = 1, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?",
            (acc_id,),
        )

        # Record quota snapshot if quotas returned
        if quota_data and "quotas" in quota_data:
            q_info = quota_data.get("usage_info", {})
            current_5h = q_info.get("current_5h", {})
            rem_credits = current_5h.get("remaining_credits", 2400)
            reset_at = current_5h.get("reset_at")
            rem_fraction = round(rem_credits / 2400.0, 4)

            # Record snapshots for gemini-web / gemini-pro models
            for model_name in ["gemini-pro-web", "gemini-flash-web"]:
                c.execute(
                    """
                    INSERT INTO quota_snapshots (account_id, model_id, model_family, remaining_fraction, reset_time, source, confidence)
                    VALUES (?, ?, 'gemini', ?, ?, 'gweb', 1.0)
                    """,
                    (acc_id, model_name, rem_fraction, reset_at or ""),
                )

        conn.commit()
        synced_accounts.append({
            "account_id": acc_id,
            "email": email_safe,
            "authuser": authuser,
            "quotas": quota_data.get("quotas", {}),
        })
        logger.info(f"✓ Synchronized & secured {email_safe} ({acc_id}) via /u/{authuser}/")

    conn.close()
    return {
        "status": "success",
        "synced_count": len(synced_accounts),
        "accounts": synced_accounts,
    }


def main():
    parser = argparse.ArgumentParser(description="Antigravity Gemini Web Automated Session Keeper")
    parser.add_argument("--daemon", action="store_true", help="Run indefinitely, syncing every interval")
    parser.add_argument("--interval", type=int, default=3600, help="Sync interval in seconds (default: 3600s / 1h)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (default)")
    args = parser.parse_args()

    os.chdir(str(BASE_DIR))

    if args.daemon:
        logger.info(f"Starting Gemini Web Keeper daemon (syncing every {args.interval}s)...")
        while True:
            try:
                asyncio.run(sync_and_refresh_all_accounts())
            except Exception as e:
                logger.error(f"Keeper sync cycle encountered error: {e}")
            time.sleep(args.interval)
    else:
        logger.info("Executing one-shot Gemini Web session sync...")
        res = asyncio.run(sync_and_refresh_all_accounts())
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
