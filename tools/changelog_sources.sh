#!/usr/bin/env bash
# Read-only material for writing a player-facing changelog. Requires git and gh.
set -euo pipefail
previous=${1:-$(git tag --list 'v*' --sort=-version:refname | sed -n '1p')}
if [[ -z "$previous" ]]; then
  echo 'No v* tag found; pass the previous tag explicitly.' >&2
  exit 1
fi
git rev-parse --verify "refs/tags/$previous^{commit}" >/dev/null
main=origin/main
git rev-parse --verify "$main" >/dev/null 2>&1 || main=main
range="$previous..$main"
# Keep commit text in arrays, never evaluate it as shell code.
prs=()
direct=()
while IFS= read -r commit; do
  subject=$(git show -s --format=%s "$commit")
  if [[ "$subject" =~ ^Merge\ pull\ request\ \#([0-9]+) ]]; then
    number=${BASH_REMATCH[1]}
  else
    # Squash/rebase merges also have a PR association. A direct commit has none.
    number=$(gh api "repos/{owner}/{repo}/commits/$commit/pulls" --jq '[.[] | select(.merged_at != null)] | .[0].number // empty')
  fi
  if [[ -n "$number" ]]; then
    if [[ " ${prs[*]-} " != *" $number "* ]]; then prs+=("$number"); fi
  else
    direct+=("$commit $subject")
  fi
done < <(git rev-list --first-parent --reverse "$range")
printf 'Pull requests since %s\n\n' "$previous"
for number in "${prs[@]}"; do
  gh pr view "$number" --json number,title,body --template '#{{.number}} {{.title}}{{"\n"}}{{.body}}{{"\n\n"}}'
done
printf '\nCommits without a pull request\n\n'
if ((${#direct[@]})); then printf '%s\n' "${direct[@]}"; fi
printf '\nDiff stat\n\n'
git diff --stat "$previous" "$main"
