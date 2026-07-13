# cs-svc-gmail-ro client: shared by the pg0 CLI and MCP entry points.
from .client import (
    GmailRoConnection,
    GmailRoMessage,
    GmailRoRecentEmailsQuery,
    GmailRoRecentEmailsResponse,
    get_recent_emails,
    mint_id_token,
)

__all__ = [
    "GmailRoConnection",
    "GmailRoMessage",
    "GmailRoRecentEmailsQuery",
    "GmailRoRecentEmailsResponse",
    "get_recent_emails",
    "mint_id_token",
]
