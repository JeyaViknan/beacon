#!/usr/bin/env bash
# Build one deterministic zip per Lambda into dist/<fn>.zip for Python 3.12 on arm64 (Graviton).
#   ./scripts/build_lambdas.sh            # all functions
#   ./scripts/build_lambdas.sh api probe  # just these
# Each zip = that function's pinned dependencies (manylinux aarch64 wheels; the only exception is
#            http-ece, which is pure Python and published as source only)
#          + services/beacon_core + services/<fn>.
# boto3/botocore are dropped: the Lambda runtime provides them.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
DIST="$ROOT/dist"
FUNCTIONS=("${@:-probe processor notifier api maintenance demo_target}")
read -r -a FUNCTIONS <<<"${FUNCTIONS[*]}"
PY="${PYTHON:-$ROOT/.venv/bin/python}"

mkdir -p "$DIST"
for fn in "${FUNCTIONS[@]}"; do
  echo "==> $fn"
  out="$BUILD/$fn"
  rm -rf "$out"
  mkdir -p "$out"
  uv pip install --quiet \
    --target "$out" \
    --python-version 3.12 \
    --python-platform aarch64-manylinux2014 \
    --only-binary :all: \
    --no-binary http-ece \
    -r "$ROOT/services/requirements/$fn.txt"
  rm -rf "$out"/boto3* "$out"/botocore* "$out"/s3transfer* "$out"/jmespath* "$out"/bin
  cp -R "$ROOT/services/beacon_core" "$out/beacon_core"
  cp -R "$ROOT/services/$fn" "$out/$fn"
  find "$out" -type d -name __pycache__ -prune -exec rm -rf {} +
  "$PY" "$ROOT/scripts/zip_dir.py" "$out" "$DIST/$fn.zip"
done
echo "Built: $(cd "$DIST" && ls -1 *.zip | tr '\n' ' ')"
