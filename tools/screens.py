#!/usr/bin/env python3
"""Screens beyond 255: SCRN.DAT, the records of the screens 255..NUM_SCREENS-1 (patch 0146, include/dw/screen.h).

A screen of the original game (0-254) is a MAP_ENTRIES row in the executable (content/screens/<id>-*.json,
written by tools/balance.py) and a section of MAPHEAD.SCN, both resident. A screen from 255 up is one
2048-byte sector of SCRN.DAT that the executable reads when the screen is named: the same row, the
screen's own toilet, door and caption when the original tables have none for it, the flags of what
the original decides by screen id in code (concave arena, mist, shop, arena), and its MAPHEAD section as a
small script of its own. So a new screen costs no resident RAM, and MAPHEAD.SCN only keeps the sections
of the original screens and the shared ones (1220..).

  screens.py build -o SCRN.DAT --maphead IN.SCN --maphead-out OUT.SCN [--content DIR ...]
        the records of every screen file with an id >= 255 in content/screens and the DIRs. Its MAPHEAD
        section is the one IN.SCN has (the story build writes it: `script new for screen N`, `place`), else
        the one its file describes ("maphead": {"like": N, "script": S}); the sections >= 255 are taken
        out of IN.SCN and OUT.SCN is the rest (what the executable keeps resident)
  screens.py show SCRN.DAT [ID ...]       prints the records
  screens.py section ID --maphead IN.SCN [--content DIR ...]
        prints the assembly text of a new screen's MAPHEAD section (what build would put in its record)

A screen file (tools/dev/playtest/screens/300-test-hollow.json is one; the keys of the original screens' files, plus):

  "doors":   0 = none, 1..24 a row of DOOR_MAPDATA, or the screen's own:
             {"models": [6 ids, -1 = none], "x": [6], "y": [6], "z": [6], "rotation": [6]}
  "toilet":  0 = none, 1..10 a row of TOILET_DATA, or the screen's own {"x1": .., "z1": .., "x2": .., "z2": ..}
  "caption": 0..69 an area name of the executable (MAP_NAME_PTR), or the screen's own text (up to 35 bytes)
  "concave", "mist", "shop", "arena": true for what the original does by screen id (default false)
  "maphead": {"like": N, "script": S}: when the story gives the screen no MAPHEAD section, the section of
             screen N (its music, its spawns) with SET_SCRIPT S, <this screen>; without "like" the section
             is SET_SCRIPT S, <id>; SET_PSTAT p245, 0; END_SECTION
"""
import argparse, glob, json, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dws import bytecode as bytecode  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREEN_DIR = os.path.join(ROOT, 'content', 'screens')
NUM_ORIGINAL_SCREENS = 255
NUM_SCREENS = 1024                   # include/dw/ids.h (a build constant)
RECORD_SIZE = 0x800
SCRIPT_OFFSET = 0x80
SCRIPT_MAX = RECORD_SIZE - SCRIPT_OFFSET
CAPTION_MAX = 36
OWN = -1
FLAGS = {'concave': 0x1, 'mist': 0x2, 'shop': 0x4, 'arena': 0x8}
KEYS = {'id', 'file', 'fileBytes', 'tims8', 'tims4', 'sound_bank', 'day_night', 'reads_digimon', 'flag20', 'doors', 'toilet',
        'caption', 'maphead'} | set(FLAGS)


class ScreenError(Exception):
    pass


def is_new(i):
    return NUM_ORIGINAL_SCREENS <= i < NUM_SCREENS


# ------------------------------------------------------------------------------------------------ screen files
def load(dirs=()):
    """{id: screen file} of the screens >= 255 in content/screens and dirs (a later dir wins for the same id)."""
    out = {}
    for d in [SCREEN_DIR] + list(dirs):
        for p in sorted(glob.glob(os.path.join(d, '*.json'))):
            m = re.match(r'^(\d+)-', os.path.basename(p))
            if not m or not is_new(int(m.group(1))): continue
            x = json.load(open(p)); x['_path'] = p
            if x.get('id') != int(m.group(1)): raise ScreenError(f'{p}: the file name starts with its id ({x.get("id")})')
            bad = sorted(k for k in x if not k.startswith('_') and k not in KEYS)
            if bad: raise ScreenError(f'{p}: unknown key {", ".join(bad)} (keys: {", ".join(sorted(KEYS))})')
            out[x['id']] = x
    return out


