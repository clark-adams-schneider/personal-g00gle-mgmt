"""Typed client for cs-svc-gmail-ro, shared by the CLI and MCP entry points.

Mints a short-lived OIDC ID token by impersonating the deployed service's
invoker service account (see infra/cs-svc-gmail-ro/README.md "Calling the
service locally") and calls the read-only emails endpoint. This module never
touches the underlying Gmail OAuth credential, which stays inside Secret
Manager and the Cloud Run runtime identity - it only ever talks to the
service's own REST API, the same as `infra/cs-svc-gmail-ro/scripts/local_client.py`.
"""

from typing import Dict, List, Optional

import google.auth
import google.auth.impersonated_credentials
import google.auth.transport.requests
import requests
from pydantic import BaseModel, Field, HttpUrl

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
RECENT_EMAILS_PATH = "/api/v1/emails/recent"
REQUEST_TIMEOUT_SECONDS = 30


class GmailRoConnection(BaseModel):
    service_url: HttpUrl
    invoker_sa_email: str


class GmailRoRecentEmailsQuery(BaseModel):
    maxResults: int = Field(default=10, ge=1, le=50)
    q: Optional[str] = Field(default=None, max_length=256)


class GmailRoMessage(BaseModel):
    id: str
    threadId: str
    snippet: Optional[str] = None
    labelIds: List[str] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)


class GmailRoRecentEmailsResponse(BaseModel):
    resultSizeEstimate: int
    messages: List[GmailRoMessage]


def mint_id_token(service_account_email: str, audience: str) -> str:
    source_credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    target_credentials = google.auth.impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=service_account_email,
        target_scopes=[CLOUD_PLATFORM_SCOPE],
    )
    id_token_credentials = google.auth.impersonated_credentials.IDTokenCredentials(
        target_credentials, target_audience=audience, include_email=True
    )
    id_token_credentials.refresh(google.auth.transport.requests.Request())
    return id_token_credentials.token


def get_recent_emails(
    connection: GmailRoConnection, query: GmailRoRecentEmailsQuery
) -> GmailRoRecentEmailsResponse:
    base_url = str(connection.service_url).rstrip("/")
    id_token = mint_id_token(connection.invoker_sa_email, base_url)

    params = {"maxResults": query.maxResults}
    if query.q:
        params["q"] = query.q

    response = requests.get(
        f"{base_url}{RECENT_EMAILS_PATH}",
        headers={"Authorization": f"Bearer {id_token}"},
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return GmailRoRecentEmailsResponse.model_validate(response.json())
