"""
server.py

THIS is the actual MCP server. Everything above the line marked "MCP part
starts here" is just normal Python -- no different from a regular script.
The MCP part is deliberately small: it's a thin wrapper that tells Claude
(or any other MCP-compatible AI) "here is a tool you can call, here's its
name, here's what it needs, here's what it gives back."

To run this yourself:
    pip install "mcp[cli]"
    python server.py

Once it's running, an MCP client (like Claude Desktop, or eventually this
Cowork session once it's deployed and connected) can call the
get_daily_cash_sheet tool the same way it calls any other connected tool
-- Google Calendar, Slack, whatever you've connected before.
"""

from mcp.server.fastmcp import FastMCP
from cash_sheet_logic import build_cash_sheet, format_cash_sheet_text

# --- MCP part starts here ---

# This name ("Cash Sheet") is what shows up when this server is listed
# as a connector -- same idea as seeing "Google Calendar" in your tools.
mcp = FastMCP("Cash Sheet")


@mcp.tool()
def get_daily_cash_sheet(date: str) -> str:
    """
    Build the merged Cash Sheet for a given day by combining Toast's
    export with the nightly exception log.

    Args:
        date: The day to build the sheet for, formatted YYYY-MM-DD
              (e.g. "2026-09-15").
    """
    sheet = build_cash_sheet(date)
    return format_cash_sheet_text(sheet)


# This is the part that starts the server listening for an MCP client
# to connect. "stdio" is the simplest transport -- it just means the
# server talks over standard input/output, which is how tools like
# Claude Desktop connect to a locally-running MCP server. When we move
# this to the cloud later, we'll switch this one line to an HTTP-based
# transport so it can run as a hosted service instead of only locally.
if __name__ == "__main__":
    mcp.run(transport="stdio")