def head(x, script):
    """The 0x80 bytes before the script (screen.h ScreenRecordHead)."""
    p = x['_path']
    name = bytes(x['fileBytes']) if x.get('fileBytes') else x['file'].encode('latin-1')
    if len(name) > 10 or (len(name) == 10 and not x.get('fileBytes')): raise ScreenError(f'{p}: "file" has at most 9 characters')
    fl = (x.get('sound_bank', 0) & 0x1F) | (0x20 if x.get('flag20') else 0) | (0 if x.get('day_night', True) else 0x40) | \
         (0x80 if x.get('reads_digimon') else 0)
    toilet = struct.pack('<4h', 0, 0, 0, 0); door = bytes(54); caption = b''
    t = x.get('toilet', 0)
    if isinstance(t, dict): toilet = struct.pack('<4h', t['x1'], t['z1'], t['x2'], t['z2']); t = OWN
    elif not 0 <= t <= 10: raise ScreenError(f'{p}: "toilet" is 0 (none), 1..10 (TOILET_DATA) or {{"x1", "z1", "x2", "z2"}}')
    dr = x.get('doors', 0)
    if isinstance(dr, dict):
        v = [dr[k] for k in ('models', 'x', 'y', 'z', 'rotation')]
        if any(len(a) != 6 for a in v): raise ScreenError(f'{p}: each list of "doors" has 6 values (one per door, -1 = none)')
        door = struct.pack('<6b24h', *v[0], *v[1], *v[2], *v[3], *v[4]); dr = OWN
    elif not 0 <= dr <= 24: raise ScreenError(f'{p}: "doors" is 0 (none), 1..24 (DOOR_MAPDATA) or the screen\'s own doors')
    c = x.get('caption', 0)
    if isinstance(c, str):
        caption = c.encode('latin-1')
        if len(caption) >= CAPTION_MAX: raise ScreenError(f'{p}: "caption" has at most {CAPTION_MAX - 1} bytes')
        c = OWN
    elif not 0 <= c < 70: raise ScreenError(f'{p}: "caption" is 0..69 (an area name of the executable) or a text')
    flags = sum(v for k, v in FLAGS.items() if x.get(k))
    entry = name.ljust(10, b'\0') + struct.pack('<bbBbbb', x.get('tims8', 0), x.get('tims4', 0), fl, dr, t, c)
    h = b'SCR1' + struct.pack('<hH', x['id'], len(script)) + entry + struct.pack('<I', flags) + toilet + door + bytes(2) + \
        caption.ljust(CAPTION_MAX, b'\0')
    assert len(h) == SCRIPT_OFFSET, len(h)
    return h


# ------------------------------------------------------------------------------------------------ MAPHEAD text
SECTION_RE = re.compile(r'^\.section\s+(\d+)\s+(\S+)\s*$')
LABEL_RE = re.compile(r'^([A-Za-z_]\w*):')


def code_part(line):
    """The line without its comment (a ';' outside quotes)."""
    q = False
    for i, ch in enumerate(line):
        if ch == '"': q = not q
        elif ch == ';' and not q: return line[:i]
    return line


def dis_text(maphead):
    txt, end, _ = bytecode.disassemble_script(maphead, f'MAPHEAD.SCN ({len(maphead)} bytes)')
    if end != len(maphead): raise ScreenError(f'MAPHEAD.SCN: {len(maphead) - end} bytes after the end of its code')
    return txt


def chunks(text):
    """(header lines, [(label or None, lines)]): the text cut at every label of a section start."""
    lines = text.split('\n')
    starts = {m.group(2): int(m.group(1)) for m in map(SECTION_RE.match, lines) if m}
    hdr = [l for l in lines if SECTION_RE.match(l)]
    body = [l for l in lines if not SECTION_RE.match(l)]
    out = [(None, [])]
    for l in body:
        m = LABEL_RE.match(l)
        if m and m.group(1) in starts: out.append((m.group(1), []))
        out[-1][1].append(l)
    return starts, hdr, out


