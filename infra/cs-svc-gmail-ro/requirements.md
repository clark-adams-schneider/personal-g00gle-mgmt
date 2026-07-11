# cs-svc-gmail-ro: Requirements & Specification

## Overview
`cs-svc-gmail-ro` is a standalone Backend-for-Frontend (BFF) proxy service hosted on Google Cloud Run. Its primary purpose is to establish a **cryptographically enforced, structural read-only boundary** for a personal `@gmail.com` inbox. 

By isolating the highly-privileged Gmail OAuth token in the cloud, this service prevents local automation environments (and autonomous AI agents operating within them) from automating privilege escalation or executing unauthorized write operations (e.g., sending emails), even if the local environment is fully compromised.

## Core Architecture
- **Hosting**: Google Cloud Run (Serverless).
- **Framework**: Python / FastAPI (lightweight, asynchronous).
- **Infrastructure as Code**: Pulumi (Python).
- **External Authentication (The Guardrail)**: Google Cloud IAM (OIDC). The local client authenticates to the proxy using a highly restricted GCP Service Account.
- **Internal Authentication (The Vault)**: User-delegated OAuth 2.0 credentials, stored securely in Google Secret Manager.

## 1. Security Requirements
- **Strict Token Isolation**: The user's OAuth Access Token and Refresh Token must **never** be transmitted to, returned to, or accessible by the local caller. The local client must never possess the mathematical capability to query the Gmail API directly.
- **Zero Write Codepaths**: The service codebase must structurally exclude any logic, endpoint routing, or function wrappers capable of executing `messages.send`, `messages.modify`, `messages.trash`, or any other modifying operation. 
- **OIDC Identity Validation**: The service must not be publicly accessible. It must rely on Cloud Run's native IAM proxy to block any request that does not contain a valid OIDC ID Token issued specifically to the authorized Service Account.

## 2. Functional Requirements
### Cloud Run Application (The BFF)
- **Token Hydration**: The application must retrieve the OAuth credential payload (`token.json`) from Google Secret Manager on startup or during the request cycle.
- **Auto-Refresh**: The application must utilize Google's standard auth libraries to automatically refresh the OAuth Access Token using the Refresh Token when it expires.
- **Exposed Endpoints**:
    - `GET /health`: Standard health check for Cloud Run.
    - `GET /api/v1/emails/recent`: A rigid, read-only endpoint that wraps the `gmail.users.messages.list` and `gmail.users.messages.get` API calls. It should accept safe query parameters (e.g., `maxResults`, `q` for search queries) and return the email data as sanitized JSON.

### Infrastructure (Pulumi)
The IaC must provision the following resources:
1. **Secret Manager Secret**: To hold the OAuth `token.json` payload.
2. **Cloud Run Service Identity**: A service account for the Cloud Run container itself, with the `roles/secretmanager.secretAccessor` role to read the token.
3. **Cloud Run Service**: The containerized application deployment.
4. **Local Invoker Identity**: A separate Service Account (e.g., `local-automation-client`) whose sole permission is `roles/run.invoker` on the Cloud Run service.

## 3. Operational Workflow
1. **One-Time Setup**: The developer performs the standard OAuth Web Flow locally *once* to generate a valid `token.json`, and uploads the contents into the GCP Secret Manager secret.
2. **Deployment**: Pulumi deploys the Cloud Run service and the IAM bindings.
3. **Local Execution**: The local automation script uses the `local-automation-client` Service Account key to mint an OIDC ID Token. It attaches this token to an HTTP GET request directed at the Cloud Run service URL.
4. **Proxy Execution**: Cloud Run intercepts the request, validates the OIDC token via IAM, pulls the OAuth token from Secret Manager, fetches the emails from Google's servers, and returns the read-only data payload to the local script.
