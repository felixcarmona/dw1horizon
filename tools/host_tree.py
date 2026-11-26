"""The patched decompilation tree the host-compiled C tests read: the argument, else DW_SELFTEST_DECOMP, else the
first prepared build/decomp-dev or build/decomp-int. Without one the test skips (exit 0), as tools/selftest.sh does."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _current(tree):
    """True when the tree's last commit is the last patch of mods/patches/series: an older tree lacks later patches."""
    last = (ROOT / 'mods/patches/series').read_text().split()[-1].removesuffix('.patch')
    head = subprocess.run(['git', '-C', str(tree), 'log', '-1', '--format=%s'], capture_output=True, text=True).stdout
    squash = lambda t: re.sub(r'[^a-z0-9]', '', t.lower())
    n = min(len(squash(last)), len(squash(head)), 40)
    return n > 0 and squash(last)[:n] == squash(head)[:n]


def host_tree(*needs):
    """The tree to test, or exit 0 with a SKIP line when none is prepared (needs: files that must exist in it)."""
    if len(sys.argv) > 1:
        tree = Path(sys.argv[1])
    else:
        found = [Path(os.environ['DW_SELFTEST_DECOMP'])] if 'DW_SELFTEST_DECOMP' in os.environ else []
        found += [ROOT / 'build' / n for n in ('decomp-dev', 'decomp-int')]
        tree = next((t for t in found if (t / 'src/main/main.c').exists() and (t / '.git').exists() and _current(t)), found[0])
        if not _current(tree):
            print(f'SKIP: no patched decompilation tree is as current as mods/patches/series (DW_SELFTEST_DECOMP): {tree}')
            sys.exit(0)
    missing = [n for n in ('src/main/main.c',) + needs if not (tree / n).exists()]
    if missing:
        print(f'SKIP: needs a prepared patched decompilation tree (DW_SELFTEST_DECOMP): {tree} lacks {missing[0]}')
        sys.exit(0)
    return tree