def refs(lines, names):
    found = set()
    for l in lines:
        if LABEL_RE.match(l): continue
        found |= {w for w in re.findall(r'[A-Za-z_]\w*', code_part(l)) if w in names}
    return found


def split(text, ids):
    """MAPHEAD text -> (the text without the sections `ids`, {id: text of a one-section script})."""
    starts, hdr, parts = chunks(text)
    by_id = {}
    for name, sec in starts.items():
        by_id.setdefault(sec, name)                       # a repeated id: getScriptSection takes the first
    take = {i: by_id[i] for i in ids if i in by_id}
    defined = {}
    for k, (name, lines) in enumerate(parts):
        for l in lines:
            m = LABEL_RE.match(l)
            if m: defined[m.group(1)] = k
    out = {}; drop = set()
    for i, name in take.items():
        k = next(k for k, (n, _) in enumerate(parts) if n == name)
        mine = {n for n, kk in defined.items() if kk == k}
        others = [n for n, s in starts.items() if n in mine and s != i]
        if others: raise ScreenError(f'MAPHEAD section {i} shares its code with {others}')
        outside = refs(parts[k][1], set(defined)) - mine
        if outside: raise ScreenError(f'MAPHEAD section {i} jumps into code outside it ({", ".join(sorted(outside))})')
        into = set()
        for kk, (_, lines) in enumerate(parts):
            if kk != k: into |= refs(lines, mine)
        if into: raise ScreenError(f'MAPHEAD code outside section {i} jumps into it ({", ".join(sorted(into))})')
        out[i] = '\n'.join([f'; MAPHEAD section {i} (screen {i}): the script of its SCRN.DAT record', f'.section {i} {name}', ''] +
                           parts[k][1]) + '\n'
        drop.add(k)
    names = {n for i, n in take.items()}
    hdr = [l for l in hdr if SECTION_RE.match(l).group(2) not in names]
    rest = [l for k, (_, lines) in enumerate(parts) if k not in drop for l in lines]
    first = next((k for k, l in enumerate(rest) if LABEL_RE.match(l)), len(rest))
    return '\n'.join(rest[:first] + hdr + [''] + rest[first:]), out


def section_of(text, sec):
    """The lines of MAPHEAD section `sec` (its label first) in a disassembly, or None."""
    starts, _, parts = chunks(text)
    name = next((n for n, s in starts.items() if s == sec), None)
    return next((lines for n, lines in parts if n == name), None) if name else None


def synth_section(i, x, text):
    """The assembly of a new screen's MAPHEAD section from its file ("maphead": {"like", "script"}), its label
    sec<i> and its own labels renamed so that it can join the text it was copied from."""
    mh = x.get('maphead') or {}
    like = mh.get('like')
    if like is None:
        if 'script' not in mh: raise ScreenError(f'{x["_path"]}: screen {i} has no MAPHEAD section; give it "maphead": {{"like": N}} or '
                                                 '{"script": S} (or a `script new for screen` in the story)')
        return [f'sec{i}:', f'    SET_SCRIPT {mh["script"]}, {i}', '    SET_PSTAT p245, 0', '    END_SECTION', '']
    lines = section_of(text, like)
    if lines is None: raise ScreenError(f'{x["_path"]}: "like": {like}: MAPHEAD has no section {like}')
    own = [LABEL_RE.match(l).group(1) for l in lines if LABEL_RE.match(l)]
    ren = {n: f'sec{i}' if k == 0 else f'{n}_s{i}' for k, n in enumerate(own)}
    out = []; done = False
    for l in lines:
        c = code_part(l)
        l2 = re.sub(r'[A-Za-z_]\w*', lambda m: ren.get(m.group(0), m.group(0)), c).rstrip()
        m = re.match(r'^(\s*SET_SCRIPT\s+)(\d+)\s*,\s*(\d+)', l2)
        if m and not done:
            l2 = f'{m.group(1)}{mh.get("script", int(m.group(2)))}, {i}'; done = True
        out.append(l2)
    if not done: raise ScreenError(f'{x["_path"]}: section {like} has no SET_SCRIPT')
    return out + ['']


