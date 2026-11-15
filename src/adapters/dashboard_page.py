from pathlib import Path

DASHBOARD_HTML: str = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
