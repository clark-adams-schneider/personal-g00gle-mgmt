"""UTCP discovery manual for cs-svc-gmail-ro.

Models mirror the UTCP spec's own field names exactly (see CLAUDE.md Rule 3:
no invented synonyms for API-native terms) so this manual validates against
any standard UTCP client without translation. Modeled from the spec and
reference implementations at
/Users/cschneider/Desktop/growth/finances_/.references/utcp_ (utcp-specification,
python-utcp's HttpCallTemplate/Tool/UtcpManual).

This is the "no UTCP dependencies" server pattern the python-utcp README
documents: the service returns plain JSON matching the spec's shape rather
than depending on the `utcp` package itself, which is meant for clients.
"""

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

UTCP_VERSION = "1.1.3"
MANUAL_VERSION = "1.0.0"

RECENT_EMAILS_PATH = "/api/v1/emails/recent"


class UtcpAuthType(str, Enum):
    API_KEY = "api_key"


class UtcpAuthLocation(str, Enum):
    HEADER = "header"


class UtcpApiKeyAuth(BaseModel):
    """A caller-supplied bearer token, per UTCP's api_key auth shape.

    The token value is never static here: it's a short-lived OIDC ID token
    the caller mints on demand by impersonating the invoker service account
    (see README "Calling the service locally"), so `api_key` is a UTCP
    variable reference for the caller's own client config, not a secret
    embedded in this manual.
    """

    auth_type: Literal[UtcpAuthType.API_KEY] = UtcpAuthType.API_KEY
    api_key: str = "Bearer ${GMAIL_RO_ID_TOKEN}"
    var_name: str = "Authorization"
    location: UtcpAuthLocation = UtcpAuthLocation.HEADER


class UtcpHttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class UtcpHttpCallTemplate(BaseModel):
    name: str
    call_template_type: Literal["http"] = "http"
    http_method: UtcpHttpMethod = UtcpHttpMethod.GET
    url: str
    content_type: str = "application/json"
    auth: Optional[UtcpApiKeyAuth] = None


class UtcpJsonSchema(BaseModel):
    type: Optional[str] = None
    properties: Optional[Dict[str, "UtcpJsonSchema"]] = None
    items: Optional["UtcpJsonSchema"] = None
    required: Optional[List[str]] = None


UtcpJsonSchema.model_rebuild()


class UtcpTool(BaseModel):
    name: str
    description: str = ""
    inputs: UtcpJsonSchema = Field(default_factory=UtcpJsonSchema)
    outputs: UtcpJsonSchema = Field(default_factory=UtcpJsonSchema)
    tags: List[str] = Field(default_factory=list)
    tool_call_template: UtcpHttpCallTemplate


class UtcpManual(BaseModel):
    manual_version: str = MANUAL_VERSION
    utcp_version: str = UTCP_VERSION
    tools: List[UtcpTool]


def _recent_emails_tool(base_url: str) -> UtcpTool:
    return UtcpTool(
        name="get_recent_emails",
        description=(
            "Fetch recent Gmail messages with sanitized headers only "
            "(From/To/Subject/Date) - never raw bodies or attachments. "
            "Read-only: no send/modify/trash code path exists in this service."
        ),
        inputs=UtcpJsonSchema(
            type="object",
            properties={
                "maxResults": UtcpJsonSchema(type="integer"),
                "q": UtcpJsonSchema(type="string"),
            },
        ),
        outputs=UtcpJsonSchema(
            type="object",
            properties={
                "resultSizeEstimate": UtcpJsonSchema(type="integer"),
                "messages": UtcpJsonSchema(type="array"),
            },
            required=["resultSizeEstimate", "messages"],
        ),
        tags=["gmail", "read-only"],
        tool_call_template=UtcpHttpCallTemplate(
            name="cs_svc_gmail_ro_recent_emails",
            url=f"{base_url}{RECENT_EMAILS_PATH}",
            auth=UtcpApiKeyAuth(),
        ),
    )


def build_manual(base_url: str) -> UtcpManual:
    return UtcpManual(tools=[_recent_emails_tool(base_url)])
