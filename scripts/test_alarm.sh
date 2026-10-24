#!/usr/bin/env bash
# Prove the ops alert path end to end (M7 "done when"): force one alarm into ALARM.
#   CloudWatch alarm -> SNS beacon-ops-alerts -> email + PagerDuty "Beacon Platform"
# CloudWatch re-evaluates within about a minute, sees the real (healthy) metric and returns the
# alarm to OK, which sends an OK notification and auto-resolves the PagerDuty incident.
#   ./scripts/test_alarm.sh [alarm-name]   (default: beacon-dlq-not-empty)
set -euo pipefail

ALARM="${1:-beacon-dlq-not-empty}"
REGION="${AWS_REGION:-ap-south-1}"

aws cloudwatch set-alarm-state --region "$REGION" --alarm-name "$ALARM" --state-value ALARM \
  --state-reason "Manual test of the ops alert path (scripts/test_alarm.sh). Safe to ignore."
echo "Set $ALARM to ALARM. Expect within ~1 minute:"
echo "  - email 'ALARM: \"$ALARM\" in Asia Pacific (Mumbai)'"
echo "  - a PagerDuty incident on 'Beacon Platform' (if the integration URL is set)"
echo "Then, after the next evaluation, an OK email and the PagerDuty incident resolving itself."
