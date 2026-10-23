#!/usr/bin/env bash
# Import every handler from its built zip inside AWS's own Lambda image (Python 3.12, arm64).
# Catches wrong-architecture wheels and missing dependencies before they reach AWS.
#   ./scripts/build_lambdas.sh && ./scripts/smoke_lambda_imports.sh
# Needs Docker; on x86 machines also QEMU (docker/setup-qemu-action in CI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="public.ecr.aws/lambda/python:3.12-arm64"
FUNCTIONS=(probe processor notifier api maintenance demo_target)

docker run --rm --platform linux/arm64 \
  -v "$ROOT/dist:/dist:ro" \
  -e AWS_REGION=ap-south-1 -e AWS_DEFAULT_REGION=ap-south-1 \
  -e POWERTOOLS_TRACE_DISABLED=true -e POWERTOOLS_METRICS_NAMESPACE=Beacon \
  -e TABLE_NAME=beacon -e HOME_REGION=ap-south-1 \
  --entrypoint /bin/bash "$IMAGE" -c "
    set -e
    for fn in ${FUNCTIONS[*]}; do
      mkdir -p /tmp/\$fn && cd /tmp/\$fn
      python3 -m zipfile -e /dist/\$fn.zip .
      python3 -c \"import importlib; m = importlib.import_module('\$fn.app'); assert callable(m.handler)\"
      echo \"  ok  \$fn\"
    done
  "
echo "All handlers import cleanly on python3.12/arm64."
