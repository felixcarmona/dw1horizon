#!/usr/bin/env bash
# Builds the disc for an Android handheld running DuckStation (build/device.cue: python3 -m tools.dev build, with its cache),
# sends it to /sdcard/Digimon/ and starts DuckStation. The device is selected by DEVICE (USB serial or wireless
# HOST:PORT). Enable USB debugging first.
#   tools/dev/device.sh            build, push, launch
#   tools/dev/device.sh push       push the existing build/device.* and launch
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${DEVICE:?Set DEVICE to an authorized adb serial or HOST:PORT}"
DEV=$DEVICE
[ "${1:-}" = push ] || python3 -m tools.dev build --name device
case $DEV in *:*) adb connect "$DEV" >/dev/null;; esac
adb -s "$DEV" get-state | grep -q device || { echo "$DEV is not authorized: accept the prompt on the device" >&2; exit 1; }
adb -s "$DEV" shell am force-stop com.github.stenzek.duckstation
adb -s "$DEV" push build/device.cue build/device.bin /sdcard/Digimon/
adb -s "$DEV" shell monkey -p com.github.stenzek.duckstation -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
echo "DuckStation started: tap the game in the list"
