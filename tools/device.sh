#!/usr/bin/env bash
# Compatibility entry point for protected motion history drivers.
set -euo pipefail
cd "$(dirname "$0")/.."
exec tools/dev/device.sh "$@"
