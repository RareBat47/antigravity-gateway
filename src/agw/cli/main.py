"""Command Line Interface (agw) for Antigravity Gateway administration."""

import asyncio
import os
import sys
import webbrowser
from typing import Optional
import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agw.auth.oauth import build_auth_url, generate_pkce
from agw.config import load_config

console = Console()


def get_base_url() -> str:
    cfg = load_config()
    host = "127.0.0.1" if cfg.server.host in ("0.0.0.0", "") else cfg.server.host
    return f"http://{host}:{cfg.server.port}"


def get_headers(is_admin: bool = True) -> dict:
    cfg = load_config()
    key = cfg.security.admin_api_key if is_admin else cfg.security.gateway_api_key
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


@click.group()
def cli():
    """Antigravity Gateway CLI Administration Tool."""
    pass


# --- Accounts Group ---


@cli.group()
def accounts():
    """Manage Antigravity Google accounts."""
    pass


@accounts.command("list")
def list_accounts_cmd():
    """List all configured Antigravity accounts."""
    base = get_base_url()
    try:
        resp = httpx.get(f"{base}/admin/accounts", headers=get_headers())
        if resp.status_code != 200:
            console.print(f"[red]Error fetching accounts ({resp.status_code}): {resp.text}[/red]")
            sys.exit(1)

        data = resp.json()
        table = Table(title="Connected Antigravity Accounts", header_style="bold cyan")
        table.add_column("Account ID", style="dim")
        table.add_column("Display Name")
        table.add_column("Safe Email")
        table.add_column("Tier", style="green")
        table.add_column("Status")
        table.add_column("Enabled")
        table.add_column("Requests", justify="right")
        table.add_column("Tokens", justify="right")

        for acc in data:
            status_style = "green" if acc["status"] == "active" else "red"
            enabled_str = "[green]Yes[/green]" if acc["enabled"] else "[red]No[/red]"
            table.add_row(
                acc["id"],
                acc.get("display_name") or "-",
                acc["email_safe"],
                acc.get("tier", "unknown"),
                f"[{status_style}]{acc['status']}[/{status_style}]",
                enabled_str,
                str(acc.get("total_requests", 0)),
                f"{acc.get('total_tokens', 0):,}",
            )

        console.print(table)
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")
        sys.exit(1)


