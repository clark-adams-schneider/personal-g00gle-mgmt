"""MCP server exposing cs-svc-gmail-ro's recent-emails capability.

Thin adapter over `gmail_ro.client`: the REST endpoint is the canonical
implementation (see `infra/cs-svc-gmail-ro/app/main.py`), this just exposes
the same capability over MCP as a first-class entry point (CLAUDE.md Rule 7,
entry-point parity), sharing the same typed client and connection config the
CLI uses instead of reimplementing the call.
"""

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from .client import GmailRoConnection, GmailRoRecentEmailsQuery, get_recent_emails

MCP_SERVER_NAME = "cs-svc-gmail-ro"


def build_server(connection: GmailRoConnection) -> FastMCP:
    mcp = FastMCP(MCP_SERVER_NAME)

    @mcp.tool()
    def get_recent_emails_tool(
        max_results: int = 10, q: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch recent Gmail messages with sanitized headers only (From/To/Subject/Date).

        Read-only: no send/modify/trash code path exists in the underlying
        service. `q` is the Gmail search query syntax (e.g. "is:unread").
        """
        response = get_recent_emails(
            connection, GmailRoRecentEmailsQuery(maxResults=max_results, q=q)
        )
        return response.model_dump()

    return mcp
