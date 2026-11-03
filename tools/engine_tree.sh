#!/usr/bin/env bash
# The engine as a reader sees it: the pinned decompilation with every patch of mods/patches applied, one commit each, on
# a branch that a fork of the decompilation can publish. mods/patches stays the source: this branch is generated and
# never edited by hand. It holds no disc data: asm and generated files stay out, as in the decompilation itself.
#
#   tools/engine_tree.sh build [DIR]        creates DIR (default build/engine-tree), branch "horizon", and checks it
#   tools/engine_tree.sh push TAG REMOTE    pushes that branch and the tag horizon-TAG to REMOTE (needs DW1H_PUBLISH=1)
#
# Every commit carries the date of the build. A new build rewrites the branch, so a push
# replaces the published one (--force-with-lease).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
NAME="Horizon authors"
EMAIL="1969778+felixcarmona@users.noreply.github.com"

build() {
  W=${1:-build/engine-tree}
  BASE=$(git rev-parse HEAD:decomp)
  rm -rf "$W"
  git clone -q --no-checkout "${DECOMP_SOURCE:-$(git config -f .gitmodules submodule.decomp.url)}" "$W"
  git -C "$W" checkout -q -B horizon "$BASE"
  git -C "$W" config user.name "$NAME"
  git -C "$W" config user.email "$EMAIL"
  git -C "$W" am -q "$ROOT"/mods/patches/*.patch
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  FILTER_BRANCH_SQUELCH_WARNING=1 git -C "$W" filter-branch -f --env-filter "
    export GIT_AUTHOR_NAME='$NAME' GIT_AUTHOR_EMAIL='$EMAIL' GIT_COMMITTER_NAME='$NAME' GIT_COMMITTER_EMAIL='$EMAIL'
    export GIT_AUTHOR_DATE='$NOW' GIT_COMMITTER_DATE='$NOW'
  " "$BASE"..horizon >/dev/null
  export GIT_AUTHOR_NAME="$NAME" GIT_AUTHOR_EMAIL="$EMAIL" GIT_COMMITTER_NAME="$NAME" GIT_COMMITTER_EMAIL="$EMAIL"
  export GIT_AUTHOR_DATE="$NOW" GIT_COMMITTER_DATE="$NOW"
  cat > "$W/HORIZON.md" <<NOTE
# Digimon World: Horizon, engine source

This branch is generated: the decompilation at $BASE with the patch series of
[Digimon World: Horizon](https://dw1horizon.com) applied, one commit per patch. To read a change, use
\`git log\` or \`git blame\` here. To change the engine, send a patch to that repository's \`mods/patches\`: this branch is
rebuilt from it by \`tools/engine_tree.sh\`, so a commit made here is lost.

It holds no disc data. Building it needs the steps in that repository's \`docs/building.md\`. The decompilation is by
its own authors under its MIT licence ([LICENSE](LICENSE)).
NOTE
  git -C "$W" add HORIZON.md
  git -C "$W" commit -q -m "Say that this branch is generated"
  check "$W" "$BASE"
  echo "engine tree ready in $W: $(git -C "$W" rev-list --count "$BASE"..horizon) commits, tip $(git -C "$W" rev-parse --short horizon)"
}

check() {
  W=$1; BASE=$2
  emails=$(git -C "$W" log "$BASE"..horizon --format='%ae%n%ce' | sort -u)
  [ "$emails" = "$EMAIL" ] || { echo "unexpected commit identity: $emails" >&2; exit 1; }
  if git -C "$W" diff --numstat "$BASE" horizon | grep -q '^-'; then
    echo "binary files in the series:" >&2
    git -C "$W" diff --numstat "$BASE" horizon | grep '^-' >&2
    exit 1
  fi
  if git -C "$W" ls-files | grep -E '^(asm|disks|build)/|\.(bin|BIN|cue|iso|TIM|MMD|STD|VB|VH)$' | grep -v '^disks/.*\.xml$' | grep -q .; then
    echo "disc files in the tree" >&2; exit 1
  fi
  if git -C "$W" diff "$BASE" horizon | grep -E '^\+' | grep -qE '/home/[a-z]|192\.168\.'; then
    echo "a private path in the series" >&2; exit 1
  fi
}

case "${1:-}" in
  build) build "${2:-}" ;;
  push)
    [ "${DW1H_PUBLISH:-}" = 1 ] || { echo "publishing needs DW1H_PUBLISH=1" >&2; exit 1; }
    W=build/engine-tree
    git -C "$W" tag -f "horizon-$2" horizon >/dev/null
    # A fresh build has no remote-tracking branch, so a bare lease is always stale: lease on the tip the remote has now.
    old=$(git -C "$W" ls-remote "$3" refs/heads/horizon | cut -f1)
    git -C "$W" push --force-with-lease="horizon:$old" "$3" horizon "horizon-$2" ;;
  *) sed -n 2,9p "$0" >&2; exit 1 ;;
esac
