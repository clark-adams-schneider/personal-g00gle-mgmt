"""cs-svc-gmail-ro: read-only Gmail BFF proxy.

Structural read-only guarantee: this module only ever calls
`users().messages().list` and `users().messages().get` against the Gmail
API. There is no code path capable of `send`, `modify`, `trash`, or any
other mutating call, and the OAuth credential loaded here is never
returned to a caller.
"""

import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cs-svc-gmail-ro")

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SANITIZED_HEADERS = ("From", "To", "Subject", "Date")

GCP_PROJECT = os.environ["GCP_PROJECT"]
TOKEN_SECRET_NAME = os.environ.get("TOKEN_SECRET_NAME", "cs-svc-gmail-ro-token")
TOKEN_SECRET_VERSION = os.environ.get("TOKEN_SECRET_VERSION", "latest")

_credentials: Optional[Credentials] = None

app = FastAPI(
    title="cs-svc-gmail-ro",
    description="Cryptographically enforced read-only Gmail BFF proxy",
)


def _secret_version_path() -> str:
    return f"projects/{GCP_PROJECT}/secrets/{TOKEN_SECRET_NAME}/versions/{TOKEN_SECRET_VERSION}"


def _load_credentials_from_secret_manager() -> Credentials:
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(name=_secret_version_path())
    payload = json.loads(response.payload.data.decode("utf-8"))
    return Credentials.from_authorized_user_info(payload, scopes=[GMAIL_READONLY_SCOPE])


def _get_credentials() -> Credentials:
    global _credentials
    if _credentials is None:
        _credentials = _load_credentials_from_secret_manager()
    if not _credentials.valid:
        if _credentials.expired and _credentials.refresh_token:
            _credentials.refresh(GoogleAuthRequest())
        else:
            raise RuntimeError(
                "Stored Gmail credential is invalid and cannot be refreshed."
            )
    return _credentials


def _gmail_service():
    return build("gmail", "v1", credentials=_get_credentials(), cache_discovery=False)


def _sanitize_message(raw: dict) -> dict:
    headers = {
        header["name"]: header["value"]
        for header in raw.get("payload", {}).get("headers", [])
        if header["name"] in SANITIZED_HEADERS
    }
    return {
        "id": raw.get("id"),
        "threadId": raw.get("threadId"),
        "snippet": raw.get("snippet"),
        "labelIds": raw.get("labelIds", []),
        "headers": headers,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/emails/recent")
def get_recent_emails(
    maxResults: int = Query(10, ge=1, le=50),
    q: Optional[str] = Query(None, max_length=256),
):
    try:
        service = _gmail_service()
        list_response = (
            service.users()
            .messages()
            .list(userId="me", maxResults=maxResults, q=q)
            .execute()
        )
        messages = []
        for entry in list_response.get("messages", []):
            raw = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=entry["id"],
                    format="metadata",
                    metadataHeaders=list(SANITIZED_HEADERS),
                )
                .execute()
            )
            messages.append(_sanitize_message(raw))
        return {
            "resultSizeEstimate": list_response.get(
                "resultSizeEstimate", len(messages)
            ),
            "messages": messages,
        }
    except HttpError as exc:
        logger.exception("Gmail API error")
        raise HTTPException(status_code=502, detail="Upstream Gmail API error") from exc
