#!/usr/bin/env bash
# Build the PWA and publish it: S3 sync + CloudFront invalidation of the never-cached files.
# Needs: terraform outputs from infra/main (initialised), AWS credentials, VITE_VAPID_PUBLIC_KEY.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF="terraform -chdir=$ROOT/infra/main"
BUCKET="${WEB_BUCKET:-$($TF output -raw web_bucket)}"
DIST_ID="${DISTRIBUTION_ID:-$($TF output -raw cloudfront_distribution_id)}"
export VITE_APP_VERSION="${VITE_APP_VERSION:-$(git -C "$ROOT" rev-parse --short HEAD)}"
: "${VITE_VAPID_PUBLIC_KEY:?set VITE_VAPID_PUBLIC_KEY (from make vapid)}"

(cd "$ROOT/web" && npm ci && npm run build)

# Hashed assets can be cached forever; the shell, service worker and manifest must not be.
aws s3 sync "$ROOT/web/dist" "s3://$BUCKET" --delete \
  --exclude index.html --exclude sw.js --exclude manifest.webmanifest \
  --cache-control "public,max-age=31536000,immutable"
for f in index.html sw.js manifest.webmanifest; do
  [[ -f "$ROOT/web/dist/$f" ]] || continue
  aws s3 cp "$ROOT/web/dist/$f" "s3://$BUCKET/$f" --cache-control "no-cache"
done

aws cloudfront create-invalidation --distribution-id "$DIST_ID" \
  --paths /index.html /sw.js /manifest.webmanifest >/dev/null
echo "Deployed web $VITE_APP_VERSION to $BUCKET (distribution $DIST_ID)"
