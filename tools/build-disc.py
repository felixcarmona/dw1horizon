#!/usr/bin/env python3
"""Builds a disc image: the layout of tools/disc-layout.xml filled from the build and extracted/.

Usage:
  build-disc.py NAME [--from DIR ...] [--file DEST=SRC ...] [--no-pad]
  build-disc.py layout [XML]      writes tools/disc-layout.xml from the mkpsxiso project tools/extract.sh made of
                                  the USA image (default build/digimonworld.xml); done once, the result is committed

  NAME              image name: build/NAME.bin + .cue (and build/disc-NAME/)
  --from DIR        copies onto the disc every file in DIR whose name is in the layout
                    (e.g. decomp/build/us/psx/gcc → SLUS_010.32 and *_REL.BIN)
  --file DEST=SRC   replaces one specific file (DEST its path on the disc,
                    e.g. SCN/DG.SCN=build/DG_mod.SCN)
  --add DEST=SRC    adds a new file: in the root of the disc, before MMM.DAT (e.g.
                    DIGI.DAT=build/species/DIGI.DAT), or in a directory, made if missing
                    (MAP/NEW/RIFT01.MAP=...); 8.3 upper-case names, unique across the disc.
                    Needs --relayout and an executable whose FILE_OFFSET_TABLE has an entry
                    with that name (the mod entries, or NEW_FILES: patch 0147,
                    tools/newfiles.py); the build stops when it has none
  --no-pad          do not zero-pad up to the original size
  --relayout        free layout: pads nothing (each file at its real size, new files
                    can be added) and rewrites FILE_OFFSET_TABLE inside the
                    executable with the real sector and size of each file. Needs the
                    executable's linker map (--map, by default the one in --from).
  --map FILE        linker map (.elf.map) of the executable that goes on the disc
  --derived MANIFEST  tools/derive's manifest (build/NAME/derived/manifest.json): every file given (--from, --file,
                    --add; the last of a DEST) must be one it lists, with its SHA-1, or one its plan says we author
                    (the executable, the overlays, LANGEN/LANGES.BIN and the overlays' Spanish copies); anything else
                    stops the build (rule: the disc carries no file made outside tools/derive, so the patcher can make
                    every one of them on the player's machine)
  --writer W        what writes the image: mkpsxiso (default when .tools/mkpsxiso is built: ~1 s) or python
                    (tools/isowriter.py, standard library only: the same bytes, ~35 s for the everything disc; with
                    --relayout the LBAs are computed first, the table rewritten, the image written once)
  --seek-order      lays the disc out for short seeks (needs --relayout): everything a map change
                    reads (CHDAT, DOOR, ETC*, SCN, SOUND, STDDAT, the overlays, the executable)
                    first, then MAP, then the 127 MB of movies, MMM.DAT last. In the original the
                    movies sit between MAP and SOUND/overlays, so each map load jumps ~110 000
                    sectors back and forth. Movies are found by name (CdSearchFile) and the rest
                    by the table, which --relayout rewrites.

The disc (rule): its files, their order, dates and types (the movies are "mixed": 2336-byte sectors), the volume
identifiers are read from the player's USA extraction project (build/digimonworld.xml);
the license entry and structural metadata come from tools/disc-layout.xml (no file contents). Each file of the layout comes from, in this order: a --file/--from of the build; SYSTEM.CNF is
written here (it boots SLUS_010.32, the name the build gives its executable whatever the base disc); the rest, the
game's data, from extracted/ by its path (any base disc laid out as the USA dump: tools/basedisc.py). The executable and
the overlays (*_REL.BIN) are the base release's own code: tools/build-full.sh gives every one of them from the build;
another caller that gives none gets extracted/'s (said on the output). The license sectors come from
extracted/license_data.dat.

By default each replaced file is padded up to its original size so that the LBAs
of the following files do not change: the game loads by absolute sector with its
own table (FILE_OFFSET_TABLE), not through the file system. A new file that takes
more sectors than the original stops the build unless --relayout is given (which
moves the later files and rewrites that table; DG.SCN, found by name with
CdSearchFile, may then grow freely: docs/mods/scripts.md "If DG.SCN grows").
"""
import argparse, os, re, shutil, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isolist
import isowriter
import discmeta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, 'extracted')
BUILD = os.path.join(ROOT, 'build')
MKPSXISO = os.path.join(ROOT, '.tools/mkpsxiso/build/mkpsxiso')
LAYOUT = os.path.join(ROOT, 'tools/disc-layout.xml')
DISC_TOKEN = '@DISC@'                                   # the layout's stand-in for the folder the disc is assembled in
# rule: the BIOS boots the file SYSTEM.CNF names; the USA disc's bytes (CR LF), the build's executable keeps the name
SYSTEM_CNF = b'BOOT = cdrom:\\SLUS_010.32;1\r\nTCB = 4\r\nEVENT = 16\r\nSTACK = 801FFFF0\r\n'
PROGRAM = re.compile(r'SLUS_010\.32|[A-Z0-9]+_REL\.BIN')  # the base release's code: the build gives its own


