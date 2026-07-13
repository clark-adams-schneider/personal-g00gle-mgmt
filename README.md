# personal-g00gle-mgmt
Personal Google Cloud and Services Management IaC

## `pg0` CLI

This package installs a `pg0` command - the unified CLI entry point for this
workspace. Every capability here is meant to be reachable as a first-class
citizen through raw REST, MCP, CLI, and UTCP alike (see `CLAUDE.md` Rule 7);
`pg0` is the CLI side of that, and shares its typed client code with the MCP
side so neither can drift from the canonical REST implementation.

```bash
uv pip install -e .
pg0 --help
```

### `pg0 gmail` - cs-svc-gmail-ro

Talks to the deployed [cs-svc-gmail-ro](infra/cs-svc-gmail-ro/README.md)
Cloud Run service - a read-only Gmail BFF proxy. Every `pg0 gmail` command
calls that service's REST API over an OIDC ID token minted by impersonating
its invoker service account; none of them touch the Gmail API or the
underlying OAuth credential directly (those stay inside Secret Manager and
the Cloud Run runtime identity - see that service's README for the full
security design).

Every command needs the service URL and the invoker service account email,
either as flags or env vars. Read them from the deployed Pulumi stack:

```bash
export GMAIL_RO_SERVICE_URL="$(pulumi -C infra/cs-svc-gmail-ro/pulumi stack output serviceUrl)"
export GMAIL_RO_INVOKER_SA_EMAIL="$(pulumi -C infra/cs-svc-gmail-ro/pulumi stack output localInvokerServiceAccountEmail)"
```

Your own `gcloud auth login` / ADC identity needs
`roles/iam.serviceAccountTokenCreator` on that invoker service account (set
via the Pulumi `developerEmail` config in `infra/cs-svc-gmail-ro`).

**Fetch recent emails** (sanitized headers only - `From`/`To`/`Subject`/`Date`,
never raw bodies):

```bash
pg0 gmail recent --max-results 5 --query "is:unread"
```

**Run an MCP server** exposing the same capability as a tool
(`get_recent_emails_tool`), e.g. for wiring into Claude Desktop's MCP config:

```bash
pg0 gmail mcp-serve
```

```json
{
  "mcpServers": {
    "cs-svc-gmail-ro": {
      "command": "pg0",
      "args": ["gmail", "mcp-serve"],
      "env": {
        "GMAIL_RO_SERVICE_URL": "https://cs-svc-gmail-ro-xyz.a.run.app",
        "GMAIL_RO_INVOKER_SA_EMAIL": "local-automation-client@<project>.iam.gserviceaccount.com"
      }
    }
  }
}
```

**UTCP discovery**: the service also exposes a `GET /utcp` manual describing
its REST tool(s) for any UTCP-compatible client - see
`infra/cs-svc-gmail-ro/app/utcp_manual.py`.
