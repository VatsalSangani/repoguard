"""Fixture: Unicode-heavy Python file (emoji, arrows) — this exact class of
content used to crash the Ruff MCP server on Windows with
'charmap' codec can't encode character '✅' (see mcp_drivers/base_driver.py
PYTHONUTF8/PYTHONIOENCODING fix)."""
import os


def notify() -> None:
    print("✅ Done → moving to next step")
