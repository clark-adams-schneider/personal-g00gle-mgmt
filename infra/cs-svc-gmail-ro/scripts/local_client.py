#!/usr/bin/env python3
"""Example local automation client for cs-svc-gmail-ro.

Mints an OIDC ID token for the `local-automation-client` service account by
impersonating it (via `gcloud auth application-default login` / ADC) and
calls the read-only emails endpoint. This is the only codepath the local
environment needs; it never sees the underlying Gmail OAuth credential,
which stays inside Secret Manager and the Cloud Run runtime identity.

Impersonation rather than a downloaded JSON key: most orgs disable
service-account key creation as a security policy, and even where it's
allowed, a long-lived key file is strictly worse than minting short-lived
tokens on demand from your own `gcloud` identity. Your identity needs
`roles/iam.serviceAccountTokenCreator` on the invoker SA (see the Pulumi
`developerEmail` config).
"""

import argparse
import json

import google.auth
import google.auth.impersonated_credentials
import google.auth.transport.requests
import requests

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service-url",
        required=True,
        help="Cloud Run service URL, e.g. https://cs-svc-gmail-ro-xyz.a.run.app",
    )
    parser.add_argument(
        "--invoker-sa-email",
        required=True,
        help="local-automation-client service account email to impersonate.",
    )
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument(
        "--query", default=None, help="Gmail search query (the `q` parameter)."
    )
    args = parser.parse_args()

    id_token = mint_id_token(args.invoker_sa_email, args.service_url)

    params = {"maxResults": args.max_results}
    if args.query:
        params["q"] = args.query

    response = requests.get(
        f"{args.service_url}/api/v1/emails/recent",
        headers={"Authorization": f"Bearer {id_token}"},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
