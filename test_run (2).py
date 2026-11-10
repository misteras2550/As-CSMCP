"""
test_run.py

This does NOT use MCP at all -- it just calls the same logic the MCP tool
calls, directly, so you can see the output without needing a full MCP
client hooked up. This is the fastest way to check "does the logic work"
before worrying about the MCP plumbing at all.

Run it with:
    python test_run.py
"""

from cash_sheet_logic import build_cash_sheet, format_cash_sheet_text

sheet = build_cash_sheet("2026-09-15")
print(format_cash_sheet_text(sheet))
