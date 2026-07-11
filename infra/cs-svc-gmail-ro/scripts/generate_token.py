#!/usr/bin/env python3
"""One-time local OAuth flow to produce token.json for cs-svc-gmail-ro.

Run this once on a trusted local machine using an OAuth client secret
downloaded from the GCP Console (Desktop app credential type). It never
touches Secret Manager - use upload_token.py afterwards to push the
result to GCP, then delete the local copy.
"""

import argparse
import pathlib

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-secret",
        default="client_secret.json",
        help="Path to the OAuth client secret JSON downloaded from GCP Console.",
    )
    parser.add_argument(
        "--output",
        default="token.json",
        help="Where to write the resulting token.json.",
    )
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    credentials = flow.run_local_server(port=0)

    output_path = pathlib.Path(args.output)
    output_path.write_text(credentials.to_json())
    output_path.chmod(0o600)

    print(f"Wrote {output_path} (scopes: {', '.join(SCOPES)})")
    print(
        f"Next: python upload_token.py --project <GCP_PROJECT> --token-file {output_path}"
    )


if __name__ == "__main__":
    main()
