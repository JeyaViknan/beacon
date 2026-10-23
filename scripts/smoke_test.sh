#!/usr/bin/env bash
# Post-deploy smoke test (HANDOVER §14): the API is healthy, runs the expected version, and the
# web app is served.  ./scripts/smoke_test.sh https://dxxxx.cloudfront.net [expected-version]
set -euo pipefail

URL="${1:?usage: smoke_test.sh <app url> [expected version]}"
URL="${URL%/}"
EXPECTED="${2:-}"

for attempt in $(seq 1 10); do
  health="$(curl -fsS --max-time 10 "$URL/api/health" || true)"
  if [[ -n "$health" ]]; then
    version="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["version"])' "$health")"
    if [[ -z "$EXPECTED" || "$version" == "$EXPECTED" ]]; then
      echo "API healthy, version $version"
      break
    fi
    echo "API answered version $version, waiting for $EXPECTED (attempt $attempt)"
  else
    echo "API not answering yet (attempt $attempt)"
  fi
  [[ "$attempt" == 10 ]] && { echo "Smoke test failed: /api/health" >&2; exit 1; }
  sleep 6
done

code="$(curl -sS -o /tmp/beacon-index.html -w '%{http_code}' --max-time 10 "$URL/")"
if [[ "$code" != "200" ]] || ! grep -q 'id="root"' /tmp/beacon-index.html; then
  echo "Smoke test failed: GET / returned $code" >&2
  exit 1
fi
echo "Web app served (HTTP 200)"
