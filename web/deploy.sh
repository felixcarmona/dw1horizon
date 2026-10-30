#!/usr/bin/env bash
# Publishes web/ to this host's nginx root for dw1horizon.com.
#   web/deploy.sh          regenerate data/discs.json from tools/discs.py (its languages checked against RELEASE's
#                          recipe), then copy; the engine (ENGINE, default
#                          <main>/build/web-engine in the main checkout, made by web/build-engine.sh) goes to engine/
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
main=$(dirname "$(git -C "$here" rev-parse --path-format=absolute --git-common-dir)")
dest=/var/www/dw1horizon
# the languages the page says the disc plays in (discs.json languages) must be those of
# the release the engine builds (RELEASE, default <main>/build/web-release: its bundle's recipe), not of a working tree
release=${RELEASE:-$main/build/web-release}
metadata=()
if [ -f "$release/bundle/tools/derive/recipes/everything.json" ]; then
  metadata+=(--recipe "$release/bundle/tools/derive/recipes/everything.json")
fi
python3 "$here/../tools/discs.py" web-json "$here/data/discs.json" "${metadata[@]}"
if [ -f "$release/bundle/tools/derive/recipes/everything.json" ]; then
  python3 - "$here/data/discs.json" "$release/bundle/tools/derive/recipes/everything.json" <<'PY'
import json, sys
page = json.load(open(sys.argv[1])).get('languages') or []
rel = [x for x in (json.load(open(sys.argv[2]))['environment'].get('LANGS') or '').split(',') if x]
if sorted(page) != sorted(rel):
    sys.exit(f'deploy: the page says {",".join(page)}, the release plays in {",".join(rel)}: run from the checkout the release was made from')
PY
fi
rsync -a --delete --exclude deploy.sh --exclude build-engine.sh --exclude README.md --exclude /enginebuild --exclude /test \
  --exclude /propuestas --exclude /engine --exclude /media/clips "$here/" "$dest/"
engine=${ENGINE:-$main/build/web-engine}
if [ -f "$engine/current.json" ]; then
  # the versioned folders first, current.json last (a page never reads a version that is not all there)
  rsync -a --delete --exclude current.json "$engine/" "$dest/engine/"
  cp "$engine/current.json" "$dest/engine/current.json"
  echo "engine $(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$engine/current.json")"
fi
echo "deployed to $dest → https://dw1horizon.com/"

# ---- the showcase clips (not in git): build/web-media of the main checkout, supplied separately,
# published as media/clips/; the page rsync above leaves that folder alone (--exclude /media/clips)
media=${MEDIA:-$main/build/web-media}
if [ -d "$media" ]; then
  mkdir -p "$dest/media/clips"
  rsync -a --delete "$media/" "$dest/media/clips/"
  echo "clips $(ls "$media" | wc -l) files, $(du -sh "$media" | cut -f1)"
fi
