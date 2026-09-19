"""Embedded Web Dashboard module."""

import os
from pathlib import Path

DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"


def get_dashboard_html() -> str:
    """Return HTML content for embedded admin dashboard."""
    if DASHBOARD_FILE.is_file():
        return DASHBOARD_FILE.read_text(encoding="utf-8")
    return "<h1>Antigravity Dashboard</h1>"
