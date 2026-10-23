SHELL := /bin/bash
VENV ?= .venv
PY ?= $(VENV)/bin/python
TF_MAIN := infra/main

.PHONY: help setup lint fmt test build web validate plan apply deploy-web secrets vapid hash clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup: ## Create .venv (Python 3.12) and install dev dependencies
	uv venv $(VENV) --python 3.12
	uv pip install --python $(PY) -r requirements-dev.txt

lint: ## ruff check + format check
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt: ## Auto-fix lint and format
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

test: ## pytest (unit + integration with moto), 85% coverage gate on beacon_core
	$(PY) -m pytest

build: ## Build Lambda zips into dist/ (arm64)
	./scripts/build_lambdas.sh

web: ## Frontend: install, typecheck, lint, test, build
	cd web && npm ci && npm run typecheck && npm run lint && npm test && npm run build

validate: ## terraform fmt check + validate (no backend, no credentials needed)
	terraform fmt -check -recursive infra
	cd infra/bootstrap && terraform init -backend=false -input=false >/dev/null && terraform validate
	cd infra/modules/probe && terraform init -backend=false -input=false >/dev/null && terraform validate
	cd $(TF_MAIN) && terraform init -backend=false -input=false >/dev/null && terraform validate

plan: build ## terraform plan for infra/main (needs AWS credentials)
	cd $(TF_MAIN) && terraform init -input=false -backend-config="bucket=$${TF_STATE_BUCKET:?set TF_STATE_BUCKET}" && terraform plan -out tfplan

apply: ## Apply the saved plan (Jeya only)
	cd $(TF_MAIN) && terraform apply tfplan

deploy-web: ## Build the PWA and upload it to S3 + invalidate CloudFront
	./scripts/deploy_web.sh

secrets: ## Prompt for secrets and write them to SSM Parameter Store
	./scripts/put_secrets.sh

vapid: ## Print a new VAPID key pair for Web Push
	$(PY) scripts/gen_vapid.py

hash: ## Prompt for the admin password and print its argon2id hash
	$(PY) scripts/hash_password.py

clean: ## Remove build output
	rm -rf dist .pytest_cache .ruff_cache .coverage htmlcov
