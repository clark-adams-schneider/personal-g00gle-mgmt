"""Fixtures for the cs-svc-gmail-ro integration tests.

These tests hit the real, deployed Cloud Run service - there is nothing to
mock, since the entire point of this service is the IAM boundary and the
live Gmail API round trip. Values default to reading from the Pulumi stack
and can be overridden with env vars for CI or a non-default stack.
"""

import os
import subprocess

import google.auth
import google.auth.exceptions
import google.auth.impersonated_credentials
import google.auth.transport.requests
import pytest

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PULUMI_DIR = os.path.join(REPO_ROOT, "pulumi")
STACK_NAME = os.environ.get("STACK_NAME", "dev")


def _pulumi_output(name: str) -> str:
    result = subprocess.run(
        ["pulumi", "stack", "output", name, "--stack", STACK_NAME],
        cwd=PULUMI_DIR,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PULUMI_CONFIG_PASSPHRASE": os.environ.get("PULUMI_CONFIG_PASSPHRASE", ""),
        },
    )
    if result.returncode != 0:
        pytest.skip(f"could not read pulumi output '{name}': {result.stderr.strip()}")
    return result.stdout.strip()


@pytest.fixture(scope="session")
def service_url() -> str:
    return os.environ.get("SERVICE_URL") or _pulumi_output("serviceUrl")


@pytest.fixture(scope="session")
def invoker_sa_email() -> str:
    return os.environ.get("LOCAL_INVOKER_SA_EMAIL") or _pulumi_output(
        "localInvokerServiceAccountEmail"
    )


@pytest.fixture(scope="session")
def id_token(service_url: str, invoker_sa_email: str) -> str:
    # Impersonation, not a downloaded key: your own `gcloud auth login` /
    # ADC identity needs roles/iam.serviceAccountTokenCreator on the
    # invoker SA (set via the Pulumi `developerEmail` config).
    try:
        source_credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    except google.auth.exceptions.DefaultCredentialsError:
        pytest.skip("no Application Default Credentials found; run `make gcloud-auth`")
    target_credentials = google.auth.impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=invoker_sa_email,
        target_scopes=[CLOUD_PLATFORM_SCOPE],
    )
    id_token_credentials = google.auth.impersonated_credentials.IDTokenCredentials(
        target_credentials, target_audience=service_url, include_email=True
    )
    try:
        id_token_credentials.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.RefreshError as exc:
        pytest.skip(f"could not impersonate {invoker_sa_email}: {exc}")
    return id_token_credentials.token
