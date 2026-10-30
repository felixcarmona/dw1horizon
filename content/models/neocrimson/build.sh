#!/usr/bin/env bash
# NeoCrimson (402) model: bone map by anatomy (spec.json), legs by their feet (tools/legik.py, from Tyrannomon's walk),
# feet flat (tools/footfix.py). Writes build/neocrimson-out/NeoCrimson.MMD/.TIM, the files content/species/402 names.
# Check it with tools/animstudio.py (docs/mods/models.md "Animation studio").
set -euo pipefail
cd "$(dirname "$0")/../../.."
T=build/neocrimson-work; O=build/neocrimson-out
SLOTS="2 3 4 0x1b 0x23 0x24"
python3 tools/dw2mmd.py partner content/models/neocrimson/spec.json $T
python3 tools/legik.py $T/NeoCrimson.MMD $T/ik.MMD 402 extracted/CHDAT/MMD0/TYRA.MMD 8 --legs 2,3,4:21,23 5,6,7:24,26 --k 1.3 --neutral --slots $SLOTS
python3 tools/footfix.py plant $T/ik.MMD $O/NeoCrimson.MMD 402 --slots $SLOTS
cp $T/NeoCrimson.TIM $O/NeoCrimson.TIM
