#!/usr/bin/env bash
# Build the native iOS app's screens and copy them into the Xcode project (ADR 0015).
# The app draws real SF Symbols, exported from the SF Symbols app on this Mac (ADR 0016).
#   ./scripts/build_ios.sh            # then: open web/ios/App/App.xcodeproj, press Run
# The app calls the live API cross-origin, so it needs Beacon's public URL:
#   BEACON_URL=https://dxxxx.cloudfront.net ./scripts/build_ios.sh   (default: terraform output)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${BEACON_URL:-$(terraform -chdir="$ROOT/infra/main" output -raw cloudfront_url)}"
VERSION="$(git -C "$ROOT" rev-parse --short HEAD)"

"$ROOT/scripts/export_sf_symbols.sh" || echo "Building with Beacon's own icons instead of SF Symbols." >&2

cd "$ROOT/web"
BEACON_NATIVE=1 VITE_API_BASE="$URL" VITE_APP_VERSION="$VERSION" npx vite build
npx cap sync ios
echo "iOS app updated (API: $URL, version $VERSION). Open web/ios/App/App.xcodeproj in Xcode and press Run."
