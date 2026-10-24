#!/usr/bin/env bash
# Export the SF Symbols Beacon uses from the SF Symbols app into web/.symbols/ for the iPhone
# app build (ADR 0016). The output is gitignored: SF Symbols are licensed for Apple-platform
# apps only, so they never go into the repo or the public web app.
#   ./scripts/export_sf_symbols.sh            # needs Xcode's swiftc and the SF Symbols app
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${SF_SYMBOLS_APP:-$(find /Applications -maxdepth 1 -name 'SF Symbols*.app' | sort | tail -1)}"
FONT="$APP/Contents/Resources/Fonts/SFSymbolsFallback.otf"

if [[ -z "$APP" || ! -f "$FONT" ]]; then
  echo "SF Symbols app not found in /Applications; the app keeps Beacon's own icons." >&2
  exit 1
fi

uv run --quiet --no-project --with fonttools==4.60.1 python "$ROOT/scripts/sf_symbols/export.py" "$FONT"
