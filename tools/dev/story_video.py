#!/usr/bin/env python3
"""Split-screen videos of a DWS story: the game on the left, the DWS source on the right with the line that is
running highlighted, and a small watch panel of the story's state.

  story_video.py capture DIR [--fps 20] [--exe-map ELF.map] [--watch NAME=ADDR:LEN[:fmt] ...]
        grabs the emulator's screen (tools/dev/emulator.py, EMU_PORT) and, at the same moment, the interpreter's state
        (SCRIPT_POINTER, ACTIVE_SCRIPT, ACTIVE_MAP_SCRIPT, MAPHEAD_SCRIPT_PTR, IS_SCRIPT_PAUSED, ACTIVE_INSTRUCTION) and the
        watched RAM; DIR/NNNNNN.png + DIR/frames.jsonl. Runs until DIR/STOP exists. A driver (any program that presses
        buttons) runs beside it and may append markers to DIR/markers.jsonl: {"t": time, "title": "..."} shows a caption,
        {"t": time, "speed": 4} plays what follows faster (until the next speed marker).
  story_video.py render DIR --srcmap DG.SCN.srcmap.json --out OUT.mp4 [--fps 30] [--watch-spec FILE.json] [--game-only OUT2.mp4]
        renders every captured frame as one 1920x1080 picture (the game at the top left, x3, the caption and the watch panel
        under it, the source on the right) and writes the video (ffmpeg, H.264, crf 28). The watch spec (JSON) names the
        watched values ("watch": [{"name", "label", "bit" or "mask", "signed", "values"}]), screen names ("screens") and, per screen, the
        source line to show while MAPHEAD sets the screen up ("setup": {"218": "file.dws:LINE"}: its presence rule).

The source map comes from `tools/dws.py compile --srcmap`: for each script, the offset of the first instruction of every
statement and its file:line (and "-" where an event's code ends). The line shown is the last statement at or before the
instruction the interpreter is on; while the tamer has control (IS_SCRIPT_PAUSED = 1) or the script is the original game's,
the panel says so. Times are host times; the game runs in real time during the capture.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse, bisect, json, os, re, struct, subprocess, sys, time, urllib.parse, urllib.request

ROOT = _DEV_ROOT
PORT = int(os.environ.get('EMU_PORT', '38090'))
BASE = f'http://127.0.0.1:{PORT}'
FFMPEG = os.path.expanduser('~/.local/bin/ffmpeg')
DEFAULT_MAP = os.path.join(ROOT, 'build/full/exe/SLUS_010.32.elf.map')
STATE_SYMS = ['IS_SCRIPT_PAUSED', 'ACTIVE_INSTRUCTION', 'SCRIPT_POINTER', 'ACTIVE_SCRIPT', 'ACTIVE_MAP_SCRIPT', 'MAPHEAD_SCRIPT_PTR',
              'CURRENT_SCREEN']


def api(path, data=None, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(BASE + path, data=data), timeout=timeout).read()


def lua(code):
    f = os.path.join(ROOT, f'build/dwsvideo-{PORT}.lua'); open(f, 'w').write(code)
    return api('/api/v1/lua/eval?file=' + urllib.parse.quote(f)).decode()


def symbols(map_path):
    text = open(map_path, encoding='utf-8', errors='replace').read()
    out = {}
    for name in STATE_SYMS:
        m = re.search(r'^\s+(0x[0-9a-f]+)\s+%s$' % name, text, re.M)
        if not m: sys.exit(f'{map_path}: no symbol {name}')
        out[name] = int(m.group(1), 16)
    return out


# ------------------------------------------------------------------ capture
def capture(a):
    os.makedirs(a.dir, exist_ok=True)
    syms = symbols(a.exe_map)
    lo = min(v for k, v in syms.items() if k != 'CURRENT_SCREEN'); hi = max(v for k, v in syms.items() if k != 'CURRENT_SCREEN') + 4
    ranges = [('state', lo, hi - lo), ('screen', syms['CURRENT_SCREEN'], 1)]
    for w in a.watch:
        name, spec = w.split('=', 1); ad, ln = spec.split(':')[:2]
        ranges.append((name, int(ad, 0), int(ln, 0)))
    lua('DV = DV or {}\nDV.r = {' + ','.join(f'{{{ad & 0x1FFFFF},{n}}}' for _, ad, n in ranges) + '}\n'
        'DV.rd = function() local m = PCSX.getMemPtr(); local o = {}\n'
        '  for _, r in ipairs(DV.r) do for i = r[1], r[1] + r[2] - 1 do o[#o + 1] = string.format("%02x", m[i]) end end\n'
        '  return table.concat(o) end\nreturn 1')
    meta = {'syms': syms, 'ranges': [(n, ad, ln) for n, ad, ln in ranges]}
    json.dump(meta, open(os.path.join(a.dir, 'meta.json'), 'w'), indent=1)
    log = open(os.path.join(a.dir, 'frames.jsonl'), 'a')
    period = 1.0 / a.fps; i = len(open(os.path.join(a.dir, 'frames.jsonl')).read().splitlines())
    stop = os.path.join(a.dir, 'STOP')
    print(f'capturing into {a.dir} (touch {stop} to end)', flush=True)
    while not os.path.exists(stop):
        t = time.time()
        ram = lua('return DV.rd()')
        png = api('/api/v1/screen/still')
        open(os.path.join(a.dir, f'{i:06d}.png'), 'wb').write(png)
        log.write(json.dumps({'i': i, 't': t, 'ram': ram}) + '\n'); log.flush()
        i += 1
        time.sleep(max(0.0, period - (time.time() - t)))
    print(f'{i} frames', flush=True)


# ------------------------------------------------------------------ render
KEYWORDS = set('''script new for screen empty on talk enter step use replace before if else choice say return place city presence npc
when flag var persistent session enum pub import const battle give give_bits take recruit walk run await remove sound warp face
cutscene loop while repeat break continue and or not text item species won lost fled cancel prosperity group alias fn sub let
narrator tamer partner self true false'''.split())
COL = {'bg': (24, 26, 33), 'fg': (210, 214, 222), 'kw': (198, 146, 255), 'str': (152, 214, 120), 'num': (247, 166, 92),
       'com': (110, 118, 135), 'hl': (88, 74, 22), 'hlbar': (255, 214, 64), 'ran': (40, 48, 66), 'lineno': (95, 102, 120),
       'head': (120, 200, 255), 'panel': (32, 35, 45), 'watch': (255, 214, 64), 'dim': (150, 156, 170)}
TOKEN = re.compile(r'(//.*$|#.*$)|("(?:[^"\\]|\\.)*")|(\b\d+\b)|([A-Za-z_][\w.]*)|(\s+)|(.)')


def parse_state(meta, hexs):
    b = bytes.fromhex(hexs); out = {}; o = 0
    for name, ad, ln in meta['ranges']:
        out[name] = b[o:o + ln]; o += ln
    s = meta['syms']; st = out['state']; lo = min(v for k, v in s.items() if k != 'CURRENT_SCREEN')
    g = lambda k, n: int.from_bytes(st[s[k] - lo:s[k] - lo + n], 'little')
    sp, act, mh = g('SCRIPT_POINTER', 4), g('ACTIVE_SCRIPT', 4), g('MAPHEAD_SCRIPT_PTR', 4)
    return dict(paused=g('IS_SCRIPT_PAUSED', 1), op=g('ACTIVE_INSTRUCTION', 1), ip=(sp - 1 - act) & 0xFFFFFFFF,
                script='maphead' if act == mh else g('ACTIVE_MAP_SCRIPT', 2), screen=out['screen'][0], raw=out)


class SrcMap:
    def __init__(self, path):
        self.m = {}
        for k, v in json.load(open(path)).items():
            v = sorted(v, key=lambda e: e[0]); self.m[k] = ([o for o, _ in v], [w for _, w in v])   # stable: same order at one offset

    def at(self, script, ip):
        e = self.m.get(str(script))
        if not e: return None
        k = bisect.bisect_right(e[0], ip) - 1
        if k < 0 or e[1][k] == '-': return None
        f, ln = e[1][k].rsplit(':', 1)
        return f, int(ln)

    def between(self, script, ip0, ip1):
        """statements whose first instruction lies in (ip0, ip1]: what ran since the last frame (same script, forward)"""
        e = self.m.get(str(script))
        if not e or ip1 <= ip0: return []
        a, b = bisect.bisect_right(e[0], ip0), bisect.bisect_right(e[0], ip1)
        return [tuple(w.rsplit(':', 1)) for w in e[1][a:b] if w != '-']


def statement_end(lines, ln, py=False):
    """The last line of the statement that starts on line `ln` (a call written over several lines)."""
    end = ln
    if py:                                      # Python: until the brackets opened on the line are closed
        depth = 0
        while end <= len(lines) and end - ln < 8:
            code = re.sub(r'#.*$', '', re.sub(r'"(?:[^"\\]|\\.)*"', '""', lines[end - 1]))
            depth += code.count('(') + code.count('[') - code.count(')') - code.count(']')
            if depth <= 0: return end
            end += 1
        return min(end, len(lines))
    while end < len(lines) and end - ln < 8:
        code = re.sub(r'//.*$', '', re.sub(r'"(?:[^"\\]|\\.)*"', '""', lines[end - 1])).rstrip()
        if not code or code.endswith((';', '{', '}')): break
        end += 1
    return end


def enclosing_event(lines, ln):
    """`on talk(gekomon)`, `on enter`...: the event header above line `ln`, and the script header above that."""
    ev = sc = None
    for k in range(ln - 1, -1, -1):
        t = lines[k].strip()
        if t.startswith('def ') and lines[k][:1] == 'd':          # Python: the handler and its decorator
            deco = lines[k - 1].strip() if k and lines[k - 1].startswith('@') else ''
            return ' · '.join(x for x in (deco, re.sub(r':\s*(#.*)?$', '', t)) if x)
        if ev is None and re.match(r'on\s+\w+', t): ev = re.sub(r'\s*(replace|before)?\s*\{.*$', '', t)
        if re.match(r'script\b', t): sc = re.sub(r'\s*\{.*$', '', t); break
    return ' · '.join(x for x in (sc, ev) if x)


def render(a):
    from tools.image import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(a.dir, 'meta.json')))
    frames = [json.loads(l) for l in open(os.path.join(a.dir, 'frames.jsonl'))]
    mpath = os.path.join(a.dir, 'markers.jsonl')
    marks = [json.loads(l) for l in open(mpath)] if os.path.exists(mpath) else []
    spec = json.load(open(a.watch_spec)) if a.watch_spec else {}
    smap = SrcMap(a.srcmap)
    F = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono'
    font, bold = ImageFont.truetype(F + '.ttf', a.font), ImageFont.truetype(F + '-Bold.ttf', a.font)
    small, smallb = ImageFont.truetype(F + '.ttf', a.font - 4), ImageFont.truetype(F + '-Bold.ttf', a.font - 4)
    capf = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', a.font + 2)
    W, H = a.width, a.height                       # whole frame; the game takes the left half at 4:3, the code the right half
    GW = W // 2; GH = GW * 3 // 4; CW = W - GW
    files = {}
    def src(f):
        if f not in files: files[f] = open(os.path.join(ROOT, f), encoding='utf-8').read().splitlines()
        return files[f]
    lh = a.font + 8; slh = a.font + 2
    head_h = lh + slh + 14
    code_rows = (H - head_h - 10) // lh
    out_dir = os.path.join(a.dir, 'frames-' + os.path.splitext(os.path.basename(a.out))[0]); os.makedirs(out_dir, exist_ok=True)
    mh_secs = []                                   # MAPHEAD's section table: (offset, section id), to tell which screen it sets up
    if a.maphead:
        b = open(a.maphead, 'rb').read(); o = 2
        while struct.unpack_from('<H', b, o)[0] != 0xFFFF:
            sid, off = struct.unpack_from('<HH', b, o); mh_secs.append((off, sid)); o += 4
        mh_secs.sort()
    def mh_section(ip):
        k = bisect.bisect_right([x for x, _ in mh_secs], ip) - 1
        return mh_secs[k][1] if k >= 0 else None
    setup = {}                                     # screen -> (file, first line, last line)
    for k, v in spec.get('setup', {}).items():
        f, r = v.rsplit(':', 1); lo, _, hi = r.partition('-'); setup[k] = (f, int(lo), int(hi or lo))
    last = None; prev = None; caption = ''
    def speed_at(t):
        sp = 1.0
        for m in marks:
            if m['t'] <= t and 'speed' in m: sp = m['speed']
        return sp
    vt = 0.0; times = []
    for k, fr in enumerate(frames):
        if k: vt += (fr['t'] - frames[k - 1]['t']) / speed_at(frames[k - 1]['t'])
        times.append(vt)
    seq = []; n_out = int(times[-1] * a.fps) + 1; j = 0
    for n in range(n_out):
        while j + 1 < len(times) and times[j + 1] <= n / a.fps: j += 1
        seq.append(j)
    rendered = {}
    for k, fr in enumerate(frames):
        st = parse_state(meta, fr['ram'])
        here = None if st['paused'] == 1 else smap.at(st['script'], st['ip'])
        mode = 'run' if here else 'idle'
        mh_screen = (mh_section(st['ip']) if mh_secs else st['screen']) if st['script'] == 'maphead' else None
        if not here and st['paused'] != 1 and str(mh_screen) in setup:
            here = setup[str(mh_screen)][:2]; mode = 'setup'
        ran = set()
        if prev and mode == 'run' and prev['script'] == st['script'] and prev['paused'] != 1:
            ran = {(f, int(l)) for f, l in smap.between(st['script'], prev['ip'], st['ip'])}
        prev = st
        if here: last = here
        for m in marks:
            if 'title' in m and m['t'] <= fr['t']: caption = m['title']
        img = Image.new('RGB', (W, H), COL['bg']); d = ImageDraw.Draw(img)
        game = Image.open(os.path.join(a.dir, f'{fr["i"]:06d}.png')).convert('RGB').resize((GW, GH), Image.NEAREST)
        img.paste(game, (0, 0))
        # ---- under the game: the caption and the watch panel
        y = GH + 10
        d.rectangle([0, GH, GW, H], fill=COL['panel'])
        for line in wrap_text(d, caption, capf, GW - 28)[:2]:
            d.text((14, y), line, font=capf, fill=COL['watch']); y += a.font + 8
        y += 4
        items = []
        for w in spec.get('watch', []):
            v = int.from_bytes(st['raw'][w['name']], 'little', signed=w.get('signed', False))
            if 'bit' in w: v = (v >> w['bit']) & 1
            if 'mask' in w: v &= w['mask']             # several bits: a quest's stage (Horn_b0 + 2 Horn_b1)
            items.append((w['label'], w.get('values', {}).get(str(v), str(v))))
        items.append(('screen', f'{st["screen"]} {spec.get("screens", {}).get(str(st["screen"]), "")}'.strip()))
        cols = 2; cw = (GW - 28) // cols
        for q, (lab, val) in enumerate(items):
            x = 14 + (q % cols) * cw; yy = y + (q // cols) * (lh - 2)
            d.text((x, yy), lab + ' ', font=font, fill=COL['dim'])
            d.text((x + d.textlength(lab + ' ', font=font), yy), val, font=bold, fill=COL['fg'])
        # ---- the code
        X0 = GW
        d.rectangle([X0, 0, W, head_h], fill=COL['panel'])
        show = here or last
        if mode == 'run': status = f'running  script {st["script"]}  offset {st["ip"]:#06x}'
        elif mode == 'setup': status = f'screen setup (MAPHEAD section {mh_screen}): the presence rule'
        elif st['paused'] == 1: status = 'the player has control'
        elif st['script'] == 'maphead': status = 'screen setup (MAPHEAD)'
        else: status = f'the original game\'s script {st["script"]}'
        if show:
            lines = src(show[0]); cur = show[1]
            end = setup[str(mh_screen)][2] if mode == 'setup' else statement_end(lines, cur, show[0].endswith('.py'))
            htxt = os.path.basename(show[0]) + '   ' + enclosing_event(lines, cur)
            hf = bold if d.textlength(htxt, font=bold) <= CW - 28 else smallb      # a long handler header: the smaller font
            while d.textlength(htxt, font=hf) > CW - 28: htxt = htxt[:-2] + '…'
            d.text((X0 + 14, 6), htxt, font=hf, fill=COL['head'])
            d.text((X0 + 14, 6 + lh), status, font=small, fill=COL['watch'] if mode != 'idle' else COL['dim'])
            cwid = d.textlength('M', font=font)
            x0 = X0 + 14 + 4.5 * cwid
            ncols = max(20, int((W - 6 - x0) / cwid))
            ind = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
            def rows_of(text_):
                """the line as visual rows of (char, colour) lists: long lines wrap at a space, the continuation indented by 4"""
                runs = []
                for m in TOKEN.finditer(text_[ind:].rstrip()):
                    com, s_, num, word, ws, other = m.groups(); t = m.group(0)
                    c = COL['com'] if com else COL['str'] if s_ else COL['num'] if num else \
                        COL['kw'] if word and word in KEYWORDS else COL['fg']
                    runs += [(ch, c) for ch in t]
                hang = len(text_[ind:]) - len(text_[ind:].lstrip()) + 4
                out = []
                while len(runs) > ncols:
                    cut = ncols
                    for q in range(ncols, ncols // 2, -1):
                        if runs[q - 1][0] == ' ' or runs[q][0] == ' ': cut = q; break
                    out.append(runs[:cut]); runs = [(' ', COL['fg'])] * hang + runs[cut:]
                    while len(runs) > hang and runs[hang][0] == ' ': del runs[hang]
                out.append(runs)
                return out
            wr = {}
            def rows(n):
                if n not in wr: wr[n] = rows_of(lines[n - 1])
                return wr[n]
            top = cur; used = len(rows(cur))              # walk up for about a third of the panel, then fill downwards
            while top > 1 and used + len(rows(top - 1)) <= code_rows // 3 + len(rows(cur)): top -= 1; used += len(rows(top))
            last_ln = top - 1; used = 0
            while last_ln < len(lines) and used + len(rows(last_ln + 1)) <= code_rows: last_ln += 1; used += len(rows(last_ln))
            while top > 1 and used + len(rows(top - 1)) <= code_rows: top -= 1; used += len(rows(top))
            r = 0
            for ln in range(top, last_ln + 1):
                active = cur <= ln <= end
                rs = rows(ln); y0 = head_h + 6 + r * lh; y1 = y0 + len(rs) * lh
                if active:
                    d.rectangle([X0, y0 - 3, W, y1 - 5], fill=COL['hl'] if mode != 'idle' else COL['ran'])
                    d.rectangle([X0, y0 - 3, X0 + 7, y1 - 5], fill=COL['hlbar'] if mode != 'idle' else COL['dim'])
                elif (show[0], ln) in ran:
                    d.rectangle([X0, y0 - 3, W, y1 - 5], fill=COL['ran'])
                d.text((X0 + 14, y0 + 2), f'{ln:3d}', font=small, fill=COL['lineno'])
                f_ = bold if active and mode != 'idle' else font
                for q, row in enumerate(rs):
                    x = x0
                    for ch, c in row:
                        if ch != ' ': d.text((x, y0 + q * lh), ch, font=f_, fill=c)
                        x += cwid
                r += len(rs)
        else:
            d.text((X0 + 14, 6), 'DWS source', font=bold, fill=COL['head'])
            d.text((X0 + 14, 6 + lh), status, font=small, fill=COL['dim'])
        p = os.path.join(out_dir, f'{k:06d}.png'); img.save(p, compress_level=1)
        rendered[k] = p
    lst = os.path.join(a.dir, 'seq.txt'); lst2 = os.path.join(a.dir, 'seq-panel.txt')
    with open(lst, 'w') as f, open(lst2, 'w') as g:
        for j in seq:
            gp = os.path.abspath(os.path.join(a.dir, '%06d.png' % frames[j]['i']))
            f.write(f"file '{gp}'\nduration {1 / a.fps:.6f}\n")
            g.write(f"file '{os.path.abspath(rendered[j])}'\nduration {1 / a.fps:.6f}\n")
    enc = ['-c:v', 'libx264', '-preset', 'slow', '-crf', str(a.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst2, '-vf', f'fps={a.fps}', *enc, a.out], check=True)
    print(a.out, f'{os.path.getsize(a.out) / 1e6:.1f} MB, {n_out / a.fps:.0f} s')
    if a.game_only:
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-vf',
                        f'scale=960:720:flags=neighbor,setsar=1,fps={a.fps}', *enc, a.game_only], check=True)
        print(a.game_only, f'{os.path.getsize(a.game_only) / 1e6:.1f} MB')


def wrap_text(d, text, font, width):
    words = text.split(); lines = []; cur = ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture'); c.add_argument('dir'); c.add_argument('--fps', type=float, default=20)
    c.add_argument('--exe-map', default=DEFAULT_MAP); c.add_argument('--watch', action='append', default=[])
    r = sub.add_parser('render'); r.add_argument('dir'); r.add_argument('--srcmap', required=True); r.add_argument('--out', required=True)
    r.add_argument('--fps', type=int, default=30); r.add_argument('--crf', type=int, default=28); r.add_argument('--font', type=int, default=24)
    r.add_argument('--width', type=int, default=1920); r.add_argument('--height', type=int, default=1080)
    r.add_argument('--watch-spec'); r.add_argument('--game-only')
    r.add_argument('--maphead', help='the disc\'s MAPHEAD.SCN: tells which screen a MAPHEAD frame is setting up')
    a = ap.parse_args()
    capture(a) if a.cmd == 'capture' else render(a)


if __name__ == '__main__':
    main()
