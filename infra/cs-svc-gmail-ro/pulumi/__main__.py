"""Pulumi program for cs-svc-gmail-ro.

Provisions:
  1. A Secret Manager secret to hold the Gmail OAuth token.json payload
     (versions are populated out-of-band by scripts/upload_token.py, never
     by Pulumi, so the token never passes through the IaC state).
  2. An Artifact Registry repository to hold the app's container images.
  3. A Cloud Run runtime service identity, granted secretAccessor on that
     secret and nothing else.
  4. The Cloud Run v2 service itself. It is never granted an `allUsers` /
     `allAuthenticatedUsers` IAM binding, so Cloud Run's IAM proxy rejects
     any request without a valid OIDC token for an authorized principal.
  5. A local invoker identity whose sole grant is `roles/run.invoker` on
     this specific Cloud Run service.
  6. IAM grants for the project's default Compute Engine service account,
     which Cloud Build runs as by default: `roles/storage.objectViewer` to
     read the source tarball it stages in GCS, `roles/artifactregistry.writer`
     to push the built image, and `roles/logging.logWriter` to write build
     logs (`make build-image` / `make deploy-image` fail without these).
  7. `roles/iam.serviceAccountTokenCreator` on the local invoker identity for
     `developerEmail` (Pulumi config), if set. Most orgs' security policy
     disables service-account-key creation (`constraints/iam.disableService
     AccountKeyCreation`), so `scripts/local_client.py` and the pytest suite
     mint OIDC tokens via impersonation instead of a downloaded JSON key -
     this grant is what lets your own `gcloud auth login` identity do that
     impersonation, with nothing long-lived ever written to disk.

Bootstrapping note: `containerImage` defaults to Google's public Cloud Run
"hello" sample so the secret/registry/IAM scaffolding can be created before
you've built the real app image (see Makefile `build-image`). Re-run
`pulumi up` with `containerImage` set to your pushed image to roll out the
real service.
"""

import pulumi
import pulumi_gcp as gcp

config = pulumi.Config()
gcp_config = pulumi.Config("gcp")

project = gcp_config.require("project")
region = gcp_config.get("region") or "us-central1"

service_name = config.get("serviceName") or "cs-svc-gmail-ro"
token_secret_id = config.get("tokenSecretId") or "cs-svc-gmail-ro-token"
image_repo_id = config.get("imageRepoId") or service_name
container_image = (
    config.get("containerImage") or "us-docker.pkg.dev/cloudrun/container/hello:latest"
)
developer_email = config.get("developerEmail")

project_info = gcp.organizations.get_project(project_id=project)
cloudbuild_default_sa_email = (
    f"{project_info.number}-compute@developer.gserviceaccount.com"
)

# 1. Secret Manager secret for the OAuth token.json payload.
token_secret = gcp.secretmanager.Secret(
    "gmail-token-secret",
    secret_id=token_secret_id,
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

# 2. Artifact Registry repository for the app's container images.
image_repository = gcp.artifactregistry.Repository(
    "app-images",
    repository_id=image_repo_id,
    location=region,
    format="DOCKER",
)

# 3. Cloud Run runtime identity - read access to the token secret only.
runtime_service_account = gcp.serviceaccount.Account(
    "cloud-run-runtime-sa",
    account_id=f"{service_name}-runtime",
    display_name="cs-svc-gmail-ro Cloud Run runtime identity",
)

runtime_secret_access = gcp.secretmanager.SecretIamMember(
    "runtime-secret-accessor",
    secret_id=token_secret.secret_id,
    role="roles/secretmanager.secretAccessor",
    member=runtime_service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# 4. Cloud Run service. No allUsers/allAuthenticatedUsers binding is ever
#    created, so only principals explicitly granted run.invoker (below)
#    can reach it.
cloud_run_service = gcp.cloudrunv2.Service(
    "cs-svc-gmail-ro",
    name=service_name,
    location=region,
    ingress="INGRESS_TRAFFIC_ALL",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        service_account=runtime_service_account.email,
        containers=[
            gcp.cloudrunv2.ServiceTemplateContainerArgs(
                image=container_image,
                envs=[
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="GCP_PROJECT", value=project
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="TOKEN_SECRET_NAME", value=token_secret_id
                    ),
                ],
                ports=[
                    gcp.cloudrunv2.ServiceTemplateContainerPortArgs(container_port=8080)
                ],
            )
        ],
    ),
    opts=pulumi.ResourceOptions(depends_on=[runtime_secret_access]),
)

# 5. Local invoker identity - sole permission is run.invoker on this service.
local_invoker_service_account = gcp.serviceaccount.Account(
    "local-invoker-sa",
    account_id="local-automation-client",
    display_name="Local automation client (Cloud Run invoker only)",
)

local_invoker_binding = gcp.cloudrunv2.ServiceIamMember(
    "local-invoker-run-invoker",
    name=cloud_run_service.name,
    location=region,
    role="roles/run.invoker",
    member=local_invoker_service_account.email.apply(
        lambda email: f"serviceAccount:{email}"
    ),
)

# 6. Cloud Build (invoked by `make build-image`) runs as this default SA and
#    needs to read its GCS source tarball, push the built image, and write
#    build logs.
cloudbuild_default_sa_roles = [
    "roles/storage.objectViewer",
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
]
cloudbuild_default_sa_bindings = [
    gcp.projects.IAMMember(
        f"cloudbuild-default-sa-{role.split('/')[-1]}",
        project=project,
        role=role,
        member=f"serviceAccount:{cloudbuild_default_sa_email}",
    )
    for role in cloudbuild_default_sa_roles
]

# 7. Lets `developerEmail` impersonate the local invoker identity to mint
#    OIDC tokens on demand, instead of a downloaded service-account key.
if developer_email:
    developer_impersonation = gcp.serviceaccount.IAMMember(
        "developer-invoker-impersonation",
        service_account_id=local_invoker_service_account.name,
        role="roles/iam.serviceAccountTokenCreator",
        member=f"user:{developer_email}",
    )

pulumi.export("serviceUrl", cloud_run_service.uri)
pulumi.export("runtimeServiceAccountEmail", runtime_service_account.email)
pulumi.export("localInvokerServiceAccountEmail", local_invoker_service_account.email)
pulumi.export("tokenSecretId", token_secret.secret_id)
pulumi.export(
    "imageRepo",
    pulumi.Output.concat(
        region, "-docker.pkg.dev/", project, "/", image_repository.repository_id
    ),
)
