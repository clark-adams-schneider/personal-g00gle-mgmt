from enum import Enum
from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GoogleOAuthScope(str, Enum):
    DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
    SPREADSHEETS = "https://www.googleapis.com/auth/spreadsheets"


class GoogleApiName(str, Enum):
    DRIVE = "drive"
    GMAIL = "gmail"
    DOCS = "docs"
    SLIDES = "slides"
    EARTH = "earth"
    NEWS = "news"
    TRANSLATE = "translate"


def get_google_service(
    api_name: GoogleApiName,
    api_version: str,
    client_secrets_path: Path,
    token_path: Path,
    scopes: List[GoogleOAuthScope],
):
    """
    Generic Google API service builder with OAuth2 caching.
    """
    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_path), [s.value for s in scopes]
            )
        except Exception as e:
            print(f"Error loading token from {token_path}: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), [s.value for s in scopes]
            )
            creds = flow.run_local_server(port=0)
        with token_path.open("w") as token_file:
            token_file.write(creds.to_json())

    return build(api_name, api_version, credentials=creds)
