#!/bin/sh
# Generate the art of the cards in content/cards/new.json that have no original yet, retrying on rate limits.
# usage: tools/generate_cards.sh KEY [KEY...]   (run from the repository root; needs the Gemini key of cardmaker.py)
# Originals land in build/cards-originals/<key>.png (CARD_ORIGINALS overrides); the prompt and settings of each go
# next to it as <key>.json (kept in content/cards/generation/). Then: python3 tools/cardmaker.py reduce KEY.
PY=${PYTHON:-python3}
for k in "$@"; do
  dir=${CARD_ORIGINALS:-build/cards-originals}
  [ -f "$dir/$k.png" ] && continue
  ok=0
  for t in 1 2 3 4 5; do
    "$PY" tools/cardmaker.py gen "$k" && [ -f "$dir/$k.png" ] && { ok=1; break; }
    sleep $((30 * t))
  done
  [ $ok = 1 ] || echo "FAILED $k" >&2
done
