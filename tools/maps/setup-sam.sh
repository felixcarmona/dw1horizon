#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Usage: tools/maps/setup-sam.sh [venv-directory [checkpoint-directory]]
set -euo pipefail
cd "$(dirname "$0")/../.."
VENV=${1:-build/sam-venv}
MODELS=${2:-build/sam-models}
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install 'torch==2.15.0' --index-url https://download.pytorch.org/whl/cpu
"$VENV/bin/python" -m pip install 'numpy==2.5.4' 'opencv-python-headless==5.0.0.93' \
  'git+https://github.com/facebookresearch/segment-anything.git@dca509fe793f601edb92606367a655c15ac00fdf'
# Prompted SAM uses tools/maps/sam.py. Upstream's automatic-mask initializer
# imports torchvision (whose image transforms require Pillow); we do not use it.
"$VENV/bin/python" - <<'PYTEST'
import importlib.util
from tools.maps.sam import SamPredictor, sam_model_registry
assert importlib.util.find_spec('PIL') is None, 'use a fresh SAM venv without Pillow'
assert 'vit_h' in sam_model_registry
PYTEST
mkdir -p "$MODELS"
CHECKPOINT="$MODELS/sam_vit_h_4b8939.pth"
SHA=a7bf3b02f3ebf1267aba913ff637d9a2d5c33d3173bb679e46d9f338c26f262e
if ! test -f "$CHECKPOINT"; then
  curl --fail --location --retry 3 https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth -o "$CHECKPOINT.part"
  printf '%s  %s\n' "$SHA" "$CHECKPOINT.part" | sha256sum --check
  mv "$CHECKPOINT.part" "$CHECKPOINT"
fi
printf '%s  %s\n' "$SHA" "$CHECKPOINT" | sha256sum --check
