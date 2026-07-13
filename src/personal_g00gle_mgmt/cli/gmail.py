"""`pg0 gmail` - CLI entry point for cs-svc-gmail-ro.

Calls the same deployed REST API the MCP server and UTCP manual describe
(CLAUDE.md Rule 7, entry-point parity), never the Gmail API directly.
"""

from typing import Optional

import typer

from ..gmail_ro import GmailRoConnection, GmailRoRecentEmailsQuery, get_recent_emails
from ..gmail_ro.mcp_server import build_server

SERVICE_URL_ENV = "GMAIL_RO_SERVICE_URL"
INVOKER_SA_EMAIL_ENV = "GMAIL_RO_INVOKER_SA_EMAIL"

app = typer.Typer(help="Commands for cs-svc-gmail-ro, the read-only Gmail BFF proxy.")

_SERVICE_URL_OPTION = typer.Option(
    ...,
    "--service-url",
    envvar=SERVICE_URL_ENV,
    help="Cloud Run service URL, e.g. https://cs-svc-gmail-ro-xyz.a.run.app",
)
_INVOKER_SA_EMAIL_OPTION = typer.Option(
    ...,
    "--invoker-sa-email",
    envvar=INVOKER_SA_EMAIL_ENV,
    help="local-automation-client service account email to impersonate.",
)


@app.command()
def recent(
    service_url: str = _SERVICE_URL_OPTION,
    invoker_sa_email: str = _INVOKER_SA_EMAIL_OPTION,
    max_results: int = typer.Option(10, "--max-results", min=1, max=50),
    query: Optional[str] = typer.Option(
        None, "--query", "-q", help="Gmail search query (the `q` parameter)."
    ),
) -> None:
    """Fetch recent Gmail messages (sanitized headers only)."""
    connection = GmailRoConnection(
        service_url=service_url, invoker_sa_email=invoker_sa_email
    )
    response = get_recent_emails(
        connection, GmailRoRecentEmailsQuery(maxResults=max_results, q=query)
    )
    typer.echo(response.model_dump_json(indent=2))


@app.command("mcp-serve")
def mcp_serve(
    service_url: str = _SERVICE_URL_OPTION,
    invoker_sa_email: str = _INVOKER_SA_EMAIL_OPTION,
) -> None:
    """Run an MCP stdio server exposing get_recent_emails_tool."""
    connection = GmailRoConnection(
        service_url=service_url, invoker_sa_email=invoker_sa_email
    )
    build_server(connection).run()