@accounts.command("login")
def login_cmd():
    """Interactive Google OAuth2 login via PKCE."""
    cfg = load_config()
    base = get_base_url()
    console.print(Panel("[bold cyan]Starting Google OAuth PKCE Login Flow[/bold cyan]"))

    try:
        resp = httpx.post(f"{base}/auth/login")
        if resp.status_code != 200:
            console.print(f"[red]Error initializing login: {resp.text}[/red]")
            sys.exit(1)

        data = resp.json()
        auth_url = data["auth_url"]
        verifier = data["code_verifier"]

        console.print("\n[yellow]Opening authorization URL in your browser...[/yellow]")
        console.print(f"[dim]{auth_url}[/dim]\n")
        webbrowser.open(auth_url)

        console.print("[bold]If automatic redirect did not complete, copy the code from the URL and paste here:[/bold]")
        code = click.prompt("Authorization Code (or press Enter if completed in browser)", default="")

        if code:
            m_resp = httpx.post(
                f"{base}/auth/manual",
                json={"code": code.strip(), "code_verifier": verifier},
            )
            if m_resp.status_code == 200:
                console.print("[green]✓ Account linked successfully![/green]")
            else:
                console.print(f"[red]Failed to link account: {m_resp.text}[/red]")
        else:
            console.print("[green]Check browser tab for confirmation.[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@accounts.command("add")
@click.option("--refresh-token", prompt=True, hide_input=True, help="OAuth Refresh Token")
@click.option("--label", prompt=True, help="Safe account identifier or label")
@click.option("--display-name", default="", help="Optional display name")
def add_account_cmd(refresh_token: str, label: str, display_name: str):
    """Add an account manually using an existing OAuth refresh token."""
    base = get_base_url()
    try:
        resp = httpx.post(
            f"{base}/admin/accounts",
            headers=get_headers(),
            json={
                "refresh_token": refresh_token,
                "label": label,
                "display_name": display_name or label,
            },
        )
        if resp.status_code == 200:
            res = resp.json()
            console.print(f"[green]✓ Account '{label}' added successfully! (ID: {res['account']['account_id']})[/green]")
        else:
            console.print(f"[red]Failed to add account ({resp.status_code}): {resp.text}[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@accounts.command("remove")
@click.argument("account_id")
def remove_account_cmd(account_id: str):
    """Delete an account by its ID."""
    base = get_base_url()
    try:
        resp = httpx.delete(f"{base}/admin/accounts/{account_id}", headers=get_headers())
        if resp.status_code == 200:
            console.print(f"[green]✓ Account '{account_id}' removed.[/green]")
        else:
            console.print(f"[red]Failed: {resp.text}[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@accounts.command("enable")
@click.argument("account_id")
def enable_account_cmd(account_id: str):
    """Enable a previously disabled account."""
    base = get_base_url()
    try:
        resp = httpx.post(f"{base}/admin/accounts/{account_id}/enable", headers=get_headers())
        if resp.status_code == 200:
            console.print(f"[green]✓ Account '{account_id}' enabled.[/green]")
        else:
            console.print(f"[red]Failed: {resp.text}[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@accounts.command("disable")
@click.argument("account_id")
def disable_account_cmd(account_id: str):
    """Disable an account from receiving requests."""
    base = get_base_url()
    try:
        resp = httpx.post(f"{base}/admin/accounts/{account_id}/disable", headers=get_headers())
        if resp.status_code == 200:
            console.print(f"[yellow]✓ Account '{account_id}' disabled.[/yellow]")
        else:
            console.print(f"[red]Failed: {resp.text}[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@accounts.command("refresh")
@click.argument("account_id", required=False)
def refresh_account_cmd(account_id: Optional[str]):
    """Force token refresh for an account or all accounts."""
    base = get_base_url()
    try:
        if account_id:
            resp = httpx.post(f"{base}/admin/accounts/{account_id}/refresh", headers=get_headers())
            if resp.status_code == 200:
                console.print(f"[green]✓ Account '{account_id}' token refreshed.[/green]")
            else:
                console.print(f"[red]Failed: {resp.text}[/red]")
                sys.exit(1)
        else:
            # List all accounts and refresh each
            accs = httpx.get(f"{base}/admin/accounts", headers=get_headers()).json()
            for a in accs:
                aid = a["id"]
                r = httpx.post(f"{base}/admin/accounts/{aid}/refresh", headers=get_headers())
                status = "[green]OK[/green]" if r.status_code == 200 else f"[red]FAIL ({r.status_code})[/red]"
                console.print(f"Refreshed {aid}: {status}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


# --- Quota Command ---


@cli.command("quota")
@click.option("--account", "account_id", default=None, help="Specific account ID to inspect")
def quota_cmd(account_id: Optional[str]):
    """Inspect remaining quota and reset times."""
    base = get_base_url()
    try:
        if account_id:
            resp = httpx.get(f"{base}/admin/accounts/{account_id}/quota", headers=get_headers())
            if resp.status_code != 200:
                console.print(f"[red]Failed to get quota: {resp.text}[/red]")
                sys.exit(1)
            data = resp.json()
            table = Table(title=f"Quota for Account {account_id}", header_style="bold magenta")
            table.add_column("Model ID")
            table.add_column("Family")
            table.add_column("Remaining %", justify="right")
            table.add_column("Reset Time")

            models_dict = data.get("models", {})
            for mid, mdata in models_dict.items():
                frac = mdata.get("remaining_fraction")
                pct_str = f"{int(frac*100)}%" if frac is not None else "unknown"
                table.add_row(mid, mdata.get("model_family", "-"), pct_str, str(mdata.get("reset_time") or "-"))
            console.print(table)
        else:
            # Check docs/account-status.md or status from API
            accs_resp = httpx.get(f"{base}/admin/accounts", headers=get_headers())
            if accs_resp.status_code == 200:
                accs = accs_resp.json()
                table = Table(title="Account Quotas Overview", header_style="bold magenta")
                table.add_column("Account")
                table.add_column("Display Name")
                table.add_column("Tier")
                table.add_column("Status")

                for a in accs:
                    table.add_row(
                        a["id"],
                        a.get("display_name") or "-",
                        a.get("tier", "unknown"),
                        a.get("status", "active"),
                    )
                console.print(table)
                console.print("[dim]Tip: Use 'agw quota --account <id>' for per-model breakdown.[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


# --- Models Command ---


@cli.command("models")
def models_cmd():
    """List supported models and configuration."""
    base = get_base_url()
    try:
        resp = httpx.get(f"{base}/v1/models", headers=get_headers(is_admin=False))
        if resp.status_code != 200:
            console.print(f"[red]Failed to fetch models: {resp.text}[/red]")
            sys.exit(1)
        data = resp.json()
        table = Table(title="Registered OpenAI-Compatible Models", header_style="bold blue")
        table.add_column("Model Identifier")
        table.add_column("Description")
        table.add_column("Owned By")

        for m in data.get("data", []):
            table.add_row(m["id"], m.get("description", "-"), m.get("owned_by", "-"))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


# --- Health Command ---


@cli.command("health")
def health_cmd():
    """Inspect gateway health, active cooldowns, and reliability."""
    base = get_base_url()
    try:
        resp = httpx.get(f"{base}/admin/health", headers=get_headers())
        if resp.status_code != 200:
            console.print(f"[red]Gateway unhealthy or unreachable ({resp.status_code})[/red]")
            sys.exit(1)
        data = resp.json()
        console.print(Panel(
            f"[bold green]Status: {data['status'].upper()}[/bold green]\n"
            f"Active Accounts: {data['active_accounts']} / {data['total_accounts']}\n"
            f"Active Cooldowns: {data['active_cooldowns_count']}",
            title="Gateway Health",
        ))

        acc_table = Table(title="Account Reliability Scores", header_style="bold cyan")
        acc_table.add_column("Account ID")
        acc_table.add_column("Name")
        acc_table.add_column("Health Score", justify="right")
        acc_table.add_column("Avg Latency", justify="right")

        for a in data.get("accounts", []):
            score = a.get("health_score", 100.0)
            score_color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")
            acc_table.add_row(
                a["account_id"],
                a.get("display_name") or "-",
                f"[{score_color}]{score:.1f}%[/{score_color}]",
                f"{a.get('avg_latency_ms', 0):.0f}ms",
            )
        console.print(acc_table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


# --- Test Command ---


@cli.command("test")
@click.option("--model", default="gemini-3.5-flash", help="Model to test with")
def test_cmd(model: str):
    """Execute a test completion against the gateway."""
    base = get_base_url()
    console.print(f"Sending test completion to model '[cyan]{model}[/cyan]'...")
    try:
        resp = httpx.post(
            f"{base}/v1/chat/completions",
            headers=get_headers(is_admin=False),
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Respond with the word 'PONG'."}],
            },
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            account_used = resp.headers.get("x-agw-account", "unknown")
            console.print(Panel(f"[green]Response:[/green] {content.strip()}\n[dim]Served by: {account_used}[/dim]", title="✓ Test Successful"))
        else:
            console.print(f"[red]Test failed ({resp.status_code}): {resp.text}[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")
        sys.exit(1)


# --- Logs Command ---


@cli.command("logs")
@click.option("--limit", default=10, help="Number of recent requests to display")
def logs_cmd(limit: int):
    """View recent gateway request logs."""
    base = get_base_url()
    try:
        resp = httpx.get(f"{base}/admin/usage", headers=get_headers())
        if resp.status_code == 200:
            data = resp.json()
            console.print(Panel(
                f"Total Requests: {data.get('total_requests', 0):,}\n"
                f"Total Tokens: {data.get('total_tokens', 0):,}\n"
                f"Avg Latency: {data.get('avg_latency_ms', 0):.1f}ms",
                title="Usage Summary",
            ))
        else:
            console.print(f"[red]Failed: {resp.text}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
