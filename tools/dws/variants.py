#!/usr/bin/env python3
"""EXTENDED STORY (patch 0199, docs/mods/options.md): the disc files a story mod changes, and their copies as the
original story has them.

A disc built with a story mod (tools/build-full.sh EXTRA_STORY) keeps the extended story under the disc's own names and
puts beside it a copy of every file the mods change, as the story without them has it: the script text compiled again
without the mods (_G.SCN, _APHEAD.SCN; build-full.sh adds those) and the map files (.MAP, .TFS) the mods retouched or
the story compiler edited for them. With EXTENDED STORY off the executable reads the copies (modStoryFile in
mod_options.c).

  python3 -m tools.dws.variants plan -o DIR [--ext DEST=SRC ...] [--base DEST=SRC ...]
        --ext: the files the extended story puts on the disc, in build-disc.py's order (the last one of a DEST wins): the
        retouched maps (EXTRA_FILES), then the story compiler's (its FILE: lines); --base: the story compiler's files of
        the story without the mods. A DEST the base list lacks is the disc's own file (extracted/). Every DEST whose two
        files differ gets a copy DIR/_AME.EXT of the base one. Prints, per copy:
          --add<TAB>DIRECTORY/_AME.EXT=DIR/_AME.EXT     (build-disc.py's option; the copy sits beside the file)
          COPY<TAB>DEST<TAB>_AME.EXT<TAB>EXT_SRC<TAB>BASE_SRC  (for the sign copies, tools/localize/signs.py --file)
  python3 -m tools.dws.variants finish -o DIR --plan PLAN [--base DEST=SRC ...]
        writes each copy again from the last --base file of its DEST (the base story compiler's files, then the balance
        maps of tools/balance.py build for it), or the disc's own file.
In Python: plan(out, ext, base) -> rows and finish(out, rows, base): tools/derive's storycopies step  calls both in
one go, after its story and balance steps (the balance maps are made before the executable since 2026-10-26).

Names: the file's name with an underscore for its first letter (MAYO03.MAP -> _AYO03.MAP): the executable finds a copy by
that rule, with no table (each row would cost its heap). A name another disc file already has, or two copies' that
meet, stops the build (the game looks files up by name only).
"""
import argparse, filecmp, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTRACTED = os.path.join(ROOT, 'extracted')


def pairs(specs):
    """DEST=SRC options -> {DEST: SRC}, the last one of a DEST winning (build-disc.py's order)"""
    out = {}
    for s in specs or []:
        dest, src = s.split('=', 1)
        out[dest] = src
    return out


def copy_name(name):
    """the original story's copy of the disc file `name` (modStoryFile's rule)"""
    return '_' + name[1:]


def disc_file(dest):
    p = os.path.join(EXTRACTED, dest)
    return p if os.path.isfile(p) else None


def plan(out, ext, base):
    """The copies (plan): ext, base {DEST: SRC} as above -> [(DEST, copy name, ext file, base file)] in DEST order, each
    copy written into out from its base file."""
    os.makedirs(out, exist_ok=True)
    taken = {f for _, _, fs in os.walk(EXTRACTED) for f in fs}
    rows = []
    for dest in sorted(set(ext) | set(base)):
        if not dest.upper().endswith(('.MAP', '.TFS')) or disc_file(dest) is None:
            continue                         # a new file (a new screen's): only the extended story reaches it
        e = ext.get(dest) or disc_file(dest)
        b = base.get(dest) or disc_file(dest)
        if filecmp.cmp(e, b, shallow=False):
            continue
        name = copy_name(os.path.basename(dest))
        if name in taken:
            raise SystemExit(f'{dest}: its copy\'s name {name} is taken on the disc')
        taken.add(name)
        shutil.copyfile(b, os.path.join(out, name))
        rows.append((dest, name, e, b))
    return rows


def plan_lines(out, rows):
    """plan()'s rows as the command prints them (the --add and COPY lines)."""
    lines = []
    for dest, name, e, b in rows:
        copy = os.path.join(out, name)
        lines += [f'--add\t{os.path.dirname(dest)}/{name}={copy}', f'COPY\t{dest}\t{name}\t{e}\t{b}']
    return lines


def finish(out, rows, base):
    """Each copy of rows written again from the last base file of its DEST (base {DEST: SRC}), or the disc's own file
    -> the number rewritten."""
    n = 0
    for dest, name, *_ in rows:
        src = base.get(dest) or disc_file(dest)
        copy = os.path.join(out, name)
        if not filecmp.cmp(src, copy, shallow=False):
            shutil.copyfile(src, copy)
            n += 1
    return n


def cmd_plan(a):
    for line in plan_lines(a.o, plan(a.o, pairs(a.ext), pairs(a.base))):
        print(line)


def cmd_finish(a):
    rows = [tuple(f[1:5]) for f in (l.rstrip('\n').split('\t') for l in open(a.plan)) if f[0] == 'COPY']
    n = finish(a.o, rows, pairs(a.base))
    print(f'original story copies: {n} rewritten from the balance step')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('-o', required=True)
    p.add_argument('--ext', action='append')
    p.add_argument('--base', action='append')
    p = sub.add_parser('finish')
    p.add_argument('-o', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--base', action='append')
    a = ap.parse_args()
    {'plan': cmd_plan, 'finish': cmd_finish}[a.cmd](a)


if __name__ == '__main__':
    main()