def add_section(text, i, lines):
    """MAPHEAD text with section i appended (the backend's `script new for screen i` of a new screen)."""
    lines_all = text.rstrip('\n').split('\n')
    last = max(k for k, l in enumerate(lines_all) if SECTION_RE.match(l))
    return '\n'.join(lines_all[:last + 1] + [f'.section {i} sec{i}'] + lines_all[last + 1:] + [''] + lines) + '\n'


def asm_opts(pack_ascii=None):
    """The assembler's options of MAPHEAD text: one-byte letters (patch 0145) as the story packed them (pack_ascii; None: the
    environment's SCNASM_PACK_ASCII, as the command line)."""
    if pack_ascii is None: pack_ascii = os.environ.get('SCNASM_PACK_ASCII') == '1'
    return {'pack_ascii': pack_ascii, 'quiet': True}


# ------------------------------------------------------------------------------------------------ SCRN.DAT
def encode_record(i, x, text, opts):
    code, _ = bytecode.assemble_script(text, f'screen_{i}.scn.txt', opts)
    if len(code) > SCRIPT_MAX:
        raise ScreenError(f'screen {i}: its MAPHEAD section takes {len(code)} bytes; a record holds {SCRIPT_MAX}')
    return head(x, code) + code, len(code)


def build(recs, maphead, maphead_max=0x8000, log=print, pack_ascii=None, cache_records=False):
    """-> (SCRN.DAT bytes, the MAPHEAD.SCN that stays resident, {id: script size}). pack_ascii: asm_opts'."""
    opts = asm_opts(pack_ascii)
    text = dis_text(maphead)
    present = {i for i in recs if section_of(text, i) is not None}
    rest, secs = split(text, sorted(present))
    for i, x in recs.items():
        if i not in secs:
            secs[i] = '\n'.join([f'; screen {i}: the MAPHEAD section of its file ({x["_path"]})', f'.section {i} sec{i}', ''] +
                                synth_section(i, x, text)) + '\n'
    again, _ = bytecode.assemble_script(text, 'maphead.scn.txt', opts)
    if again != maphead:
        # the text does not assemble back to the same bytes (another text packing than the story's): keep MAPHEAD as it is;
        # the records still win (getMapHeadScript), the new screens' sections just stay resident too
        log('warning: MAPHEAD.SCN does not assemble back byte for byte: its sections >= 255 are left in it')
        mh = maphead
    else:
        mh, _ = bytecode.assemble_script(rest, 'maphead.scn.txt', opts)
    if len(mh) > maphead_max:
        raise ScreenError(f'MAPHEAD.SCN is {len(mh)} bytes without the new screens; the executable holds {maphead_max}')
    top = max(recs) if recs else NUM_ORIGINAL_SCREENS - 1
    out = bytearray(RECORD_SIZE * (1 + top - NUM_ORIGINAL_SCREENS + 1))
    out[0:10] = b'SCRN' + struct.pack('<HHH', 1, NUM_ORIGINAL_SCREENS, top - NUM_ORIGINAL_SCREENS + 1)
    sizes = {}
    codec = bytecode.source_digest() if cache_records else None
    for i, x in sorted(recs.items()):
        if cache_records:
            from tools.derive.cache import screen_piece
            rec, size = screen_piece(encode_record, (i, x, secs[i], opts), os.path.join(ROOT, 'build/.cache-screen-pieces'), codec)
        else:
            rec, size = encode_record(i, x, secs[i], opts)
        o = RECORD_SIZE * (1 + i - NUM_ORIGINAL_SCREENS)
        out[o:o + len(rec)] = rec; sizes[i] = size
    return bytes(out), mh, sizes, secs


