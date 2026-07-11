SCRIPTS_DIR := scripts
PULUMI_DIR := pulumi
APP_DIR := app
TESTS_DIR := tests
CLIENT_SECRET ?= client_secret.json
TOKEN_FILE ?= token.json
SECRET_ID ?= cs-svc-gmail-ro-token
SERVICE_NAME ?= cs-svc-gmail-ro
IMAGE_TAG ?= latest
STACK_NAME ?= dev

# This stack has no pulumi-managed secrets (the OAuth token is uploaded to
# Secret Manager directly, never through `pulumi config`), so an empty
# passphrase is fine - and this stack was already sealed with one, so don't
# change the value here without also migrating the stack's secrets provider.
# It's passed explicitly on every pulumi invocation below (not just via
# `export`): GNU Make 3.81 (macOS's default `make`) doesn't reliably
# propagate `export`ed variables into the $(shell) function used inside
# variable definitions, only into recipe-line subshells, so relying on
# `export` alone leaves it genuinely unset (not just empty) for some calls.
PULUMI_CONFIG_PASSPHRASE ?=
PULUMI_ENV := PULUMI_CONFIG_PASSPHRASE=$(PULUMI_CONFIG_PASSPHRASE)

GCP_PROJECT ?= $(shell cd $(PULUMI_DIR) && $(PULUMI_ENV) pulumi config get gcp:project --stack $(STACK_NAME) 2>/dev/null)
IMAGE_REPO = $(shell cd $(PULUMI_DIR) && $(PULUMI_ENV) pulumi stack output imageRepo --stack $(STACK_NAME) 2>/dev/null)

SCRIPTS_VENV_STAMP := $(SCRIPTS_DIR)/.venv/pyvenv.cfg
PULUMI_VENV_STAMP := $(PULUMI_DIR)/venv/pyvenv.cfg
TESTS_VENV_STAMP := $(TESTS_DIR)/.venv/pyvenv.cfg

.PHONY: scripts-venv pulumi-venv tests-venv pulumi-stack gcloud-auth mint-token upload-token clean-token pulumi-up build-image deploy-image test

# Real file targets (not .PHONY): only (re)build the venv when it's missing
# or requirements.txt changed, so repeat `make` calls are fast and never hit
# uv's interactive "replace existing venv?" prompt.
$(SCRIPTS_VENV_STAMP): $(SCRIPTS_DIR)/requirements.txt
	cd $(SCRIPTS_DIR) && uv venv && uv pip install -r requirements.txt

$(PULUMI_VENV_STAMP): $(PULUMI_DIR)/requirements.txt
	cd $(PULUMI_DIR) && uv venv venv --seed && VIRTUAL_ENV=venv uv pip install -r requirements.txt

$(TESTS_VENV_STAMP): $(TESTS_DIR)/requirements.txt
	cd $(TESTS_DIR) && uv venv && uv pip install -r requirements.txt

scripts-venv: $(SCRIPTS_VENV_STAMP)

pulumi-venv: $(PULUMI_VENV_STAMP)

tests-venv: $(TESTS_VENV_STAMP)

# Selects the stack non-interactively, creating it on first run, so `pulumi`
# commands never fall into the "choose a stack" interactive picker.
pulumi-stack: pulumi-venv
	cd $(PULUMI_DIR) && $(PULUMI_ENV) pulumi stack select $(STACK_NAME) --create

gcloud-auth:
	gcloud auth application-default login
	@if [ -n "$(GCP_PROJECT)" ]; then \
		gcloud auth application-default set-quota-project $(GCP_PROJECT); \
	fi

mint-token: scripts-venv
	cd $(SCRIPTS_DIR) && uv run --no-project python generate_token.py \
		--client-secret $(CLIENT_SECRET) \
		--output $(TOKEN_FILE)

upload-token: scripts-venv
	@if [ -z "$(GCP_PROJECT)" ]; then \
		echo "GCP_PROJECT is not set and could not be read from 'pulumi config' in $(PULUMI_DIR)/; pass GCP_PROJECT=<project>"; \
		exit 1; \
	fi
	cd $(SCRIPTS_DIR) && uv run --no-project python upload_token.py \
		--project $(GCP_PROJECT) \
		--secret-id $(SECRET_ID) \
		--token-file $(TOKEN_FILE)

clean-token:
	@if command -v shred >/dev/null 2>&1; then \
		shred -u $(SCRIPTS_DIR)/$(TOKEN_FILE); \
	else \
		rm -f $(SCRIPTS_DIR)/$(TOKEN_FILE); \
	fi

pulumi-up: pulumi-stack
	cd $(PULUMI_DIR) && $(PULUMI_ENV) pulumi up --stack $(STACK_NAME) --yes

build-image: pulumi-stack
	@if [ -z "$(IMAGE_REPO)" ]; then \
		echo "Could not read 'imageRepo' from the pulumi stack; run 'make pulumi-up' first"; \
		exit 1; \
	fi
	gcloud builds submit --tag $(IMAGE_REPO)/$(SERVICE_NAME):$(IMAGE_TAG) $(APP_DIR)

deploy-image: build-image
	cd $(PULUMI_DIR) && $(PULUMI_ENV) pulumi config set containerImage $(IMAGE_REPO)/$(SERVICE_NAME):$(IMAGE_TAG) --stack $(STACK_NAME)
	$(MAKE) pulumi-up

# Integration tests against the live deployed service: unauthenticated
# access must 403, and (once a real invoker key exists, see README) /health
# and /api/v1/emails/recent must behave and stay within the sanitized shape.
test: tests-venv
	cd $(TESTS_DIR) && uv run --no-project pytest -v
