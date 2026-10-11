import os
import sys
from pathlib import Path

DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"


def get_dashboard_html() -> str:
    """Return HTML content for embedded admin dashboard."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "agw" / "dashboard" / "dashboard.html"
        if bundled.is_file():
            return bundled.read_text(encoding="utf-8")
    if DASHBOARD_FILE.is_file():
        return DASHBOARD_FILE.read_text(encoding="utf-8")
    return "<h1>Antigravity Dashboard</h1>"