def build_files(maphead, maphead_out, out, content=(), maphead_max=0x8000, pack_ascii=None, log=print, cache_records=False):
    """`screens.py build`: SCRN.DAT at `out` and the resident MAPHEAD at `maphead_out`, from the MAPHEAD.SCN file `maphead`
    and the screen files of content/screens and the folders `content`."""
    recs = load(content)
    dat, mh, sizes, _ = build(recs, open(maphead, 'rb').read(), maphead_max, log=log, pack_ascii=pack_ascii,
                             cache_records=cache_records)
    open(out, 'wb').write(dat); open(maphead_out, 'wb').write(mh)
    for i, n in sorted(sizes.items()):
        log(f'screen {i}: {recs[i]["file"] or "-"}, MAPHEAD section {n} bytes ({os.path.relpath(recs[i]["_path"], ROOT)})')
    log(f'{out}: {len(sizes)} screens, {len(dat)} bytes; {maphead_out}: {len(mh)} bytes of {maphead_max}')


def records(dat):
    if dat[:4] != b'SCRN': raise ScreenError('not a SCRN.DAT')
    first, count = struct.unpack_from('<HH', dat, 6)
    for k in range(count):
        o = RECORD_SIZE * (1 + k)
        r = dat[o:o + RECORD_SIZE]
        if r[:4] != b'SCR1': continue
        i, size = struct.unpack_from('<hH', r, 4)
        name = r[8:18].rstrip(b'\0').decode('latin-1')
        n8, n4, fl, dr, t, c = struct.unpack_from('<bbBbbb', r, 18)
        flags, = struct.unpack_from('<I', r, 0x18)
        toilet = struct.unpack_from('<4h', r, 0x1C)
        cap = r[0x5C:0x5C + CAPTION_MAX].split(b'\0')[0].decode('latin-1')
        yield dict(id=i, file=name, tims8=n8, tims4=n4, flags=fl, doors=dr, toilet=t, caption=c, caption_text=cap,
                   screen_flags=[k for k, v in FLAGS.items() if flags & v], toilet_xy=toilet, script=bytes(r[SCRIPT_OFFSET:SCRIPT_OFFSET + size]))


def main():
    global NUM_SCREENS
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build'); b.add_argument('-o', required=True); b.add_argument('--maphead', required=True)
    b.add_argument('--maphead-out', required=True); b.add_argument('--content', action='append', default=[])
    b.add_argument('--maphead-max', type=lambda s: int(s, 0), default=0x8000)
    b.add_argument('--num-screens', type=int, default=NUM_SCREENS)
    s = sub.add_parser('show'); s.add_argument('dat'); s.add_argument('ids', nargs='*', type=int)
    c = sub.add_parser('section'); c.add_argument('id', type=int); c.add_argument('--maphead', required=True)
    c.add_argument('--content', action='append', default=[])
    a = ap.parse_args()
    try:
        if a.cmd == 'build':
            NUM_SCREENS = a.num_screens
            build_files(a.maphead, a.maphead_out, a.o, a.content, a.maphead_max)
        elif a.cmd == 'show':
            for r in records(open(a.dat, 'rb').read()):
                if a.ids and r['id'] not in a.ids: continue
                cap = repr(r['caption_text']) if r['caption'] == OWN else f'area {r["caption"]}'
                print(f'screen {r["id"]}: file {r["file"]} tims {r["tims8"]}+{r["tims4"]} flags 0x{r["flags"]:02X} doors {r["doors"]} '
                      f'toilet {r["toilet"]}{" " + str(r["toilet_xy"]) if r["toilet"] == OWN else ""} caption {cap} '
                      f'{" ".join(r["screen_flags"])} section {len(r["script"])} bytes')
        else:
            recs = load(a.content)
            text = dis_text(open(a.maphead, 'rb').read())
            lines = section_of(text, a.id)
            print('\n'.join(lines) if lines is not None else '\n'.join(synth_section(a.id, recs[a.id], text)))
    except (ScreenError, bytecode.BytecodeError) as e:
        sys.exit(f'screens.py: {e}')


if __name__ == '__main__':
    main()
