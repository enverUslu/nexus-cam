#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m PyInstaller packaging/NexusCam-macos.spec --clean --noconfirm

mkdir -p dist/installer
hdiutil create \
  -volname "Nexus.cam" \
  -srcfolder "dist/Nexus.cam.app" \
  -ov \
  -format UDZO \
  "dist/installer/NexusCam-v0.1.0-macOS.dmg"

echo
echo "Built: dist/Nexus.cam.app"
echo "Built: dist/installer/NexusCam-v0.1.0-macOS.dmg"
