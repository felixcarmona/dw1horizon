#!/usr/bin/env python3
"""New disc files with new names (patch 0147): what a build adds to the disc and to FILE_OFFSET_TABLE.

The executable finds a data file by its name only (lookupFileTable, file.c: the text after the last '\\' is looked up in
FILE_OFFSET_TABLE). A file whose name the table lacks (a new screen's .MAP and .TFS, a model, a texture) needs an entry:
the Makefile's NEW_FILES makes one per name after the mod entries (src/main/file_table_us.c, file_table_new.h), and
build-disc.py --relayout writes its sector and size. This tool decides, for the files a build puts on the disc, which
replace a file of the disc (--file), which are new (--add) and which names the executable must be built with.

  newfiles.py plan [--table FILE_TABLE_US.C] [--screens DIR ...] [--file DEST=SRC ...] [--add DEST=SRC ...]
        --file DEST=SRC: a file for the disc (DEST relative to its root, e.g. MAP/NEW/RIFT01.MAP). DEST on the disc already: it
        replaces that file; else it is a new file in that directory (made if missing). --add DEST=SRC: always a new file.
        Screens: the screen files >= 255 of content/screens and each --screens DIR (tools/screens.py); a screen's "file" names its
        .MAP and .TFS: on the disc already (an original map, e.g. MGEN17), given above, or beside its screen file
        (DIR/<file>.MAP, DIR/<file>.TFS, placed in MAP/NEW/); anything else stops the build.
        Prints one line per file, "--file<TAB>DEST=SRC" or "--add<TAB>DEST=SRC" (build-disc.py's options), and last
        "NEW_FILES<TAB>NAME NAME ..." (the names --table lacks: make NEW_FILES=...).

Names: 8.3 upper case (A-Z 0-9 _; the disc is ISO 9660 level 1, so a new name has at most 8 characters before the dot,
not the 9 a MAP_ENTRIES row holds), unique across the whole disc (the lookup ignores the directory) and among the new
files. Each name costs about 24 bytes of the executable's .data (the entry and its string), checked by the link's
MIN_HEAP assert like any other data.
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screens  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, 'extracted')
NAME_RE = re.compile(r'[A-Z0-9_]{1,8}\.[A-Z0-9_]{1,3}')
DIR_RE = re.compile(r'[A-Z0-9_]{1,8}')
SCREEN_MAP_DIR = 'MAP/NEW'


class PlanError(Exception):
    pass


def disc_paths():
    """{DEST: basename} of every file of the extracted disc."""
    out = {}
    for dp, _, fs in os.walk(EXTRACTED):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), EXTRACTED).replace(os.sep, '/')
            out[rel] = f
    return out


def table_names(path):
    """The names of a FILE_OFFSET_TABLE source (file_table_us.c), the mod entries included."""
    return set(re.findall(r'\{\s*0x[0-9a-fA-F]+,\s*0x[0-9a-fA-F]+,\s*"([^"]+)"\s*\}', open(path).read())) - {'NULL'}


def check_dest(dest):
    parts = dest.split('/')
    if not NAME_RE.fullmatch(parts[-1]):
        raise PlanError(f'{dest}: a new file has an 8.3 upper-case name (A-Z 0-9 _, at most 8 characters before the dot)')
    for d in parts[:-1]:
        if not DIR_RE.fullmatch(d):
            raise PlanError(f'{dest}: directory "{d}" is not an ISO 9660 name (A-Z 0-9 _, at most 8 characters)')


def plan(specs, adds=(), screen_dirs=(), table=None, names=None):
    """[(option, DEST, SRC)] and the sorted new names the table lacks (table: file_table_us.c, or names: its names, as
    tools/derive's facts give them)."""
    disc = disc_paths()
    disc_names = {}
    for rel, base in disc.items():
        disc_names.setdefault(base, rel)
    out, new_by_name = [], {}
    def add(dest, src, why):
        check_dest(dest)
        base = dest.split('/')[-1]
        if base in disc_names:
            raise PlanError(f'{dest} ({why}): the disc already has a file named {base} ({disc_names[base]}); names are unique '
                            'across the disc (the game looks files up by name only): give it another name')
        if base in new_by_name:
            raise PlanError(f'{dest} ({why}): {base} is already a new file ({new_by_name[base]})')
        if not os.path.isfile(src):
            raise PlanError(f'{dest} ({why}): no file {src}')
        new_by_name[base] = dest
        out.append(('--add', dest, src))
    for spec in specs:
        dest, src = spec.split('=', 1)
        if dest in disc:
            out.append(('--file', dest, src))
        else:
            add(dest, src, 'EXTRA_FILES')
    for spec in adds:
        dest, src = spec.split('=', 1)
        add(dest, src, '--add')
    if screen_dirs is not None:
        for i, x in sorted(screens.load(screen_dirs).items()):
            if x.get('fileBytes'): continue
            for ext in ('MAP', 'TFS'):
                name = f'{x["file"]}.{ext}'
                if name in disc_names or name in new_by_name: continue
                beside = os.path.join(os.path.dirname(x['_path']), name)
                if os.path.isfile(beside):
                    add(f'{SCREEN_MAP_DIR}/{name}', beside, f'screen {i}')
                    continue
                raise PlanError(f'{x["_path"]}: screen {i} names "{x["file"]}", but there is no {name} on the disc, in '
                                f'EXTRA_FILES or beside the screen file')
    have = set(names) if names is not None else table_names(table) if table else set()
    return out, sorted(n for n in new_by_name if n not in have)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan'); p.add_argument('--file', dest='specs', action='append', default=[])
    p.add_argument('--add', action='append', default=[])
    p.add_argument('--table'); p.add_argument('--screens', action='append', default=[])
    a = ap.parse_args()
    try:
        files, names = plan(a.specs, a.add, a.screens, a.table)
    except (PlanError, screens.ScreenError) as e:
        sys.exit(f'newfiles.py: {e}')
    for opt, dest, src in files:
        print(f'{opt}\t{dest}={src}')
    print('NEW_FILES\t' + ' '.join(names))


if __name__ == '__main__':
    main()
