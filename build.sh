#!/bin/bash

set -euo pipefail

# Configuration
PROJECT_ZIP="institute_api_code.zip"
VENV_PYTHON="${VENV_PYTHON:-myenv/bin/python}"
BUILD_DIR="temp_build"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

echo "======================================"
echo "Starting build process for AWS Lambda"
echo "======================================"

# 1. Clean up previous builds
echo "--> Cleaning up previous builds..."
rm -rf "$BUILD_DIR"
rm -f "$PROJECT_ZIP"

# 2. Prepare build directory
mkdir -p "$BUILD_DIR"

# 3. Install dependencies directly into the build directory
echo "--> Installing dependencies..."
if ! python3 -m pip install -r requirements.txt --target "$BUILD_DIR"; then
  echo "--> pip install failed; attempting local virtualenv fallback..."
  if [[ -x "$VENV_PYTHON" ]]; then
    site_packages_dir="$("$VENV_PYTHON" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    cp -a "$site_packages_dir"/. "$BUILD_DIR"/
  else
    echo "Error: Could not install dependencies." >&2
    exit 1
  fi
fi

# 4. Copy project code into the build directory
echo "--> Copying project code..."
rsync -a \
  --exclude='.git/' \
  --exclude='myenv/' \
  --exclude='temp_build/' \
  --exclude='staticfiles/' \
  --exclude='institute-api/' \
  --exclude='*.zip' \
  --exclude='*.md' \
  --exclude='*.sqlite3' \
  --exclude='.env' \
  --exclude='.vscode/' \
  --exclude='.codex' \
  --exclude='build.sh' \
  --exclude='test_*.py' \
  --exclude='*/__pycache__/' \
  --exclude='*/.pytest_cache/' \
  . "$BUILD_DIR"/ 

# 5. Zip the project
echo "--> Zipping project..."
(
  cd "$BUILD_DIR"
  zip -r9 "../$PROJECT_ZIP" . > /dev/null
)

# 6. Clean up
echo "--> Cleaning up temporary folders..."
rm -rf "$BUILD_DIR"

echo "======================================"
echo "Build complete!"
echo "Package: $PROJECT_ZIP (Upload directly to Lambda)"
echo "======================================"
