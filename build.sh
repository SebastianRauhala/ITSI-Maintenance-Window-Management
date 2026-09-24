#!/usr/bin/env bash
#
# Reproducible packaging for ITSI Maintenance Window Management.
# Builds an installable .spl into ./dist/ WITHOUT committing any build artifact
# to git (dist/ is .gitignored). The .spl excludes tests and repo/dev files.
#
# Usage:  ./build.sh
#
set -euo pipefail

APP="itsi_maintenance_window_management"
ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -nE 's/^version = ([0-9].*)$/\1/p' "$ROOT/default/app.conf" | head -1)"
DIST="$ROOT/dist"
STAGE="$(mktemp -d)"
OUT="$DIST/${APP}-${VERSION}.spl"

echo "Packaging $APP version $VERSION"

# Stage a clean copy of the app.
mkdir -p "$STAGE/$APP"
# Copy tracked-source-style tree, excluding dev/build/repo files.
tar --exclude='.git' --exclude='.gitignore' --exclude='tests' \
    --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.DS_Store' --exclude='*.spl' --exclude='appinspect*.json' \
    --exclude='build.sh' \
    -C "$ROOT" -cf - . | tar -C "$STAGE/$APP" -xf -

# Normalize permissions (dirs 755, files 644).
find "$STAGE/$APP" -type d -exec chmod 755 {} +
find "$STAGE/$APP" -type f -exec chmod 644 {} +

mkdir -p "$DIST"
rm -f "$OUT"
# COPYFILE_DISABLE avoids macOS AppleDouble (._*) files that AppInspect rejects.
COPYFILE_DISABLE=1 tar -C "$STAGE" -czf "$OUT" "$APP"
rm -rf "$STAGE"

echo "Built: $OUT"
echo "SHA256: $(shasum -a 256 "$OUT" | awk '{print $1}')"
