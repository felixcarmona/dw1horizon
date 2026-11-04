#!/usr/bin/env python3
"""The C patch series: `mods/patches/series` lists the patch files in the order `git am` applies them, one file name
per line. Every tool that applies or reads the patches takes the order from here, never from a directory listing.

  python3 tools/patch_series.py list [core|all]   the patch paths in order (relative to the checkout); core = the
                                                  patches before the first merge patch (tools/mods.sh prepare mods)
  python3 tools/patch_series.py check             the series file, the patch files and index.md's rows agree (no
                                                  disc, no decomp)
  python3 tools/patch_series.py check --apply     also applies the whole series to the pinned decompilation in a
                                                  temporary worktree (needs the decomp/ submodule, no disc data)

The series file is plain: no blank lines, no comments, every line ends with a newline. It and index.md (one table row
per patch, in the series order) are merged with git's union driver (.gitattributes), so two branches that each append a
patch both keep their lines; `check` catches what a union merge can leave wrong (a name twice, two versions of one
row), and `--apply` whether the two patches still apply one after the other.
"""
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIR = 'mods/patches'
SERIES = DIR + '/series'
INDEX = DIR + '/index.md'
ROW = re.compile(r'^\| `([^`]+)` \|')


def names(root=ROOT):
    """The patch file names of the series, in order."""
    return (Path(root) / SERIES).read_text(encoding='utf-8').splitlines()


def paths(root=ROOT, core=False):
    """The patch files of the series, in order; core: only those before the first merge patch."""
    out = []
    for name in names(root):
        if core and 'Merge-branch' in name:
            break
        out.append(Path(root) / DIR / name)
    return out


def problems(root=ROOT):
    """What is wrong with the series file against the patch files (an empty list when they agree)."""
    root = Path(root)
    text = (root / SERIES).read_text(encoding='utf-8')
    errs = []
    if text and not text.endswith('\n'):
        errs.append(f'{SERIES}: the last line has no newline')
    seen = set()
    for n, name in enumerate(text.splitlines(), 1):
        where = f'{SERIES}:{n}'
        if name != name.strip() or not name:
            errs.append(f'{where}: blank line or surrounding spaces: {name!r}')
        elif '/' in name or not name.endswith('.patch') or name.startswith(('.', '#')):
            errs.append(f'{where}: not a patch file name: {name!r}')
        elif name in seen:
            errs.append(f'{where}: {name} is listed twice (a union merge of the same line from two branches?)')
        elif not (root / DIR / name).is_file():
            errs.append(f'{where}: {name} does not exist')
        seen.add(name)
    for p in sorted((root / DIR).glob('*.patch')):
        if p.name not in seen:
            errs.append(f'{DIR}/{p.name}: not in {SERIES} (append its name there)')
    rows = [m.group(1) for m in map(ROW.match, (root / INDEX).read_text(encoding='utf-8').splitlines()) if m]
    listed = text.splitlines()
    for name in sorted(set(rows)):
        if rows.count(name) > 1:
            errs.append(f'{INDEX}: {rows.count(name)} rows for {name} (keep one)')
    for name in listed:
        if name not in rows:
            errs.append(f'{INDEX}: no row for {name} (add it at the end)')
    for name in rows:
        if name not in listed:
            errs.append(f'{INDEX}: a row for {name}, which is not in {SERIES}')
    if not errs and rows != listed:
        errs.append(f'{INDEX}: the rows are not in the order of {SERIES}')
    return errs


def apply(root=ROOT, decomp=None):
    """git am the whole series onto the pinned decompilation commit in a temporary worktree; returns the tree id."""
    root = Path(root)
    decomp = Path(decomp or root / 'decomp')
    pin = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD:decomp'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='patch-series-') as tmp:
        tree = Path(tmp) / 'decomp'
        subprocess.run(['git', '-C', str(decomp), 'worktree', 'add', '-q', '--detach', str(tree), pin], check=True)
        try:
            series = paths(root)
            r = subprocess.run(['git', '-C', str(tree), '-c', 'user.name=Horizon authors', '-c', 'user.email=',
                                'am', '-q', *map(str, series)], capture_output=True, text=True)
            if r.returncode:
                subprocess.run(['git', '-C', str(tree), 'am', '--abort'], capture_output=True)
                sys.stderr.write(r.stdout + r.stderr)
                m = re.search(r'Patch failed at (\d+)', r.stdout + r.stderr)
                which = f'{DIR}/{series[int(m.group(1)) - 1].name}' if m else 'the patch that failed'
                raise SystemExit(f'the series does not apply to the pinned decompilation at {which}: regenerate it on '
                                 'top of the patches before it (tools/mods.sh prepare int)')
            return subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
        finally:
            subprocess.run(['git', '-C', str(decomp), 'worktree', 'remove', '--force', str(tree)], check=True)


def main(argv):
    cmd = argv[0] if argv else ''
    if cmd == 'list' and len(argv) <= 2 and (argv[1:] or ['all'])[0] in ('core', 'all'):
        for p in paths(core=argv[1:] == ['core']):
            print(os.path.relpath(p, ROOT))
    elif cmd == 'check' and argv[1:] in ([], ['--apply']):
        errs = problems()
        for e in errs:
            print(e, file=sys.stderr)
        if errs:
            return 1
        print(f'{SERIES}: {len(names())} patches, every file listed once')
        if argv[1:] == ['--apply']:
            print(f'applied to the pinned decompilation: tree {apply()}')
    else:
        sys.exit(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
