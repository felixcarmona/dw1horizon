"""Game symbol resolution for the executable running in the emulator.

The original executable and the GCC build place variables at different
addresses. `resolve(name)` returns the right address for `build`:
  'orig' -> decomp/config/us/symbols.txt
  'gcc'  -> linker map decomp/build/us/psx/gcc/SLUS_010.32.elf.map
`detect_build(ram)` works it out by comparing the code loaded in RAM with the
original executable in extracted/.

"NAME+0x10" and literal addresses ("0x80134EB8") are accepted.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, re, sys

ROOT = _DEV_ROOT
SYMS = os.path.join(ROOT, 'decomp/config/us/symbols.txt')
MAP = os.path.join(ROOT, 'decomp/build/us/psx/gcc/SLUS_010.32.elf.map')
ORIG_EXE = os.path.join(ROOT, 'extracted/SLUS_010.32')
_cache = {}


def table(build):
    if build in _cache: return _cache[build]
    t = {}
    if build != 'orig':
        for line in open(CANDIDATES[build][1]):
            m = re.match(r'\s+(0x[0-9a-f]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', line)
            if m: t[m.group(2)] = int(m.group(1), 16)
    else:
        for line in open(SYMS):
            m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+);', line)
            if m: t[m.group(1)] = int(m.group(2), 16)
    _cache[build] = t
    return t


def resolve(expr, build='orig'):
    expr = expr.strip()
    m = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s*(?:([+-])\s*(0x[0-9A-Fa-f]+|\d+))?', expr)
    if m and not re.fullmatch(r'0x[0-9A-Fa-f]+|\d+', expr):
        t = table(build)
        if m.group(1) not in t: raise KeyError(f'symbol {m.group(1)} not found ({build})')
        off = int(m.group(3), 0) if m.group(3) else 0
        return t[m.group(1)] + (off if m.group(2) != '-' else -off)
    return int(expr, 0)


# Known executables: name -> (executable file, symbol source)
CANDIDATES = {
    'orig': (ORIG_EXE, None),
    'gcc': (os.path.join(ROOT, 'decomp/build/us/psx/gcc/SLUS_010.32'), MAP),
    'mods': (os.path.join(ROOT, 'build/decomp-mods/build/us/psx/gcc/SLUS_010.32'),
             os.path.join(ROOT, 'build/decomp-mods/build/us/psx/gcc/SLUS_010.32.elf.map')),
}
# any other worktree build under build/decomp-*/ (experiments) is picked up too,
# named after its directory (e.g. 'decomp-full')
import glob as _glob
for _d in sorted(_glob.glob(os.path.join(ROOT, 'build/decomp-*'))):
    _name = os.path.basename(_d)
    if _name == 'decomp-mods': continue
    _exe = os.path.join(_d, 'build/us/psx/gcc/SLUS_010.32')
    if os.path.exists(_exe):
        CANDIDATES[_name] = (_exe, _exe + '.elf.map')
# the executable a disc was built with (tools/build-full.sh keeps it in build/<name>/exe/): 'disc-<name>', so a
# session testing build/<name>.cue keeps the right symbols while build/decomp-*/ is rebuilt by somebody else
for _m in sorted(_glob.glob(os.path.join(ROOT, 'build/*/exe/SLUS_010.32.elf.map'))):
    _exe = _m[:-len('.elf.map')]
    if os.path.exists(_exe):
        CANDIDATES['disc-' + os.path.basename(os.path.dirname(os.path.dirname(_m)))] = (_exe, _m)


def _mismatches(ram, exe):
    """Words of the executable's whole text image that differ from RAM."""
    load = int.from_bytes(exe[0x18:0x1C], 'little') & 0x1FFFFFFF
    n = int.from_bytes(exe[0x1C:0x20], 'little')
    a, b = ram[load:load + n], exe[0x800:0x800 + n]
    if a == b: return 0
    # the BIOS patches a few library functions and the data part changes at run time
    return sum(1 for i in range(0, n, 4) if a[i:i + 4] != b[i:i + 4])


def explicit_build(spec):
    """Candidate name for an explicit choice: a name in CANDIDATES, a worktree
    directory (build/decomp-x or a path to it) or a path to the executable."""
    if spec in CANDIDATES: return spec
    if 'decomp-' + spec in CANDIDATES: return 'decomp-' + spec
    for exe in (spec, os.path.join(spec, 'build/us/psx/gcc/SLUS_010.32')):
        if os.path.isfile(exe) and os.path.exists(exe + '.elf.map'):
            name = os.path.abspath(exe)
            CANDIDATES[name] = (name, name + '.elf.map')
            return name
    raise KeyError(f'unknown build {spec!r}; known: {", ".join(CANDIDATES)}')


def rank_builds(ram):
    """[(mismatching words, name)] over the whole text, best first."""
    out = []
    for name, (exe_path, _) in CANDIDATES.items():
        try: exe = open(exe_path, 'rb').read()
        except OSError: continue
        out.append((_mismatches(ram, exe), name))
    return sorted(out)


def detect_build(ram, explicit=None, log=True):
    """Name of the executable running in RAM, or None if it has not loaded yet.

    An explicit choice (argument, else the DW_SYMS environment variable) wins:
    it is the safe way when worktrees are near-identical. Otherwise the whole
    text of every candidate is compared with RAM and the fewest mismatching
    words wins; builds with identical text (same symbols) tie harmlessly, but a
    tie between different symbol maps is reported and refused (None)."""
    spec = explicit or os.environ.get('DW_SYMS')
    if spec:
        name = explicit_build(spec)
        if log: print(f'dwsyms: build {name} (explicit)', file=sys.stderr)
        return name
    ranked = rank_builds(ram)
    if not ranked or ranked[0][0] > 0x20000: return None   # nothing close: not loaded yet
    best = ranked[0][0]
    tied = [n for m, n in ranked if m == best]
    maps = {tuple(sorted(table(n).items())) for n in tied}
    if len(maps) > 1:
        print(f'dwsyms: AMBIGUOUS build, {tied} all match RAM equally with different '
              f'symbols; set DW_SYMS=<name> or --syms', file=sys.stderr)
        return None
    if log:
        extra = f' (also identical: {", ".join(tied[1:])})' if len(tied) > 1 else ''
        print(f'dwsyms: build {tied[0]}, {best} mismatching words{extra}', file=sys.stderr)
    return tied[0]


def wide_ids(build):
    """Whether `build` has 16-bit screen ids (docs/reference/ids.md step 3): any worktree
    build whose include/dw/ids.h declares `typedef int16_t ScreenId`."""
    if build in (None, 'orig'): return False
    if build.startswith('disc-'):                              # a disc's own executable: wide ids if the disc carries SCRN.DAT (screens >= 255)
        return os.path.isfile(os.path.join(ROOT, 'build', build[5:], 'SCRN.DAT'))
    d = os.path.join(ROOT, 'build/decomp-mods' if build == 'mods' else
                     'decomp' if build == 'gcc' else os.path.join('build', build))
    if os.path.isabs(build) and os.path.isfile(build):
        # A packaged disc keeps its executable in build/NAME/exe (or exe-LANG),
        # rather than a decomp worktree's build/us/psx/gcc. Use the same marker
        # as disc-NAME before looking for a decomp header four levels up.
        if os.path.isfile(os.path.join(os.path.dirname(build), '..', 'SCRN.DAT')):
            return True
        d = os.path.normpath(os.path.join(os.path.dirname(build), '..', '..', '..', '..'))
    try:
        return 'typedef int16_t ScreenId' in open(os.path.join(d, 'include/dw/ids.h')).read()
    except OSError:
        return False
