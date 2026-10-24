#!/usr/bin/env bash
# Command-line backup for the live demo (the app's Settings -> Break/Fix demo target does the same).
#   ./scripts/demo.sh break | fix | status
# break: the demo target starts returning 503 -> DOWN alert within ~1-2 minutes (openAfter = 1).
# fix:   back to 200 -> RECOVERED alert with the downtime.
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
PARAM=/beacon/demo/healthy

case "${1:-status}" in
  break) value=false ;;
  fix) value=true ;;
  status)
    current="$(aws ssm get-parameter --region "$REGION" --name "$PARAM" --query Parameter.Value --output text)"
    if [[ "$current" == "false" ]]; then echo "Demo target is BROKEN (returns 503)"; else echo "Demo target is healthy (returns 200)"; fi
    exit 0 ;;
  *) echo "usage: $0 break|fix|status" >&2; exit 2 ;;
esac

aws ssm put-parameter --region "$REGION" --name "$PARAM" --type String --value "$value" --overwrite >/dev/null
if [[ "$value" == "false" ]]; then
  echo "Demo target broken. Expect a DOWN push + email + PagerDuty page within ~1-2 minutes."
else
  echo "Demo target fixed. Expect RECOVERED within ~1-2 minutes."
fi
