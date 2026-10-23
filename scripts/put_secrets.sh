#!/usr/bin/env bash
# Write Beacon's secrets to SSM Parameter Store (SecureString, standard tier = free).
# Run AFTER the first `terraform apply` of infra/main (Terraform creates placeholders; this
# overwrites them, and Terraform never touches the values again).
#
#   AWS_PROFILE=<your profile> ./scripts/put_secrets.sh
#
# Every prompt is silent (read -s). Values are piped to the AWS CLI via stdin, so they never
# appear in shell history or the process list. Press Enter on an optional prompt to skip it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
REGION="${AWS_REGION:-ap-south-1}"

command -v aws >/dev/null || { echo "Install the AWS CLI first: brew install awscli" >&2; exit 1; }
aws sts get-caller-identity --region "$REGION" --query Account --output text >/dev/null \
  || { echo "No AWS credentials. Set AWS_PROFILE or run 'aws sso login'." >&2; exit 1; }

put() { # put <name> <type>  (value on stdin)
  aws ssm put-parameter --region "$REGION" --name "$1" --type "$2" --overwrite \
    --value "file:///dev/stdin" >/dev/null
  echo "  ✓ $1"
}

ask() { # ask <prompt> -> REPLY (silent)
  local value
  read -r -s -p "$1: " value
  echo
  REPLY="$value"
}

echo "Beacon secrets -> SSM ($REGION)"

ask "Admin password (min 12 chars)"
first="$REPLY"
ask "Repeat admin password"
[[ "$first" == "$REPLY" ]] || { echo "Passwords do not match." >&2; exit 1; }
hash="$(printf '%s' "$first" | "$PY" "$ROOT/scripts/hash_password.py" --stdin)"
unset first REPLY
printf '%s' "$hash" | put /beacon/admin_password_hash SecureString

read -r -p "Generate a new JWT secret? Existing logins will be signed out. [Y/n] " yn
if [[ ! "$yn" =~ ^[Nn]$ ]]; then
  openssl rand -base64 48 | tr -d '\n' | put /beacon/jwt_secret SecureString
fi

ask "VAPID private key (from 'make vapid'; Enter to skip)"
if [[ -n "$REPLY" ]]; then
  printf '%s' "$REPLY" | put /beacon/vapid_private_key SecureString
  read -r -p "VAPID contact email (for mailto:): " email
  printf 'mailto:%s' "$email" | put /beacon/vapid_subject String
fi

ask "PagerDuty Events v2 routing key for product alerts (Enter to skip)"
[[ -n "$REPLY" ]] && printf '%s' "$REPLY" | put /beacon/pagerduty_routing_key SecureString

ask "PagerDuty CloudWatch integration URL for Beacon Platform (Enter to skip)"
[[ -n "$REPLY" ]] && printf '%s' "$REPLY" | put /beacon/pagerduty_ops_url SecureString

ask "healthchecks.io ping URL (Enter to skip)"
[[ -n "$REPLY" ]] && printf '%s' "$REPLY" | put /beacon/healthchecks_ping_url SecureString

unset REPLY
echo "Done. Lambdas pick up new values within 5 minutes (parameter cache)."
echo "If you set the PagerDuty ops URL, re-run terraform apply so SNS subscribes it."
