"""Windows Standalone Application Entry Point for Antigravity Gateway / Gemini API."""

import os
import sys
import time
import threading
import webbrowser
from pathlib import Path
import uvicorn
from rich.console import Console
from rich.panel import Panel

# Ensure UTF-8 console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure working directory is executable directory or current directory
if getattr(sys, "frozen", False):
    # Running as compiled PyInstaller executable
    app_dir = Path(sys.executable).parent.resolve()
    os.chdir(app_dir)
else:
    app_dir = Path(__file__).resolve().parent.parent.parent
    os.chdir(app_dir)

# Ensure data directory exists
(app_dir / "data").mkdir(parents=True, exist_ok=True)
(app_dir / "docs").mkdir(parents=True, exist_ok=True)

from agw.config import load_config
from agw.main import create_app

console = Console()


def open_browser_delayed(url: str, delay: float = 1.5):
    """Open default web browser after server initializes."""
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def main():
    cfg = load_config()
    host = cfg.server.host
    port = cfg.server.port
    
    display_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    dashboard_url = f"http://{display_host}:{port}/admin/dashboard"
    docs_url = f"http://{display_host}:{port}/docs"
    health_url = f"http://{display_host}:{port}/health"
    api_url = f"http://{display_host}:{port}/v1"

    console.print(Panel.fit(
        f"[bold cyan]⚡ ANTIGRAVITY MULTI-ACCOUNT GATEWAY / GEMINI API ⚡[/bold cyan]\n"
        f"[dim]Autonomous Multi-Account Proxy & Web Administration[/dim]\n\n"
        f"[bold yellow]📊 Admin Dashboard :[/bold yellow] [green underline]{dashboard_url}[/green underline]\n"
        f"[bold yellow]📖 Swagger API Docs:[/bold yellow] [green underline]{docs_url}[/green underline]\n"
        f"[bold yellow]❤️  Health Check    :[/bold yellow] [green underline]{health_url}[/green underline]\n"
        f"[bold yellow]🤖 OpenAI API Base :[/bold yellow] [green underline]{api_url}[/green underline]\n\n"
        f"[dim]Opening dashboard in your default browser...[/dim]\n"
        f"[bold red]Press Ctrl+C to stop the server.[/bold red]",
        title="[bold green]Gemini API Gateway[/bold green]",
        border_style="cyan"
    ))

    # Auto-launch dashboard in browser
    open_browser_delayed(dashboard_url, delay=1.5)

    app = create_app(cfg)

    # Run uvicorn server directly with app instance
    uvconfig = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(uvconfig)
    try:
        server.run()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]Gateway stopped gracefully.[/yellow]")


if __name__ == "__main__":
    main()
