#!/usr/bin/env bash
# Write Beacon's secrets to SSM Parameter Store (SecureString, standard tier = free).
# Run AFTER the first `terraform apply` of infra/main (Terraform creates placeholders; this
# overwrites them, and Terraform never touches the values again).
#
#   AWS_PROFILE=beacon ./scripts/put_secrets.sh      (or: make secrets)
#
# Every prompt is optional: press Enter to keep the current value. Typing is hidden (read -s),
# and values reach the AWS CLI through stdin, so they never appear in shell history or `ps`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
REGION="${AWS_REGION:-ap-south-1}"

command -v aws >/dev/null || { echo "Install the AWS CLI first: brew install awscli" >&2; exit 1; }
aws sts get-caller-identity --region "$REGION" --query Account --output text >/dev/null \
  || { echo "No AWS credentials. Run: aws login --profile beacon, then export AWS_PROFILE=beacon" >&2; exit 1; }

put() { # put <name> <type>  (value on stdin)
  aws ssm put-parameter --region "$REGION" --name "$1" --type "$2" --overwrite \
    --value "file:///dev/stdin" >/dev/null
  echo "  ✓ saved $1"
}

ask() { # ask <prompt>  -> REPLY (hidden input)
  local value
  read -r -s -p "$1: " value
  echo
  REPLY="$value"
}

echo "Beacon secrets -> SSM ($REGION). Press Enter on any prompt to keep the current value."
echo

ask "New admin password (12+ chars, Enter = keep current)"
if [[ -n "$REPLY" ]]; then
  first="$REPLY"
  ask "Repeat new admin password"
  [[ "$first" == "$REPLY" ]] || { echo "Passwords do not match; nothing changed." >&2; exit 1; }
  hash="$(printf '%s' "$first" | "$PY" "$ROOT/scripts/hash_password.py" --stdin)"
  unset first
  printf '%s' "$hash" | put /beacon/admin_password_hash SecureString
fi

read -r -p "Rotate the login-token (JWT) secret? Everyone gets signed out. [y/N] " yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
  openssl rand -base64 48 | tr -d '\n' | put /beacon/jwt_secret SecureString
fi

ask "VAPID private key from 'make vapid' (Enter = keep current)"
if [[ -n "$REPLY" ]]; then
  printf '%s' "$REPLY" | put /beacon/vapid_private_key SecureString
  read -r -p "Contact email for Web Push (mailto:): " email
  printf 'mailto:%s' "$email" | put /beacon/vapid_subject String
  echo "  ! Rebuild the web app with the matching VITE_VAPID_PUBLIC_KEY, then re-enable notifications on the phone."
fi

ask "PagerDuty integration key for PRODUCT alerts (Events API v2) (Enter = keep)"
[[ -z "$REPLY" ]] || printf '%s' "$REPLY" | put /beacon/pagerduty_routing_key SecureString

ask "PagerDuty integration URL for BEACON PLATFORM (CloudWatch) (Enter = keep)"
ops_url_changed=0
if [[ -n "$REPLY" ]]; then
  printf '%s' "$REPLY" | put /beacon/pagerduty_ops_url SecureString
  ops_url_changed=1
fi

ask "healthchecks.io ping URL (Enter = keep)"
[[ -z "$REPLY" ]] || printf '%s' "$REPLY" | put /beacon/healthchecks_ping_url SecureString

unset REPLY
echo
echo "Done. Lambdas pick up new values within 5 minutes (parameter cache)."
if [[ "$ops_url_changed" == 1 ]]; then
  echo "The PagerDuty ops URL changed: deploy once more (approve a pipeline run, or make plan && make apply)"
  echo "so SNS subscribes PagerDuty to beacon-ops-alerts."
fi
