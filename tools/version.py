#!/usr/bin/env python3
"""The release version and date of a build, from the repository's git tags (the one rule every place uses: the game's
title screens, make-release's manifest, the patcher's first line, the web page; docs/patcher.md "Making a release").

A release is an annotated tag vMAJOR.MINOR.PATCH (git tag -a v0.1.0 -m "..."). The version of a build of HEAD is

  X.Y.Z                    HEAD is the commit of the latest such tag reachable from it (a release build)
  X.Y.Z-dev.N+HHHHHHHH     N commits after that tag, HHHHHHHH the first 8 hex digits of HEAD (a development build)
  0.0.0-dev.N+HHHHHHHH     no tag yet: N = the commits of HEAD

and its date (UTC, YYYY-MM-DD) is the tag's date for a release build, else the date of HEAD's commit. Only HEAD and the
tags count (not the working tree's changes): the same commit gives the same version, so its build gives the same
bytes. Lightweight tags and tags of another form are ignored. Without git or checkout metadata,
the version is 0.0.0-dev+unknown and its date and commit are unknown (None).

  python3 tools/version.py                 {"version": ..., "date": ..., "tag": ..., "commit": ...}
  python3 tools/version.py version|date|game   one field; game = "v" + version, the text the title screens draw
"""
import datetime
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')
GAME_MAX = 31          # the executable's MOD_VERSION_TEXT holds 31 characters (patch 0257, src/main/main.c)


def _git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True, text=True).stdout.strip()


def _day(unix):
    return datetime.datetime.fromtimestamp(int(unix), datetime.timezone.utc).strftime('%Y-%m-%d')


def describe(repo=REPO):
    """{'version', 'date', 'tag' (None without one), 'commit' (full hash)} of HEAD in `repo`."""
    try:
        head = _git(repo, 'rev-parse', 'HEAD')
    except (OSError, subprocess.CalledProcessError):
        # Source archives and build hosts without git still build reproducibly.
        return dict(version='0.0.0-dev+unknown', date=None, tag=None, commit=None)
    tag, skip = None, []
    while True:   # annotated tags only (no --tags): the nearest reachable one of the form vX.Y.Z
        try:
            t = _git(repo, 'describe', '--abbrev=0', '--match', 'v[0-9]*', *(f'--exclude={s}' for s in skip), 'HEAD')
        except subprocess.CalledProcessError:
            break
        if TAG.match(t):
            tag = t
            break
        skip.append(t)   # (a name the glob lets through, v1.2.3-rc: not a release)
    if tag:
        n = int(_git(repo, 'rev-list', '--count', f'{tag}..HEAD'))
        base = tag[1:]
    else:
        n = int(_git(repo, 'rev-list', '--count', 'HEAD'))
        base = '0.0.0'
    if tag and n == 0:
        raw = _git(repo, 'for-each-ref', f'refs/tags/{tag}', '--format=%(taggerdate:raw)')
        return dict(version=base, date=_day(raw.split()[0]), tag=tag, commit=head)
    return dict(version=f'{base}-dev.{n}+{head[:8]}', date=_day(_git(repo, 'log', '-1', '--format=%ct', 'HEAD')),
                tag=tag, commit=head)


def game_text(info):
    """The title screens' text: v + the version (at most GAME_MAX characters)."""
    return ('v' + info['version'])[:GAME_MAX]


def main(argv):
    info = describe()
    if not argv:
        print(json.dumps(info, indent=1))
    elif argv[0] in ('version', 'date', 'tag', 'commit'):
        print(info[argv[0]] or '')
    elif argv[0] == 'game':
        print(game_text(info))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
