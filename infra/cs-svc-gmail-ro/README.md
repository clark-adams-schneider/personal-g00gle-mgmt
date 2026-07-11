# cs-svc-gmail-ro

Read-only Gmail BFF proxy on Cloud Run. See [requirements.md](./requirements.md)
for the full spec. This README covers build, deploy, and operation.

```
app/       FastAPI service (the only code with Gmail API access)
pulumi/    IaC: Secret Manager secret, Cloud Run service, IAM bindings
scripts/   Local-only helpers: OAuth flow, secret upload, example invoker
tests/     pytest integration tests against the live deployed service
```

## One-time setup

The steps below have a dependency order: the Secret Manager secret and
Artifact Registry repo have to exist (step 1) before you can upload a token
into the secret (step 3) or push an image into the repo (step 4). Pulumi
bootstraps the Cloud Run service with a public placeholder image the first
time round specifically so step 1 doesn't need the real app image yet.

1. **Deploy the infrastructure scaffolding** (Secret Manager secret,
   Artifact Registry repo, Cloud Run runtime identity, local invoker
   identity, and a Cloud Run revision running Google's public placeholder
   image):

   ```bash
   cd pulumi
   uv venv venv && uv pip install -r requirements.txt
   pulumi config set gcp:project <GCP_PROJECT>
   pulumi config set gcp:region us-central1
   pulumi config set developerEmail <your-gcloud-login-email>  # enables impersonation (step 5)
   cd ..
   make pulumi-up
   ```

   (`Pulumi.yaml` points the Python runtime at `./venv`, so `pulumi up` uses
   the environment `uv` just built without any extra activation step. The
   secret has no version yet and the service is still running the
   placeholder image, so it isn't functional until steps 3-4.)

2. **Create an OAuth client** in the GCP Console (APIs & Services >
   Credentials > Create Credentials > OAuth client ID > Desktop app).
   Download it as `client_secret.json`, then run the local OAuth flow to
   mint a `token.json` (readonly scope only):

   ```bash
   make mint-token CLIENT_SECRET=client_secret.json TOKEN_FILE=token.json
   ```

3. **Upload the token** into the secret Pulumi created in step 1. This uses
   Application Default Credentials (separate from `gcloud auth login`), so
   run `make gcloud-auth` once first if you haven't already:

   ```bash
   make gcloud-auth GCP_PROJECT=<GCP_PROJECT>    # one-time; opens a browser login
   make upload-token GCP_PROJECT=<GCP_PROJECT>   # or omit GCP_PROJECT to read it from `pulumi config`
   make clean-token                              # deletes local token.json (shred if available, else rm)
   ```

4. **Build the real app image and deploy it**, replacing the placeholder:

   ```bash
   make deploy-image
   ```

   (builds `app/` via Cloud Build, pushes it to the Artifact Registry repo
   Pulumi created, sets it as the `containerImage` Pulumi config, and
   re-runs `pulumi up`.)

5. **Nothing else to do here.** Local automation calls the service by
   *impersonating* the local invoker identity (`local-automation-client`) via
   your own `gcloud auth login` / ADC identity, minting short-lived OIDC
   tokens on demand - no downloaded service-account key ever touches disk.
   (Most orgs' security policy blocks service-account key creation outright
   - `constraints/iam.disableServiceAccountKeyCreation` - so this isn't just
   a preference.) This works because `developerEmail` (step 1) was granted
   `roles/iam.serviceAccountTokenCreator` on that identity. If you skipped
   setting `developerEmail`, set it now and re-run `make pulumi-up`.

## Testing

```bash
make test
```

Runs `tests/` with pytest against the live deployed service (there's nothing
to mock here - the point of this service is the real IAM boundary and Gmail
round trip). `test_unauthenticated_request_is_rejected` works as soon as
`make pulumi-up` has run; `test_health` and `test_recent_emails_shape` need
the real app deployed (step 4) and impersonation access (step 1's
`developerEmail` + `make gcloud-auth`) - they `SKIP` cleanly until both are
in place. Override the invoker SA email with `LOCAL_INVOKER_SA_EMAIL=<email>
make test` if you're not reading it from the Pulumi stack.

## Building and pushing a new image later

```bash
make deploy-image IMAGE_TAG=<new-tag>
```

`make build-image` alone builds and pushes without redeploying, if you want
to stage an image before rolling it out.

## Calling the service locally

```bash
cd scripts
uv run --no-project python local_client.py \
  --service-url "$(pulumi -C ../pulumi stack output serviceUrl)" \
  --invoker-sa-email "$(pulumi -C ../pulumi stack output localInvokerServiceAccountEmail)" \
  --max-results 5 \
  --query "is:unread"
```

## Security properties enforced by this design

- The Gmail OAuth token never leaves GCP: it is read from Secret Manager by
  the Cloud Run runtime identity and never serialized back into an HTTP
  response.
- The runtime identity's only grant is `roles/secretmanager.secretAccessor`
  on this one secret. The local invoker identity's only grant is
  `roles/run.invoker` on this one Cloud Run service - it has no Gmail or
  Secret Manager permissions at all.
- No `allUsers` / `allAuthenticatedUsers` IAM binding is ever created, so
  Cloud Run's IAM proxy rejects any request lacking a valid OIDC token for
  an authorized principal, independent of application code.
- `app/main.py` only calls `messages.list` and `messages.get`; there is no
  send/modify/trash/delete code path in the service.
