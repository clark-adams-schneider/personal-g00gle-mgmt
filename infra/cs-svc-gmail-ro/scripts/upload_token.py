#!/usr/bin/env python3
"""Upload a local token.json as a new Secret Manager secret version.

This is the one-time (or credential-rotation) handoff step: it reads the
OAuth credential produced by generate_token.py and stores it in the secret
that the Cloud Run service reads from (created by Pulumi). The token never
lands anywhere else in GCP, and this script never prints its contents.
"""

import argparse
import pathlib

from google.cloud import secretmanager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="GCP project ID.")
    parser.add_argument(
        "--secret-id",
        default="cs-svc-gmail-ro-token",
        help="Secret Manager secret ID (must already exist via Pulumi).",
    )
    parser.add_argument(
        "--token-file",
        default="token.json",
        help="Path to the local token.json produced by generate_token.py.",
    )
    args = parser.parse_args()

    payload = pathlib.Path(args.token_file).read_bytes()

    client = secretmanager.SecretManagerServiceClient()
    secret_path = client.secret_path(args.project, args.secret_id)
    version = client.add_secret_version(
        parent=secret_path,
        payload=secretmanager.SecretPayload(data=payload),
    )
    print(f"Uploaded new secret version: {version.name}")


if __name__ == "__main__":
    main()