def write_layout(xml_path):
    """tools/disc-layout.xml from the mkpsxiso project dumpsxiso wrote (tools/extract.sh): the same text with the dump
    folder (../extracted, the source of the tree and of the license) replaced by DISC_TOKEN."""
    text = open(xml_path).read()
    if '../extracted' not in text: sys.exit(f'{xml_path}: no ../extracted in it (not the project tools/extract.sh writes)')
    open(LAYOUT, 'w').write(discmeta.redact(text.replace('../extracted', DISC_TOKEN)))
    print(f'{LAYOUT}: {len(layout_files(text))} files')


def layout_files(xml_text):
    """The disc's files in the layout's order: their paths on the disc (DIR/SUB/NAME)."""
    import xml.etree.ElementTree as ET
    out = []
    def walk(node, pre):
        for e in node:
            if e.tag == 'file': out.append(pre + e.get('name'))
            elif e.tag == 'dir': walk(e, pre + e.get('name') + '/')
    walk(ET.fromstring(xml_text).find('.//directory_tree'), '')
    return out


def main():
    if sys.argv[1:2] == ['layout']:
        return write_layout(sys.argv[2] if len(sys.argv) > 2 else os.path.join(BUILD, 'digimonworld.xml'))
    ap = argparse.ArgumentParser()
    ap.add_argument('--metadata-xml', default=os.path.join(BUILD, 'digimonworld.xml'),
                    help='player USA extraction project containing original volume identifiers')
    ap.add_argument('name'); ap.add_argument('--from', dest='dirs', action='append', default=[])
    ap.add_argument('--file', action='append', default=[]); ap.add_argument('--no-pad', action='store_true')
    ap.add_argument('--add', action='append', default=[])
    ap.add_argument('--relayout', action='store_true'); ap.add_argument('--map')
    ap.add_argument('--seek-order', action='store_true')
    ap.add_argument('--writer', choices=('mkpsxiso', 'python'))
    ap.add_argument('--derived')
    a = ap.parse_args()
    a.writer = a.writer or ('mkpsxiso' if os.path.exists(MKPSXISO) else 'python')
    for p, what in ((EXTRACTED, 'tools/extract.sh'),) + (((MKPSXISO, 'docs/building.md'),) if a.writer == 'mkpsxiso' else ()):
        if not os.path.exists(p): sys.exit(f'missing {p}: see {what}')
    try:
        layout = discmeta.resolve(open(LAYOUT).read(), a.metadata_xml)
    except ValueError as e:
        sys.exit(str(e))
    files = layout_files(layout)
    byname = {}
    for rel in files: byname.setdefault(rel.split('/')[-1], []).append(rel)
    disc = os.path.join(BUILD, 'disc-' + a.name)
    if os.path.exists(disc): shutil.rmtree(disc)
    os.makedirs(disc)
    repl = []
    for d in a.dirs:
        for f in sorted(os.listdir(d)):
            src = os.path.join(d, f)
            if os.path.isfile(src) and f in byname:
                for rel in byname[f]: repl.append((rel, src))
    for spec in a.file:
        dest, src = spec.split('=', 1); repl.append((dest, src))
    if a.derived:
        check_derived(a.derived, repl + [tuple(x.split('=', 1)) for x in a.add])
    given = {rel for rel, _ in repl}
    stray = sorted(given - set(files))
    if stray: sys.exit(f'--file {stray[0]}: not a file of the disc (tools/disc-layout.xml); a new file is --add')
    for rel in files:                                     # every file the build does not give: SYSTEM.CNF, extracted/
        dst = os.path.join(disc, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in given: continue
        if rel == 'SYSTEM.CNF': open(dst, 'wb').write(SYSTEM_CNF); continue
        src = os.path.join(EXTRACTED, rel)
        if not os.path.exists(src):
            sys.exit(f'{rel}: not in extracted/ and not given by --from/--file' +
                     (' (the executable and the overlays come from the build: --from its folder)' if PROGRAM.fullmatch(
                         rel) else ''))
        if PROGRAM.fullmatch(rel): print(f'{rel:28} from extracted/ (the base disc\'s, not the build\'s)')
        shutil.copy2(src, dst)
    shutil.copy2(os.path.join(EXTRACTED, 'license_data.dat'), os.path.join(disc, 'license_data.dat'))
    for rel, src in repl:
        dst = os.path.join(disc, rel); new = open(src, 'rb').read()
        base = os.path.join(EXTRACTED, rel)               # the size the file had: what the LBAs after it were laid out for
        if not os.path.exists(base) and not a.relayout:
            sys.exit(f'{rel}: not in extracted/, so the sectors it had are unknown: build the disc with --relayout')
        orig = os.path.getsize(base) if os.path.exists(base) else len(new)
        note = ''; more = -(-len(new) // 2048) - -(-orig // 2048)
        if more > 0 and not a.relayout:
            sys.exit(f'{rel}: {len(new)} bytes, {more} sectors more than the original ({orig}): the files after it would move '
                     'and the executable reads them by its own sector table (FILE_OFFSET_TABLE). Build the disc with '
                     '--relayout (an executable built from decomp and its linker map: tools/build-full.sh, '
                     'dws --exe mods|species|story-state); docs/mods/scripts.md "If DG.SCN grows"')
        elif more > 0:
            note = (f'  {more} sectors more than the original ({orig}): the files after it move, '
                    'FILE_OFFSET_TABLE is rewritten (--relayout)')
        elif len(new) > orig and not a.relayout:
            note = f'  larger than the original ({orig}) but in the same sectors: no LBA moves'
        elif not (a.no_pad or a.relayout) and len(new) < orig:
            new += b'\0' * (orig - len(new)); note = f'  (padded to {orig})'
        open(dst, 'wb').write(new); print(f'{rel:28} {len(new):9d}{note}')
    if not repl and not a.add: print('warning: no file was replaced')
    xml_text = layout.replace(DISC_TOKEN, 'disc-' + a.name)
    added = []
    for spec in a.add:
        dest, src = spec.split('=', 1)
        parts = dest.split('/'); base = parts[-1]
        if not re.fullmatch(r'[A-Z0-9_]{1,8}\.[A-Z0-9_]{1,3}', base) or \
                not all(re.fullmatch(r'[A-Z0-9_]{1,8}', d) for d in parts[:-1]):
            sys.exit(f'--add {dest}: an 8.3 upper-case name, in the root of the disc or in a directory (made if missing)')
        if not a.relayout: sys.exit('--add needs --relayout (the new file moves the files after it)')
        if base in byname or base in added:
            sys.exit(f'--add {dest}: the disc already has a file named {base} (names are unique across the disc: '
                     'the game looks files up by name only; to replace it use --file)')
        os.makedirs(os.path.join(disc, *parts[:-1]), exist_ok=True)
        shutil.copyfile(src, os.path.join(disc, *parts))
        xml_text = xml_add(xml_text, parts)
        added.append(base)
        print(f'{dest:28} {os.path.getsize(src):9d}  (new file)')
    if a.seek_order:
        if not a.relayout: sys.exit('--seek-order moves files: it needs --relayout')
        xml_text = seek_order(xml_text)
    xml = os.path.join(BUILD, f'digimonworld-{a.name}.xml')
    open(xml, 'w').write(xml_text)
    out = os.path.join(BUILD, a.name + '.bin')
    mp = None
    if a.relayout:
        mp = a.map or next((os.path.join(d, 'SLUS_010.32.elf.map') for d in a.dirs
                            if os.path.exists(os.path.join(d, 'SLUS_010.32.elf.map'))), None)
        if not mp: sys.exit('--relayout needs the linker map (--map or --from with SLUS_010.32.elf.map)')
    if a.writer == 'python':
        write_python(xml_text, disc, out, mp, added)
    else:
        mkiso(xml, out)
        if a.relayout:
            exe = os.path.join(disc, 'SLUS_010.32')
            before = patch_file_table(exe, mp, out, added)
            mkiso(xml, out)                               # the executable does not change size: same LBAs
            after = {r['path'].split('/')[-1]: r['lba'] for r in iso_files(out)}
            assert before == after, 'the LBAs changed when rewriting the table'
    print(f'image: {out} ({os.path.getsize(out)} bytes)')


def check_derived(path, given):
    """--derived: every (DEST, SRC) given, the last of a DEST winning, is tools/derive's (the manifest's SHA-1) or
    authored (the manifest's plan.authored)."""
    import hashlib, json
    m = json.load(open(path))
    authored = set(m.get('plan', {}).get('authored', ()))
    bad = []
    for dest, src in dict(given).items():
        if dest in authored:
            continue
        e = m['files'].get(dest)
        if e is None:
            bad.append(f'{dest}={src}: not made by tools/derive (not in {path}) and not authored')
            continue
        h = hashlib.sha1(open(src, 'rb').read()).hexdigest()
        if h != e['sha1']:
            bad.append(f'{dest}={src}: {h}, tools/derive\'s step {e["step"]} made {e["sha1"]} ({e["file"]})')
    if bad:
        sys.exit(f'--derived: {len(bad)} files the disc would carry are not tools/derive\'s:\n  ' + '\n  '.join(bad))
    print(f'--derived: {len(dict(given))} files, every one tools/derive\'s or authored')


def write_python(xml_text, disc, out, map_path=None, added=()):
    """The image of the mkpsxiso XML `xml_text` (its tree under the folder `disc`) by tools/isowriter.py. With a linker
    map (--relayout) FILE_OFFSET_TABLE is rewritten from the planned LBAs before the one write."""
    lay = isowriter.Layout(xml_text)
    files = isowriter.files_from_dir(lay, disc)
    if map_path:
        pl = isowriter.plan(lay, {k: os.path.getsize(v) for k, v in files.items()})
        exe_path = os.path.join(disc, 'SLUS_010.32')
        exe = bytearray(open(exe_path, 'rb').read())
        planned = table_from_plan(pl)
        report_table(isowriter.rewrite_file_table(exe, file_table_offset(map_path), planned), added)
        open(exe_path, 'wb').write(exe)
    pl, _ = isowriter.write(lay, files, out, license=os.path.join(disc, 'license_data.dat'))
    if map_path:
        got = {r['path'].split('/')[-1]: r['lba'] for r in iso_files(out)}
        assert got == {k: v[0] for k, v in table_from_plan(pl).items() if k != 'PSX.EXE'}, 'LBAs differ from the plan'


def table_from_plan(pl):
    """{file name: (lba, size)} of a planned disc, as FILE_OFFSET_TABLE names them (PSX.EXE is the executable)."""
    where = {p.split('/')[-1]: v for p, v in pl.lba.items()}
    where['PSX.EXE'] = where['SLUS_010.32']
    return where


FILE_DATE = '20261011000000'


def xml_add(xml_text, parts):
    """The mkpsxiso XML with the file parts[-1] in the directory parts[:-1] (made where missing). A file in the root
    goes before MMM.DAT (the 27 MB of zeros stay last); in a directory, at its end."""
    lines = xml_text.split('\n')
    start = next(i for i, l in enumerate(lines) if l.lstrip().startswith('<directory_tree'))
    end = next(i for i, l in enumerate(lines) if l.lstrip().startswith('</directory_tree>'))
    indent = 12
    for d in parts[:-1]:
        pad = ' ' * indent
        at = next((i for i in range(start + 1, end) if lines[i].startswith(pad + f'<dir name="{d}"')), None)
        if at is None:                                   # a new directory, at the end of its parent (root: before MMM.DAT)
            where = end if indent > 12 else next(i for i in range(start + 1, end)
                                                  if lines[i].startswith(pad + '<file name="MMM.DAT"'))
            lines[where:where] = [pad + f'<dir name="{d}" date="{FILE_DATE}">', pad + '</dir>']
            at = where; end = where + 1
        else:
            end = next(i for i in range(at + 1, len(lines)) if lines[i] == pad + '</dir>')
        start = at; indent += 4
    pad = ' ' * indent
    entry = pad + f'<file name="{parts[-1]}" type="data" date="{FILE_DATE}"/>'
    if len(parts) == 1:
        end = next(i for i in range(start + 1, end) if lines[i].startswith(pad + '<file name="MMM.DAT"'))
    lines.insert(end, entry)
    return '\n'.join(lines)


def seek_order(xml_text):
    """Reorders the children of <directory_tree> (mkpsxiso lays files out in the order of the XML)."""
    head, body = xml_text.split('<directory_tree', 1)
    tree, tail = body.split('</directory_tree>', 1)
    opening, inner = tree.split('>', 1)
    # top-level entries: a one-line <file/>, <dummy/>, or a <dir> ... </dir> block at 12 spaces of indentation
    ent = re.findall(r'^ {12}<(?:file|dummy)[^\n]*/>\n|^ {12}<dir .*?^ {12}</dir>\n', inner, re.M | re.S)
    assert ''.join(ent) == inner.lstrip('\n') or ''.join(ent).strip() == inner.strip(), 'unparsed top-level entries'
    def key(e):
        n = re.search(r'name="([^"]+)"', e).group(1) if 'name=' in e else ''
        if e.lstrip().startswith('<dummy'): return 9
        if n in ('SYSTEM.CNF', 'CARD'): return 0
        if n == 'MAP': return 2
        if n == 'MOVIE': return 3
        if n == 'MMM.DAT': return 4
        return 1                                           # CHDAT DOOR ETC* SCN SOUND STDDAT *_REL.BIN SLUS_010.32
    order = sorted(ent, key=key)                           # stable: keeps the original order inside each group
    return head + '<directory_tree' + opening + '>\n' + ''.join(order) + '        </directory_tree>' + tail


def mkiso(xml, out):
    r = subprocess.run([MKPSXISO, '-y', '-o', out, '-c', out[:-4] + '.cue', xml], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)


def iso_files(img_path):
    img = isolist.Img(img_path); pvd = img.data(16)
    root = pvd[156:190]; ext, = struct.unpack_from('<I', root, 2); ln, = struct.unpack_from('<I', root, 10)
    out = []; isolist.walk(img, ext, ln, '', out); return out


def file_table_entries(exe, t, base=0x80090000):
    """FILE_OFFSET_TABLE's entries in the executable image `exe` (table at file offset t): tools/isowriter.py."""
    return isowriter.file_table_entries(exe, t, base)


def file_table_offset(map_path):
    """FILE_OFFSET_TABLE's offset in the executable file, from its linker map."""
    for line in open(map_path):
        m = re.match(r'\s+(0x[0-9a-f]+)\s+FILE_OFFSET_TABLE\s*$', line)
        if m: return int(m.group(1), 16) - 0x80090000      # 0x800 PS-X EXE header + text at 0x80090800
    sys.exit(f'{map_path}: no FILE_OFFSET_TABLE')


def report_table(result, added=()):
    n, changed, missing, names = result
    lost = [x for x in added if x not in names]
    if lost:
        sys.exit(f'the executable has no FILE_OFFSET_TABLE entry for {", ".join(lost)}: the game would not find '
                 f'{"them" if len(lost) > 1 else "it"}. Build it with NEW_FILES="{" ".join(lost)}" (patch 0147; '
                 'tools/build-full.sh does it from the content, tools/newfiles.py)')
    # modFontFile falls back to the language's screen file when the optional
    # original-font alias has sector zero. Packed tables otherwise show only its key.
    optional = 'SCRNORIG.DAT'
    keys = {optional, f'@{isowriter.filename_hash(optional) & 0xFFFFFF:08X}',
            f'@{isowriter.filename_hash(optional):08X}'}
    absent_optional = [name for name in missing if name in keys]
    missing = [name for name in missing if name not in keys]
    print(f'FILE_OFFSET_TABLE: {n} entries, {changed} updated' + (f', no file on the disc: {missing}' if missing else ''))
    if absent_optional:
        print('optional SCRNORIG.DAT font alias absent: modFontFile uses the language screen file')


def patch_file_table(exe_path, map_path, img_path, added=()):
    """Rewrites FILE_OFFSET_TABLE {i32 sector, i32 size, char *name} from the real disc. Every added file must have an
    entry (a new name comes from the executable's NEW_FILES, patch 0147: tools/newfiles.py, tools/build-full.sh)."""
    files = iso_files(img_path)
    where = {r['path'].split('/')[-1]: (r['lba'], r['size']) for r in files}
    where['PSX.EXE'] = where['SLUS_010.32']
    exe = bytearray(open(exe_path, 'rb').read())
    result = isowriter.rewrite_file_table(exe, file_table_offset(map_path), where)
    report_table(result, added)
    open(exe_path, 'wb').write(exe)
    return {r['path'].split('/')[-1]: r['lba'] for r in files}


if __name__ == '__main__':
    main()
