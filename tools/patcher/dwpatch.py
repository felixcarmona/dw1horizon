#!/usr/bin/env python3
"""Build and apply the everything release from the player's four discs.

The file-based DWP3 format reconstructs program files using binary differences
from the player's regional files and replays derived assets with tools/derive.
Every output file and image is checked against the release's hashes. Raw literals,
extras and mapping data are subject to the publication gate. See docs/patcher.md.

"""
import argparse
import hashlib
import json
import lzma
import os
import queue
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib

FORMAT = 3                      # the current file-based patch format
READS = (3,)
RAW = 2352
DATA = 2048
BLOCK = 32                       # delta: source index granularity (the shortest COPY)

# The USA reference for make-release: SLUS-01032, the redump dump (one track, MODE2/2352).
# Apply accepts the regional discs declared by the release manifest.
# http://redump.org/disc/14957/ (Original and Greatest Hits share this dump).
ORIGINAL = dict(title='Digimon World (USA)', serial='SLUS-01032', boot='SLUS_010.32', size=381771936,
                crc32='e6fdd00e', md5='8520edac0f7f1454f8a008ac5e599c1a',
                sha1='5611645da66183e30d11fb6c11a2784ff47e1fdb', redump='http://redump.org/disc/14957/')
OTHER_VERSIONS = {
    'SLES_029.14': 'Digimon World (Europe)', 'SLPS_017.97': 'Digimon World (Japan)',
    'SLPS_917.12': 'Digimon World (Japan, PlayStation the Best)', 'SLUS_011.93': 'Digimon World 2 (USA)',
    'SLUS_013.28': 'Digimon Digital Card Battle (USA)', 'SLES_039.36': 'Digimon World 2003 (Europe)',
}

class PatchError(Exception):
    pass


# ---------------------------------------------------------------- small helpers
SCREEN = None                    # apply's screen while it runs (Screen): say() and Progress go through it


def say(msg=''):
    if SCREEN is not None:
        SCREEN.log(msg)
    else:
        print(msg, flush=True)


def _tty():
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError, OSError):        # (a stream without a terminal: the browser's)
        return False


class Progress:
    """A part of the work measured in units (bytes hashed, sectors written): its percentage on its own line, or, while
    apply's screen runs, the fraction of the screen's current phase."""
    def __init__(self, what, total):
        self.what, self.total, self.last, self.t0 = what, max(1, total), -1, time.time()

    def __call__(self, done):
        if SCREEN is not None and not SCREEN.verbose:
            SCREEN.part(done / self.total)
            return
        pct = int(done * 100 / self.total)
        if pct != self.last and _tty():                   # (redirected: only the end's line)
            self.last = pct
            sys.stdout.write(f'\r  {self.what}: {pct:3d}%'); sys.stdout.flush()

    def end(self):
        if SCREEN is not None and not SCREEN.verbose:
            SCREEN.log(f'  {self.what}: done ({time.time() - self.t0:.0f} s)')
            return
        sys.stdout.write(f'\r  {self.what}: done ({time.time() - self.t0:.0f} s)\n' if _tty() else
                         f'  {self.what}: done ({time.time() - self.t0:.0f} s)\n'); sys.stdout.flush()


def clock(s):
    s = int(s + 0.5)
    return f'{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'


class Screen:
    """What apply shows: one line updated in place, an overall bar weighted by the measured time of each phase, the
    percentage, the phase in plain words, the time taken and an estimate of the time left:

      [###########.................]  41%  building the Digimon models   1:12 so far, about 1:45 left

    Plain ASCII and a carriage return (the Windows console, cmd and PowerShell, macOS and Linux terminals); when the
    output is not a terminal (redirected to a file, a pipe), one line per phase instead. Everything the patcher would
    have printed goes to the log file (`log`), and with --verbose to the screen as well, without the bar.

    phases: [(key, words, weight in seconds)] in order. start(key) begins a phase (the ones before it count as done),
    part(f) is the fraction of the current phase done (0..1; parts that are not measured advance with the time the phase
    is expected to take, up to 95% of it), done() ends the bar."""
    def __init__(self, phases, log_path, verbose=False, out=None):
        self.out = out or sys.stdout
        self.verbose = verbose
        self.tty = not verbose and hasattr(self.out, 'isatty') and self.out.isatty()
        self.keys = [k for k, _, _ in phases]
        self.words = {k: w for k, w, _ in phases}
        self.weight = {k: max(0.01, float(w)) for k, _, w in phases}
        self.total = sum(self.weight.values())
        self.log_path = log_path
        self.logf = open(log_path, 'w', encoding='utf-8', errors='replace')
        self.t0 = time.time()
        self.cur, self.cur_t0, self.frac, self.measured = None, self.t0, 0.0, False
        self.done_w, self.done_t = 0.0, 0.0           # weight and seconds of the phases finished
        self.finished = set()
        self.shown, self.width_shown, self.closed = None, 0, False
        import threading
        self.lock = threading.Lock()
        self.ticker = None
        if self.tty:
            self.ticker = threading.Thread(target=self._tick, daemon=True)
            self.ticker.start()

    # -- the log
    def log(self, msg):
        with self.lock:
            if self.logf:
                self.logf.write(msg + '\n'); self.logf.flush()
            if self.verbose:
                print(msg, flush=True)

    def write_raw(self, text):
        """Output of a tool the patcher runs (derive): to the log, and with --verbose to the screen."""
        with self.lock:
            if self.logf:
                self.logf.write(text); self.logf.flush()
            if self.verbose:
                sys.stdout.write(text); sys.stdout.flush()

    # -- the phases
    def _finish(self, key, now):
        if key in self.finished:
            return
        self.finished.add(key)
        self.done_w += self.weight[key]
        if key == self.cur:
            self.done_t += now - self.cur_t0
            self.logf.write(f'[{clock(now - self.t0)}] {self.words[key]}: {now - self.cur_t0:.1f} s\n')

    def start(self, key):
        """Phase `key` begins: the current one and any before `key` not started (skipped) count as done."""
        with self.lock:
            now = time.time()
            if self.cur is not None:
                self._finish(self.cur, now)
            for k in self.keys[:self.keys.index(key)]:
                self._finish(k, now)
            self.cur, self.cur_t0, self.frac, self.measured = key, now, 0.0, False
            self._draw(force=True)

    def step_done(self, name):
        """derive finished step `name`: the next step not finished begins (whatever order derive chose)."""
        k = 'step:' + name
        if k not in self.weight:
            return
        if k != self.cur:
            with self.lock:
                self._finish(k, time.time())
            return
        i = self.keys.index(k)
        nxt = next((q for q in self.keys[i + 1:] if q.startswith('step:') and q not in self.finished), None)
        if nxt:
            self.start(nxt)
        else:
            with self.lock:
                now = time.time()
                self._finish(k, now)
                self.frac, self.measured = 1.0, True

    def part(self, f):
        with self.lock:
            self.frac, self.measured = max(0.0, min(1.0, f)), True
            self._draw()

    def _rate(self, now, current=False):
        """Seconds per unit of weight on this machine: the phases finished so far (with the current one's measured
        part; current=True: also the time the current phase has taken, however far it got), blended with the release's
        own timings (rate 1) so that the first, short phases do not decide alone."""
        w, t = self.done_w, self.done_t
        if self.cur is not None and (current or (self.measured and self.frac > 0.05)):
            w += self.weight[self.cur] * self.frac_now(now); t += now - self.cur_t0
        prior = 0.15 * self.total
        return (t + prior) / (w + prior)

    def frac_now(self, now):
        """The current phase's fraction: as measured, else by the time it is expected to take, up to 95%."""
        if self.measured:
            return self.frac
        return min(0.95, (now - self.cur_t0) / (self.weight[self.cur] * self._rate(now)))

    def fraction(self, now=None):
        now = now or time.time()
        if self.cur is None:
            return 0.0
        return min(1.0, (self.done_w + self.weight[self.cur] * self.frac_now(now)) / self.total)

    def line(self, now=None):
        now = now or time.time()
        f = self.fraction(now)
        el = now - self.t0
        left = max(0.0, (1 - f) * self.total * self._rate(now, current=True)) if self.cur else 0.0
        words = self.words.get(self.cur, 'starting')
        try:
            cols = shutil.get_terminal_size((80, 24)).columns
        except (OSError, ValueError):
            cols = 80
        cols = max(40, cols) - 1                         # (the last column wraps on the Windows console)
        longest = max(len(w) for w in self.words.values())
        barw = max(10, min(30, cols - longest - 41))      # (the same width all along: 41 = brackets, %, the times)
        n = int(f * barw)
        head = f'[{"#" * n}{"." * (barw - n)}] {int(f * 100):3d}%  {words}'
        tails = [f'{clock(el)} so far, about {clock(left)} left', f'about {clock(left)} left', ''] if f > 0.02 else \
            [f'{clock(el)} so far', '']
        text = next((head + '  ' + t for t in tails if t and len(head) + 2 + len(t) <= cols), head)
        return text[:cols], f

    def _draw(self, force=False):
        if self.closed:
            return
        if self.tty:
            text, _ = self.line()
            pad = max(0, self.width_shown - len(text))
            self.out.write('\r' + text + ' ' * pad); self.out.flush()
            self.width_shown = len(text)
        elif force and not self.verbose and self.cur != self.shown:
            f = self.fraction()
            self.out.write(f'{int(f * 100):3d}%  {self.words[self.cur]}  ({clock(time.time() - self.t0)})\n')
            self.out.flush()
            self.shown = self.cur

    def _tick(self):
        while not self.closed:
            time.sleep(0.5)
            with self.lock:
                self._draw()

    def done(self, ok=True):
        """Ends the bar: the full bar on success; on failure the line as it stood. The log stays open for close()."""
        with self.lock:
            if self.closed:
                return
            now = time.time()
            if ok and self.cur is not None:
                self.logf.write(f'[{clock(now - self.t0)}] {self.words[self.cur]}: {now - self.cur_t0:.1f} s\n')
            if self.tty:
                if ok:
                    n = len(self.line(now)[0].split(']')[0]) - 1
                    text = f'[{"#" * n}] 100%  done in {clock(now - self.t0)}'
                else:
                    text, _ = self.line(now)
                self.out.write('\r' + text + ' ' * max(0, self.width_shown - len(text)) + '\n'); self.out.flush()
            elif ok and not self.verbose:
                self.out.write(f'100%  done in {clock(now - self.t0)}\n'); self.out.flush()
            self.logf.write(f'[{clock(now - self.t0)}] {"done" if ok else "stopped"}\n')
            self.closed = True

    def close(self):
        with self.lock:
            if self.logf:
                self.logf.close(); self.logf = None


def file_hashes(path, label='checking'):
    size = os.path.getsize(path); prog = Progress(label, size)
    crc, md5, sha1, done = 0, hashlib.md5(), hashlib.sha1(), 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b: break
            crc = zlib.crc32(b, crc); md5.update(b); sha1.update(b); done += len(b); prog(done)
    prog.end()
    return dict(size=size, crc32=f'{crc & 0xffffffff:08x}', md5=md5.hexdigest(), sha1=sha1.hexdigest())


# ---------------------------------------------------------------- source image paths


def resolve_bin(path):
    """A .cue gives its (only) .bin; anything else is taken as the image."""
    if not os.path.exists(path):
        raise PatchError(f'"{path}" does not exist.')
    if path.lower().endswith('.cue'):
        bins = []
        with open(path, 'rb') as f:
            raw = f.read()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        for line in text.splitlines():
            line = line.strip()
            if re.match(r'^FILE(?:\s|$)', line, re.I):
                entry = re.match(r'^FILE\s+(?:"([^"]+)"|([^"\s]+))(?:\s|$)', line, re.I)
                if entry is None:
                    raise PatchError(f'{path}: malformed FILE line in the cue sheet: {line}')
                name = entry[1] or entry[2]
                bins.append(os.path.join(os.path.dirname(os.path.abspath(path)), name))
        if len(bins) != 1:
            raise PatchError(f'{path}: the cue sheet names {len(bins)} files; Digimon World is one data track '
                             '(one .bin). Use a redump-style dump.')
        if not os.path.exists(bins[0]):
            raise PatchError(f'{path} points to "{bins[0]}", which does not exist (rename it back or edit the .cue).')
        return bins[0]
    low = path.lower()
    for ext, what in (('.chd', 'CHD'), ('.ecm', 'ECM'), ('.pbp', 'PBP (PSP eboot)'), ('.7z', '7z archive'),
                      ('.zip', 'zip archive'), ('.rar', 'rar archive')):
        if low.endswith(ext):
            raise PatchError(f'{path} is a {what}. Extract or convert it to .bin/.cue first '
                             '(e.g. `chdman extractcd -i game.chd -o game.cue`).')
    return path


def boot_name(path):
    """The executable SYSTEM.CNF boots (SLUS_010.32 for Digimon World USA), or None."""
    size = os.path.getsize(path)
    sector = RAW if size % RAW == 0 else DATA if size % DATA == 0 else None
    if not sector: return None
    off = 24 if sector == RAW else 0
    with open(path, 'rb') as f:
        def data(lba):
            f.seek(lba * sector + off); return f.read(DATA)
        pvd = data(16)
        if pvd[1:6] != b'CD001': return None
        ext, ln = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
        for k in range(-(-ln // DATA)):
            d = data(ext + k); p = 0
            while p < DATA and d[p]:
                rec = d[p:p + d[p]]; p += d[p]
                if rec[33:33 + rec[32]].upper().startswith(b'SYSTEM.CNF'):
                    lba, n = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                    txt = data(lba)[:n].decode('latin-1')
                    for line in txt.splitlines():
                        if line.replace(' ', '').upper().startswith('BOOT='):
                            return line.split('\\')[-1].split(';')[0].strip().upper()
    return None


# ---------------------------------------------------------------- apply
def load_release(rel_dir):
    mp = os.path.join(rel_dir, 'manifest.json')
    if not os.path.exists(mp):
        raise PatchError(f'no manifest.json in {rel_dir}: run the script from the release folder '
                         '(or pass --release FOLDER).')
    with open(mp, encoding='utf-8') as source:
        m = json.load(source)
    if not isinstance(m, dict):
        raise PatchError('manifest.json must contain a release object.')
    if m.get('format') not in READS:
        raise PatchError(f'this release has format {m.get("format")}; this patcher reads formats {READS}. '
                         'Use the dwpatch.py that came with the release.')
    variants = m.get('variants')
    if not isinstance(variants, dict) or set(variants) != {'everything'} or m.get('default') != 'everything':
        raise PatchError('this patcher serves the everything release; use the patcher bundled with this package.')
    source_games = m.get('source_discs')
    if not isinstance(source_games, list) or any(not isinstance(g, str) for g in source_games) or sorted(source_games) != ['dcb', 'dw2', 'dw2003']:
        raise PatchError('the everything package requires the three source games; use the patcher of this release.')
    variant = variants['everything']
    local = variant.get('local') if isinstance(variant, dict) else None
    if not isinstance(local, dict) or local.get('builder') != 'derive':
        raise PatchError('this release needs its accompanying patcher; everything uses the derive builder.')
    return m


class SourceDisc:
    def __init__(self, path):
        self.f = open(path, 'rb')

    def data(self, off, n):
        """n bytes of the user-data space (2048 bytes of each sector, at sector*2048)."""
        out = bytearray()
        while n:
            lba, k = divmod(off, DATA); take = min(n, DATA - k)
            self.f.seek(lba * RAW + 24 + k); out += self.f.read(take); off += take; n -= take
        return bytes(out)

    def raw(self, lba, n=1):
        self.f.seek(lba * RAW); return self.f.read(RAW * n)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------- recording tool dependencies
HOOK = '''import os, sys
_log = os.environ.get('DWPATCH_TRACE'); _busy = []
def _dwpatch_hook(ev, args):
    if ev == 'open' and not _busy and args and isinstance(args[0], str):
        _busy.append(1)
        try:
            fd = os.open(_log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            os.write(fd, (os.path.abspath(args[0]) + '\\n').encode()); os.close(fd)
        except Exception:
            pass
        finally:
            _busy.pop()
if _log: sys.addaudithook(_dwpatch_hook)
'''


# ---------------------------------------------------------------- apply / check / info
def cmd_apply(a):
    rel = os.path.abspath(a.release or os.path.dirname(os.path.abspath(__file__)))
    return cmd_apply3(a, rel, load_release(rel))


def cmd_check(a):
    rel = os.path.abspath(a.release or os.path.dirname(os.path.abspath(__file__)))
    m = load_release(rel) if os.path.exists(os.path.join(rel, 'manifest.json')) else None
    bases = m['bases'] if m else BASES
    key, path, h = identify_base(a.disc, bases)
    say(f'{path}: {bases[key]["title"]}, clean ({h["sha1"]}). It can be patched.')


def cmd_info(a):
    rel = os.path.abspath(a.release or os.path.dirname(os.path.abspath(__file__)))
    m = load_release(rel)
    say(f'{release_line(m)}, from commit {m["commit"]}')
    for b in m['bases'].values():
        say(f'Takes: {b["title"]} {b["serial"]}, SHA-1 {b["sha1"]}')
    say(f'Needs Python {m["python_min"][0]}.{m["python_min"][1]}+')
    for k, v in m['variants'].items():
        say(f'  {k:6} {v["description"]}  [{v["patch"]}, {v["patch_size"]} bytes, {len(v["holes"])} files built locally]')


# ---------------------------------------------------------------- make-release (for us)
def iso_files(img):
    """[(path, lba, size)] of a raw image (ISO 9660)."""
    f = open(img, 'rb')

    def data(lba):
        f.seek(lba * RAW + 24); return f.read(DATA)
    out = []

    def walk(ext, ln, path):
        for k in range(-(-ln // DATA)):
            d = data(ext + k); p = 0
            while p < DATA and d[p]:
                rec = d[p:p + d[p]]; p += d[p]
                name = rec[33:33 + rec[32]]
                if name in (b'\0', b'\1'): continue
                e, n = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                full = path + '/' + name.decode('ascii').split(';')[0]
                if rec[25] & 2: walk(e, n, full)
                else: out.append((full, e, n))
    pvd = data(16)
    walk(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0], '')
    return out


def release_version(a):
    """make-release: the release's version and date (UTC, YYYY-MM-DD) by the repository's one rule, tools/version.py (the
    tag vX.Y.Z on HEAD, else X.Y.Z-dev.N+HASH and HEAD's commit date); --version overrides the version only."""
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    try:
        import version as V
    finally:
        sys.path.pop(0)
    info = V.describe(REPO)
    return (a.version or info['version']), info['date']


def release_line(m):
    """The release's name, version and date, as apply and info print it first ("Digimon World Horizon 0.1.0 (2026-10-27)")."""
    return f'{m["title"]} {m["version"]} ({m["date"]})'


def git_commit():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip() + \
            ('+dirty' if subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=REPO,
                                        capture_output=True, text=True).stdout.strip() else '')
    except OSError:
        return '?'


DESCRIPTIONS = {
    'everything': 'every patch, the story mod What the island forgot, eight languages, every imported species '
                  '(OPTIONS chooses); its files are made from your four discs by tools/derive (Python standard library)',
}


# The derive builder's oldest Python: the bundle's syntax needs 3.10 (match). 3.10 and 3.11 add floats in sum() without
# 3.12's compensation (Neumaier), and the card textures' and portraits' nearest-colour searches sum squared float
# differences: tools/derive installs 3.12's sum there (tools/derive/pysum.py), so they give the release's disc too.
# Checked 2026-10-27: 3.10, 3.11, 3.12 and 3.14 give the release's disc (US; JP Rev 1 with 3.10 and 3.14).
DERIVE_PYTHON_MIN = (3, 10)


def python_min(files):
    import ast
    for minor in range(8, 20):
        try:
            for f in files:
                if f.endswith('.py'): ast.parse(open(f, encoding='utf-8').read(), feature_version=(3, minor))
            return [3, minor]
        except SyntaxError:
            continue
    return [3, sys.version_info[1]]


def save_check(a):
    """Before anything is built: the saved game of every published release must load in this one (tools/dev/saves/
    releases.py, docs/reference/save-format.md "Every release's save"). The file check always; with --save-check-emu the
    first variant's disc Continues from each card in the emulator too (build/NAME/exe/SLUS_010.32 beside it, or ,map=)."""
    t = os.path.join(REPO, 'tools', 'dev', 'saves', 'releases.py')
    runs = [[sys.executable, t, 'check']]
    if a.save_check_emu:
        target, *flags = a.variant[0].split('=', 1)[1].split(',')
        mapf = dict(f.split('=', 1) for f in flags if '=' in f).get('map') or os.path.join(
            os.path.dirname(os.path.abspath(target)), os.path.basename(target)[:-4], 'exe', 'SLUS_010.32.elf.map')
        disc = target[:-4] + '.cue' if os.path.exists(target[:-4] + '.cue') else target
        runs.append([sys.executable, t, 'emu', disc, '--exe', mapf[:-len('.elf.map')]])
    for cmd in runs:
        if subprocess.run(cmd).returncode:
            raise SystemExit(f'make-release refused: a saved game of a published release does not load ({" ".join(cmd[1:3])}, '
                             'the table above)')


# ---------------------------------------------------------------- format 3: one package for every base disc
# The patched disc is laid out on the player's machine (isowriter.py, next to this script in a release, tools/ in the
# repository): every file of it is a recipe of operations on the files of the USA disc, named by their path; each
# base disc maps those paths onto its own files (mods/base-discs/dw1-<release>.json, shipped in the release's bases/):
#   same / renamed   the player's file as it is (its sectors are moved: their EDC/ECC are reused)
#   patch            the player's file with the mapping's few USA bytes (the title image and license of Europe)
#   own              the player's own file (the STR movies: each release's PAL / Japanese masters)
#   localize         made from the player's file by the mapping's tool (the Japanese disc's baked text)
#   needs-usa        no counterpart (the executable, the overlays, the scripts): never a whole-file source; runs of
#                    them that the patched code shares are copied from the player's own executable and overlays at
#                    the offsets make-release found on each release (reloc)
# FILE_OFFSET_TABLE, the executable's sector table, is rewritten for the layout the player's files give.
#
# Payload (xz): b'DWP3', u32 n, n bytes of JSON {layout, sources, files, license, code, reloc, fix, sha1, table}, then the
# literal bytes. Operations of a file: ["s", src] the whole source file; ["c", src, offset, length] bytes of a
# source that every base has as the USA bytes; ["r", k] code copy k (code[k] = [src, offset, length] on the USA disc,
# reloc[base][k] = [[path, offset, length], ...] on another base, then fix[base][k] = [[position, hex], ...] XORed
# onto them: the address fields of moved code); ["o", path, offset, length] bytes of an earlier file of the patched
# disc; ["b", delta index, offset, length] per-base bsdiff reconstruction; ["l", offset, length] literal bytes; ["h", hole, offset, length] bytes of a file built on the player's machine.
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(REPO, 'tools')]

# The releases a format 3 package can serve (redump; checked against redump 2026-10-25, tools/discs.py DW1_RELEASES)
BASES = {
    'us': dict(ORIGINAL),
    'eu': dict(title='Digimon World (Europe)', serial='SLES-02914', boot='SLES_029.14', size=387129792,
               crc32='028ae52b', sha1='9c2922445280309f3d9c62bb70b57d6ad6da015a', redump='http://redump.org/disc/4264/'),
    'fr': dict(title='Digimon World (France)', serial='SLES-03435', boot='SLES_034.35', size=392482944,
               crc32='a4e783fe', sha1='adfaa62f6756d1e363c50bd414d60a45f1f864b2', redump='http://redump.org/disc/28228/'),
    'de': dict(title='Digimon World (Germany)', serial='SLES-03434', boot='SLES_034.34', size=392485296,
               crc32='e8abaab4', sha1='408fa08bf1b8a72f421d6caa02f146cf43513133', redump='http://redump.org/disc/3059/'),
    'es': dict(title='Digimon World (Spain)', serial='SLES-03436', boot='SLES_034.36', size=392490000,
               crc32='646fdc95', sha1='b90a8efa596771ad84f678d64786fcc5fdd65889', redump='http://redump.org/disc/10761/'),
    'it': dict(title='Digimon World (Italy)', serial='SLES-03437', boot='SLES_034.37', size=392487648,
               crc32='8da5b1c4', sha1='1478a99829fe3c385d8b342ced861f1fa1be3188', redump='http://redump.org/disc/46143/'),
    'jp1': dict(title='DigimonWorld (Japan) (Rev 1)', serial='SLPS-01797', boot='SLPS_017.97', size=381162768,
                crc32='8dcabdbf', sha1='1d10389deee8c9849136623785c256071f2f9473', redump='http://redump.org/disc/37502/'),
}
NOT_A_BASE = {381160416: 'DigimonWorld (Japan), the first pressing of SLPS-01797: five models, the effects file and '
                         'eleven maps differ from the other releases, so it cannot be a base. The Rev 1 disc can'}
GOOD = ('same', 'renamed', 'patch')            # a base gives the USA bytes themselves
WHOLE = GOOD + ('own', 'localize')             # a base gives its own version of the file


def _iw():
    import isowriter
    return isowriter


def identify_base(path, bases):
    """(key, .bin path, hashes) of the player's disc among `bases` {key: redump info}; PatchError with a message
    for anything else."""
    path = resolve_bin(path)
    size = os.path.getsize(path)
    boot = None
    try:
        boot = boot_name(path)
    except (OSError, struct.error, IndexError, ValueError):
        pass
    names = ', '.join(b['title'] for b in bases.values())
    if size % RAW and size % DATA == 0:
        raise PatchError(f'{os.path.basename(path)} is a 2048-byte-per-sector ISO ({size} bytes). The patch needs '
                         f'the raw image (.bin, 2352 bytes per sector, MODE2/2352 in the .cue) of one of: {names}.')
    if boot and boot == 'SLPS_017.97' and size in NOT_A_BASE:
        raise PatchError(f'{os.path.basename(path)} is {NOT_A_BASE[size]} ({", ".join(sorted(bases))}).')
    cands = {k: b for k, b in bases.items() if b['boot'] == boot}
    if boot and not cands:
        what = OTHER_VERSIONS.get(boot) or next((b['title'] for b in BASES.values() if b['boot'] == boot),
                                                 'another game or version')
        raise PatchError(f'{os.path.basename(path)} is {what} (boots {boot}). This release needs one of: {names}.')
    sized = {k: b for k, b in cands.items() if b['size'] == size}
    if not sized:
        b = next(iter(cands.values()), None)
        raise PatchError(f'{os.path.basename(path)} has {size} bytes; ' +
                         (f'{b["title"]} has {b["size"]}. It looks like the right game but a different or modified '
                          f'dump (a trimmed/padded image, or a hack already applied). Make a clean dump; it should '
                          f'match {b["redump"]}' if b else f'it is not one of: {names}.'))
    h = file_hashes(path, 'checking your disc')
    for k, b in sized.items():
        if h['sha1'] == b['sha1']: return k, path, h
    b = next(iter(sized.values()))
    raise PatchError(f'{os.path.basename(path)} is not a clean {b["title"]} disc.\n'
                     f'  SHA-1 {h["sha1"]}, expected {b["sha1"]}\n  CRC32 {h["crc32"]}, expected {b["crc32"]}\n'
                     'It may be modified (another patch or hack applied, a save or cheat tool), or a bad dump. '
                     f'Use an untouched copy; a good dump matches {b["redump"]}')


def boot_config(source, filename):
    """Keep the player's PS-X settings, naming this build's executable in BOOT."""
    pattern = rb'(?im)^([ \t]*BOOT[ \t]*=[ \t]*cdrom:\\)[^;\r\n]+(?=;)'
    target = filename.replace('/', '\\').encode('ascii')
    result, count = re.subn(pattern, lambda m: m[1] + target, source)
    if count != 1:
        raise PatchError('the disc has no unique BOOT executable field')
    return result


def apply_ops(ops, src, disc_copy=None):
    """A mapping patch: copy/data/fill on its file, disc_copy from a player input."""
    out = bytearray()
    for op in ops:
        if 'copy' in op: o, n = op['copy']; out += src[o:o + n]
        elif 'fill' in op: out += bytes([op['fill'][0]]) * op['fill'][1]
        elif 'disc_copy' in op:
            if disc_copy is None: raise PatchError('mapping requires a disc source reader')
            out += disc_copy(*op['disc_copy'])
        else: out += bytes.fromhex(op['data'])
    return bytes(out)


class BaseDisc:
    """The player's disc as the USA one: data(usa path) gives the bytes its mapping says, source(usa path) a writer
    source (sectors moved where the player's file is used as it is)."""
    def __init__(self, key, path, mapping=None, tool_root=None, work=None, source_discs=None):
        self.key, self.mapping = key, mapping
        self.img = _iw().Image(path)
        self.map = mapping['files'] if mapping else None
        self.tool_root, self.work, self._cache, self._loc = tool_root, work, {}, None
        self.trace = None                                # make-release: records the files the localize tool opens
        self.source_discs = dict(s.split('=', 1) for s in source_discs or [])
        self._copy_images = {}

    def how(self, p):
        if self.map is None: return 'same' if p in self.img.files or p == 'license_data.dat' else 'missing'
        return self.map[p]['how'] if p in self.map else 'missing'

    def _own(self, p):
        return self.img.license() if p == 'license_data.dat' else self.img.read(p)

    def data(self, p, cache=False):
        if p in self._cache: return self._cache[p]
        how = self.how(p); e = self.map[p] if self.map else {}
        if how == 'same': b = self._own(p)
        elif how in ('renamed', 'own'): b = self._own(e.get('source', p))
        elif how == 'patch':
            src = self._own(e['source'])
            if hashlib.sha1(src).hexdigest() != e['from_sha1']:
                raise PatchError(f'{e["source"]} of your disc is not the one of {BASES[self.key]["title"]}.')
            b = apply_ops(e['ops'], src, self.read_copy)
        elif how == 'localize': b = self.localized(p)
        else:
            raise PatchError(f'the release needs {p} of the USA disc, which {BASES[self.key]["title"]} does not have '
                             f'({how}).')
        if how in GOOD and self.map is not None and hashlib.sha1(b).hexdigest() != e['sha1']:
            raise PatchError(f'{p}: your disc\'s file did not come out as the USA one (mapping {self.key}).')
        if cache: self._cache[p] = b
        return b

    def source(self, p):
        how = self.how(p)
        if how in ('same', 'renamed', 'own') and p != 'license_data.dat':
            own = p if how == 'same' else self.map[p].get('source', p)
            return self.img.source(own)
        b = self.data(p); return _iw().Source(len(b), lambda: b)

    def code(self, path):
        """A file of the player's disc by its own path (the reloc copies)."""
        key = '\0' + path
        if key not in self._cache: self._cache[key] = self._own(path)
        return self._cache[key]

    def read_copy(self, path, offset, length):
        """Bounded raw/data-plane copy; secondary inputs are the recipe's player discs."""
        image = self.img
        if path.startswith('@disc:'):
            _, game, path = path.split(':', 2)
            if game not in self.source_discs:
                raise PatchError(f'this copy needs your {game} source disc')
            if game not in self._copy_images:
                image = _iw().Image(self.source_discs[game])
                self._copy_images[game] = image
            image = self._copy_images[game]
        if offset < 0 or length < 0:
            raise PatchError('invalid disc copy range')
        if path == '@raw':
            image.f.seek(offset)
            data = image.f.read(length)
        elif path == '@userdata':
            out = bytearray()
            left = length
            while left:
                sector, pos = divmod(offset, DATA)
                take = min(left, DATA - pos)
                image.f.seek(sector * RAW + 24 + pos)
                part = image.f.read(take)
                if len(part) != take: raise PatchError('truncated disc copy source')
                out += part
                offset += take
                left -= take
            data = bytes(out)
        else:
            raise PatchError('unknown disc copy view')
        if len(data) != length:
            raise PatchError('truncated disc copy source')
        return data

    def localized(self, p):
        """A localize file (the Japanese disc's baked text): made by the mapping's tool from the player's files."""
        m = self.mapping; e = m['files'][p]
        if self._loc is None:
            tool = os.path.join(self.tool_root or REPO, m['localize_tool'])
            if not os.path.exists(tool):
                raise PatchError(f'{BASES[self.key]["title"]}: {p} carries baked Japanese text, made in our words by '
                                 f'{m["localize_tool"]}, which this release does not have.')
            dump = os.path.join(self.work, 'dump'); out = os.path.join(self.work, 'localize')
            for q in self.img.files:
                if self.img.files[q][2]: continue
                dst = os.path.join(dump, *q.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'wb') as f: f.write(self.img.read(q))
            os.makedirs(out, exist_ok=True)
            env = dict(os.environ)
            if self.trace:
                hook = os.path.join(self.work, 'hook'); os.makedirs(hook, exist_ok=True)
                open(os.path.join(hook, 'sitecustomize.py'), 'w').write(HOOK)
                env.update(PYTHONPATH=hook, DWPATCH_TRACE=self.trace,      # a fresh cache: the sources are opened
                           PYTHONPYCACHEPREFIX=os.path.join(self.work, 'pyc'))
            if SCREEN is not None and not SCREEN.verbose:      # (its output goes to the log)
                r = subprocess.run([sys.executable, tool, out, '--extracted', dump], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
                o = r.stdout or b''
                SCREEN.write_raw(o.decode('utf-8', 'replace') if isinstance(o, bytes) else o)
            else:
                r = subprocess.run([sys.executable, tool, out, '--extracted', dump], env=env)
            if r.returncode:
                raise PatchError(f'{m["localize_tool"]} failed (' + ('the log says why).' if SCREEN is not None else
                                                                     'the message above says why).'))
            self._loc = out
        b = open(os.path.join(self._loc, *p.split('/')), 'rb').read()
        if 'ops' in e: b = apply_ops(e['ops'], b, self.read_copy)
        mk = bytearray(b)
        for o, n in e['regions']: mk[o:o + n] = bytes(n)
        if hashlib.sha1(bytes(mk)).hexdigest() != e['masked_sha1']:
            raise PatchError(f'{p}: {m["localize_tool"]} changed more than the text of the images.')
        return b


def read_payload3(raw):
    b = lzma.decompress(raw)
    if b[:4] != b'DWP3': raise PatchError('the patch file is not a DWP3 patch.')
    n, = struct.unpack_from('<I', b, 4)
    p = json.loads(b[8:8 + n].decode('utf-8')); p['blob'] = b[8 + n:]
    return p


def linker_word_bytes(entry):
    """Evaluate section-address expressions, never arbitrary table payloads.

    The mandatory developer gate independently binds these expressions to the
    current native ELF's R_MIPS_32 relocations and linker data extents.
    """
    out = bytearray()
    end = 0
    for row in entry.get('linker_words', []):
        if (not isinstance(row, list) or len(row) != 4
                or not isinstance(row[1], str) or not row[1].startswith('.')
                or any(type(row[i]) is not int for i in (0, 2, 3))):
            raise PatchError('invalid linker word expression.')
        offset, section, address, addend = row
        if (offset < end or offset + 4 > entry['size'] or addend < 0
                or not 0x80000000 <= address <= address + addend < 0x80200000):
            raise PatchError('invalid linker word bounds.')
        out.extend(struct.pack('<I', address + addend))
        end = offset + 4
    return bytes(out)


def generated_layout(entry):
    """Source-tail fields may only populate their declared destination bytes."""
    rows = [[row[0], 4] for row in entry.get('linker_words', [])]
    if entry.get('font_layout'):
        import fontcopy
        layout = entry['font_layout']
        if len(layout) != len(fontcopy.CAPACITIES) or {r[1] for r in layout} != set(fontcopy.CAPACITIES):
            raise PatchError('incomplete regional font layout.')
        end = 0
        for offset, name, size in layout:
            if type(offset) is not int or offset < end or size != fontcopy.CAPACITIES[name] or offset + size > entry['size']:
                raise PatchError('invalid regional font layout.')
            rows.append([offset, size])
            end = offset + size
    if entry.get('table_recipes'):
        import fontcopy
        rows.extend(fontcopy.table_layout(entry['table_recipes']))
    ordered = sorted(rows)
    if any(a + n > b for (a, n), (b, _) in zip(ordered, ordered[1:])):
        raise PatchError('overlapping generated fields.')
    return rows


def validate_linker_copies(entry, delta, source_size, blob):
    """Require every generated byte to use its own zero-diff source field."""
    linker_word_bytes(entry)
    rows = generated_layout(entry)
    if not rows:
        return
    destinations = [offset + i for offset, size in rows for i in range(size)]
    copied = 0
    oldpos = newpos = 0
    dp = delta['diff'][0]
    dend = dp + delta['diff'][1]
    extra_count = 0
    for n, extra, seek in delta['control']:
        if (any(type(value) is not int for value in (n, extra, seek))
                or min(n, extra) < 0 or dp + n > dend
                or newpos + n + extra > entry['size']):
            raise PatchError('invalid binary delta control.')
        lo, hi = max(oldpos, source_size), min(oldpos + n, source_size + len(destinations))
        for at in range(lo, hi):
            if newpos + at - oldpos != destinations[at - source_size] or blob[dp + at - oldpos] != 0:
                raise PatchError('a generated field is used as table payload.')
            copied += 1
        oldpos += n + seek
        newpos += n + extra
        dp += n
        extra_count += extra
    if dp != dend or extra_count != delta['extra'][1] or newpos != entry['size']:
        raise PatchError('invalid binary delta control coverage.')
    if copied != len(destinations):
        raise PatchError('a declared generated field is still encoded in delta bytes.')


def binary_delta_source(delta, read_source):
    """Read pinned player files into the delta's source address space."""
    old = read_source(delta['source'])
    if hashlib.sha1(old).hexdigest() != delta['source_sha1']:
        raise PatchError('a binary delta source differs from the release.')
    regions = [[0, len(old), delta['source'], 0]]
    parts = [old]
    end = len(old)
    seen = {delta['source']}
    for source in delta.get('additional_sources', []):
        if (not isinstance(source, dict) or set(source) != {'file', 'size', 'sha1'}
                or not isinstance(source['file'], str) or source['file'] in seen
                or type(source['size']) is not int or source['size'] <= 0):
            raise PatchError('invalid additional binary delta source.')
        data = read_source(source['file'])
        if len(data) != source['size'] or hashlib.sha1(data).hexdigest() != source['sha1']:
            raise PatchError('an additional binary delta source differs from the release.')
        regions.append([end, end + len(data), source['file'], 0])
        parts.append(data)
        end += len(data)
        seen.add(source['file'])
    return b''.join(parts), regions


def apply_binary_delta(entry, base_key, read_source, blob, *, tool_root=None):
    """Apply bsdiff control/diff/extra blocks in bounded 64 KiB chunks.

    Source and output are bounded by the corresponding game file; no whole-disc
    buffer, C extension, NumPy, Pillow or bzip2 decoder is needed on the player.
    """
    d = entry['bases'].get(base_key)
    if d is None:
        raise PatchError('the release has no binary delta for your disc.')
    old, _ = binary_delta_source(d, read_source)
    original_size = len(old)
    destinations = [offset + i for offset, size in generated_layout(entry) for i in range(size)]
    old += linker_word_bytes(entry)
    if entry.get('font_layout'):
        import fontcopy
        old += fontcopy.generated_tail(entry['font_layout'], read_source(d['source']), base_key, tool_root)
    if entry.get('table_recipes'):
        import fontcopy
        old += fontcopy.table_tail(entry['table_recipes'], base_key, read_source, tool_root)
    dp, dn = d['diff']; ep, en = d['extra']
    if min(dp, dn, ep, en, entry['size']) < 0 or dp + dn > len(blob) or ep + en > len(blob):
        raise PatchError('invalid binary delta block bounds.')
    dend, eend = dp + dn, ep + en
    validate_linker_copies(entry, d, original_size, blob)
    out = bytearray()
    oldpos = 0
    for n, extra, seek in d['control']:
        if min(n, extra) < 0 or dp + n > dend or ep + extra > eend or len(out) + n + extra > entry['size']:
            raise PatchError('invalid binary delta control.')
        left = n
        while left:
            take = min(left, 65536)
            chunk = bytearray(blob[dp:dp + take])
            lo, hi = max(0, oldpos), min(len(old), oldpos + take)
            for i in range(lo, hi):
                j = i - oldpos
                if i >= original_size:
                    if (len(out) + j != destinations[i - original_size]
                            or chunk[j] != 0):
                        raise PatchError('a generated linker word is used as table payload.')
                chunk[j] = (chunk[j] + old[i]) & 255
            out.extend(chunk)
            oldpos += take; dp += take; left -= take
        out.extend(blob[ep:ep + extra]); ep += extra
        oldpos += seek
    if len(out) != entry['size'] or dp != dend or ep != eend or hashlib.sha1(out).hexdigest() != entry.get('sha1_by_base', {}).get(base_key, entry['sha1']):
        raise PatchError('a binary delta output differs from the release.')
    return bytes(out)


def build_disc3(p, base, holes, out_bin, expect_sha1=None, progress=True):
    """Lays the patched disc out from the payload `p` on BaseDisc `base` with the locally built holes {id: bytes}.
    Returns (SHA-1, Plan)."""
    iw = _iw(); srcs, blob = p['sources'], p['blob']
    font_arrays = None
    def copied(path, offset, length, own=False):
        nonlocal font_arrays
        if path.startswith('@boot:'):
            return boot_config(base.code('SYSTEM.CNF'), path[6:])[offset:offset + length]
        if path.startswith('@font:'):
            if font_arrays is None:
                import fontcopy
                font_arrays = fontcopy.rebuild(base, p['font'])
            return font_arrays[path.split(':', 1)[1]][offset:offset + length]
        if path.startswith('@disc:'):
            return base.read_copy(path, offset, length)
        if path == '@raw':                         # audited license/directory/sector metadata copies
            base.img.f.seek(offset)
            return base.img.f.read(length)
        if path == '@userdata':                    # includes games' archives outside ISO directory files
            out = bytearray()
            while length:
                sector, pos = divmod(offset, DATA)
                take = min(length, DATA - pos)
                base.img.f.seek(sector * RAW + 24 + pos)
                out += base.img.f.read(take)
                offset += take; length -= take
            return bytes(out)
        data = base.code(path) if own else base.data(path, cache=True)
        return data[offset:offset + length]
    def assemble(ops):
        out = bytearray()
        for op in ops:
            t = op[0]
            if t == 's': out += base.data(srcs[op[1]])
            elif t == 'c': out += base.data(srcs[op[1]], cache=True)[op[2]:op[2] + op[3]]
            elif t == 'r':
                if base.key == 'us' or base.map is None:
                    s, o, n = p['code'][op[1]]; out += copied(srcs[s], o, n)
                else:
                    pieces = p['reloc'].get(base.key, {}).get(str(op[1]))
                    if pieces is None: raise PatchError(f'this release has no copy table for {BASES[base.key]["title"]}.')
                    at = len(out)
                    for path, o, n in pieces: out += copied(path, o, n, own=True)
                    for pos, x in p.get('fix', {}).get(base.key, {}).get(str(op[1]), ()):
                        for i, v in enumerate(bytes.fromhex(x)): out[at + pos + i] ^= v   # (an address moved)
            elif t == 'b':
                data = apply_binary_delta(p['deltas'][op[1]], base.key, base.code, blob, tool_root=getattr(base, 'tool_root', None))
                out += data[op[2]:op[2] + op[3]]
            elif t == 'o': out += files[op[1]][op[2]:op[2] + op[3]]                # an earlier file of this disc
            elif t == 'l': out += blob[op[1]:op[1] + op[2]]
            elif t == 'h':
                if op[1] not in holes: raise PatchError('a file built on your machine is missing.')
                out += holes[op[1]][op[2]:op[2] + op[3]]
            else: raise PatchError('the patch file is damaged (unknown operation).')
        return bytes(out)
    files, bad = {}, []
    for path, ops in p['files'].items():
        if len(ops) == 1 and ops[0][0] == 's':
            files[path] = base.source(srcs[ops[0][1]])
        else:
            # (a file that is one hole is the hole as built, checked against its SHA-1 on this base: local_holes3;
            # on a base whose own files the build reads, the Japanese one, it may differ from the USA-based file)
            whole_hole = len(ops) == 1 and ops[0][0] == 'h' and ops[0][2] == 0 and ops[0][1] in holes
            b = holes[ops[0][1]] if whole_hole else assemble(ops)
            if not whole_hole and hashlib.sha1(b).hexdigest() != p.get('sha1_by_base', {}).get(base.key, {}).get(path, p['sha1'][path]): bad.append(path)
            files[path] = b
    lic = assemble(p['license'])
    if bad:
        raise PatchError('these files came out different from the release: ' + ', '.join(bad) + '. Nothing was written.')
    lay = iw.Layout(p['layout'])
    t = p.get('table')
    if t:
        pl = iw.plan(lay, {k: (s.size if isinstance(s, iw.Source) else len(s)) for k, s in files.items()})
        where = {q.split('/')[-1]: v for q, v in pl.lba.items()}; where['PSX.EXE'] = where[t['file'].split('/')[-1]]
        exe = bytearray(files[t['file']])
        n, changed, missing, names = iw.rewrite_file_table(exe, t['offset'], where)
        if n != t['entries']: raise PatchError('the executable\'s sector table is not where the release says.')
        files[t['file']] = bytes(exe)
    prog = Progress(f'writing {os.path.basename(out_bin)}', 1) if progress else None
    def tick(done, total):
        if prog: prog.total = total; prog(done)
    pl, sha = iw.write(lay, files, out_bin, license=lic, cue=False, progress=tick)
    if prog: prog.end()
    if expect_sha1 and sha != expect_sha1:
        os.remove(out_bin)
        raise PatchError(f'the patched disc does not match the release (SHA-1 {sha}, expected {expect_sha1}). '
                         'Nothing was written.')
    return sha, pl


def write_cue(out_bin):
    cue = out_bin[:-4] + '.cue'
    with open(cue, 'w', newline='\r\n') as f:
        f.write(f'FILE "{os.path.basename(out_bin)}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
    return cue


def local_holes3(m, v, base, rel, work, a):
    """{hole id: bytes}: the locally built files of a variant, checked against their SHA-1."""
    builder = v['local'].get('builder')
    if builder != 'derive':
        raise PatchError(f'this patcher requires the derive builder, got "{builder}"; use the patcher of the release.')
    files = derive_holes(rel, m, v, base, work, source_discs=getattr(a, 'source_disc', None))
    holes, bad = {}, []
    if SCREEN is not None: SCREEN.start('holes')
    for i, h in enumerate(v['holes']):
        if SCREEN is not None and i % 20 == 0: SCREEN.part(i / len(v['holes']))
        q = files.get(h['file'])
        b = open(q, 'rb').read() if q and os.path.exists(q) else b''
        # (a base whose own files the build reads differently, the Japanese one's localized images: its own SHA-1)
        if hashlib.sha1(b).hexdigest() != h.get('sha1_by_base', {}).get(base.key, h['sha1']): bad.append(h['file'])
        holes[h['id']] = b
    if bad:
        raise PatchError('these files came out different from the release: ' + ', '.join(bad) + '. Nothing was written.')
    return holes


# ---------------------------------------------------------------- format 3: the derive builder (tools/derive)
# Every derived file of the disc (docs/derive.md) is made by tools/derive from the player's files:
# `python -m tools.derive build --recipe NAME` in a tree of the release's bundle/ with the files of the manifest's
# `extract` list written into extracted/ from the player's disc (BaseDisc.data, by USA path: any base). Its manifest
# (OUT/derived/manifest.json) names each file by disc path. The bundle holds what the build opened at make-release
# (derive --record, in a clean tree), every published file of content/ and story/base, tools/derive whole, and the
# executable's facts (exe-facts.json: the build's settings of the decompilation tree, which the player does not have).
DERIVE_TREES = ('tools', 'content', 'story', 'mods', 'text', 'docs/data')   # what a clean tree copies of the repository


STEP_DONE = re.compile(r'^derive (\S+)(?: \(\S+\))?: \d+ files, ([\d.]+) s$')   # current and recorded step logs


class _WindowsDeriveJob:
    """Kill-on-close job: descendants remain owned even after the derive parent exits."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                        ('active', w.DWORD), ('affinity', ctypes.c_size_t),
                        ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('read_ops', 'write_ops', 'other_ops',
                                                     'read_bytes', 'write_bytes', 'other_bytes')]
        class Limits(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                        ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                        ('peak_job', ctypes.c_size_t)]
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, restype, args in [
            ('CreateJobObjectW', w.HANDLE, [w.LPVOID, w.LPCWSTR]),
            ('SetInformationJobObject', w.BOOL, [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]),
            ('AssignProcessToJobObject', w.BOOL, [w.HANDLE, w.HANDLE]),
            ('CloseHandle', w.BOOL, [w.HANDLE]),
        ]:
            fn = getattr(self.api, name); fn.restype = restype; fn.argtypes = args
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        limits = Limits(); limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error()); self.close(); raise error

    def assign(self, process):
        import ctypes
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle); self.handle = None


def _stop_derive(process, job):
    if job is not None:
        job.close()  # Includes grandchildren, even if the parent already exited.
    else:
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try:
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
        finally:
            # The parent exiting is not proof that its workers have exited.
            # A second Ctrl-C during the grace period must still kill them.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
        return
    process.wait()


def _derive_lines(process, job):
    # A dead parent's worker may still hold stdout open. Read on a thread so the
    # apply thread can notice the parent's failure and kill that worker too.
    pending = queue.Queue()
    def read():
        try:
            for line in process.stdout: pending.put(line)
        except BaseException as error:
            pending.put(error)
        finally:
            pending.put(None)
    reader = threading.Thread(target=read, name='dwpatch-derive-output', daemon=True)
    reader.start()
    try:
        stopped = False
        while True:
            code = process.poll()
            if not stopped and code is not None and code != 0:
                _stop_derive(process, job); stopped = True
            try: item = pending.get(timeout=.1)
            except queue.Empty: continue
            if item is None: break
            if isinstance(item, BaseException): raise item
            yield item
    finally:
        # The caller terminates the group on exceptions before closing stdout.
        # On EOF the reader has already finished.
        if not reader.is_alive(): reader.join()


def derive_run(root, recipe, facts, record=False, jobs=None, log=None, source_discs=None):
    """tools/derive of `root` builds the recipe into root/build/NAME (the recipe's NAME: the build's own paths, so the
    same bytes) -> (its manifest, the folder). Its output goes to `log` (a file) and, while apply's screen runs, to the
    screen's log, each step's end moving the bar (the step's line, STEP_DONE)."""
    with open(os.path.join(root, 'tools', 'derive', 'recipes', f'{recipe}.json')) as source:
        rec = json.load(source)
    out = os.path.join(root, 'build', rec['environment']['NAME'])
    argv = [sys.executable, '-m', 'tools.derive', 'build', '--recipe', recipe, '--out', out, '--facts', facts]
    argv += ['--record'] if record else ['--jobs', str(jobs or os.cpu_count() or 1)]
    for source in source_discs or []:
        argv += ['--source-disc', source]
    # (PYTHONDONTWRITEBYTECODE: every module's source is opened, the record sees it; unbuffered: its lines as they come;
    # UTF-8 mode: the logs' Spanish text on a console whose code page is not UTF-8)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', PYTHONUTF8='1')
    # Packages replay in their private tree, independent of developer caches.
    for name in ('DW_BUILD_CACHE', 'DW_CACHE_DIR', 'DW_CLEAN_NATIVE'):
        env.pop(name, None)
    t0 = time.time()
    lines = []
    lf = open(log, 'w', encoding='utf-8') if log else None
    p = None
    job = None
    try:
        options = dict(cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if os.name == 'nt':
            job = _WindowsDeriveJob()
            # Gate Python before importing derive: no worker can escape before job assignment.
            gate = ('import sys,runpy; '
                    'sys.stdin.buffer.read(1) == b"1" or sys.exit(1); sys.argv=sys.argv[1:]; '
                    'runpy.run_module("tools.derive",run_name="__main__",alter_sys=True)')
            options.update(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, stdin=subprocess.PIPE)
            p = subprocess.Popen([argv[0], '-c', gate, 'tools.derive', *argv[3:]], **options)
            job.assign(p)
            p.stdin.write(b'1'); p.stdin.close()
        else:
            p = subprocess.Popen(argv, start_new_session=True, **options)
        for raw in _derive_lines(p, job):
            line = raw.decode('utf-8', 'replace').replace('\r\n', '\n')
            lines.append(line)
            if lf: lf.write(line)
            if SCREEN is not None:
                SCREEN.write_raw(line)
                mm = STEP_DONE.match(line.rstrip('\n'))
                if mm: SCREEN.step_done(mm.group(1))
        code = p.wait()
        if code: _stop_derive(p, job)
    except BaseException:
        if p is not None:
            if job is not None:
                job.close()
                # Assignment itself may have failed; the gated parent has no children yet.
                if p.poll() is None: p.kill()
                p.wait()
            else:
                _stop_derive(p, None)
        raise
    finally:
        if p is not None:
            if p.stdin is not None: p.stdin.close()
            p.stdout.close()
        if job is not None: job.close()
        if lf: lf.close()
    if code:
        tail = ''.join(lines)[-3000:]
        if SCREEN is not None and not SCREEN.verbose:
            raise PatchError('building the files from your disc failed. Its last lines:\n'
                             + ''.join(lines[-12:]).rstrip('\n'))
        say(tail)
        raise PatchError('building the files from your disc failed (the message above says why).')
    say(f'   tools/derive: {time.time() - t0:.0f} s')
    return json.load(open(os.path.join(out, 'derived', 'manifest.json'))), out


def derive_files(man, out):
    """{disc path: the file derive made}"""
    return {d: os.path.normpath(os.path.join(out, e['file'])) for d, e in man['files'].items()}


def needs_usa_paths():
    out = set()
    d = os.path.join(REPO, 'mods', 'base-discs')
    for p in sorted(os.listdir(d)):
        if p.startswith('dw1-') and p.endswith('.json'):
            out |= {q for q, e in json.load(open(os.path.join(d, p)))['files'].items() if e.get('how') == 'needs-usa'}
    return out


def derive_tree(root, files, extract, data, phase=None):
    """A clean tree: `files` {relative path: source file} copied, extracted/ written from data(usa path). phase(key)
    while apply's screen runs: the copy is phase 'tools', the player's files 'read' (each counted by files done)."""
    for k, (r, src) in enumerate(files.items()):
        if phase and k == 0: phase('tools')
        dst = os.path.join(root, *r.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        if SCREEN is not None and k % 50 == 0: SCREEN.part(k / len(files))
    for k, q in enumerate(extract):
        if phase and k == 0: phase('read')
        dst = os.path.join(root, 'extracted', *q.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f: f.write(data(q))
        if SCREEN is not None and k % 10 == 0: SCREEN.part(k / len(extract))


def publication_bundle_files(files):
    """Exclude normalization data for source releases the player cannot select.

    Keep historical developer recipes in the repository, but never ship their
    unused original model bytes in the player package.
    """
    import discs
    retired = {f'content/imports/releases/{d["id"]}.json'
               for d in discs.SOURCE_VARIANTS if not d.get('supported', True)}
    return {name: path for name, path in files.items() if name not in retired}


def make_bundle_derive(usa, work, out, recipe, facts, source_discs=None):
    """The bundle of the derive builder: the repository's tracked trees and the recipe's untracked inputs in a clean
    tree with every Form 1 file of the USA disc but the needs-usa ones, derive --record there, and the files it opened
    (+ content/, story/base, tools/derive) -> (bundle files, extract list, the clean build's {disc path: file})."""
    cand = os.path.join(work, 'cand')
    tracked = subprocess.run(['git', 'ls-files', *DERIVE_TREES], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.split('\n')
    tracked += ['decomp/' + f for f in subprocess.run(['git', 'ls-files', 'config/us'], cwd=os.path.join(REPO, 'decomp'),
                                                       capture_output=True, text=True, check=True).stdout.split('\n') if f]
    files = {f: os.path.join(REPO, f) for f in tracked if f and os.path.isfile(os.path.join(REPO, f))}
    files = publication_bundle_files(files)
    files['exe-facts.json'] = facts
    usa_only = needs_usa_paths()
    extract = sorted(q for q, (lba, n, form2) in usa.files.items() if not form2 and q not in usa_only)
    say(f'  a clean tree: {len(files)} source/configuration files, {len(extract)} files of the USA disc (not the needs-usa ones)')
    derive_tree(cand, files, extract, usa.read)
    say('  tools/derive there, recording every file it opens (one process)')
    man, dout = derive_run(cand, recipe, os.path.join(cand, 'exe-facts.json'), record=True,
                           log=os.path.join(work, 'derive-cand.log'), source_discs=source_discs)
    opened = {p for s in man['steps'].values() for p in s.get('inputs', [])}
    # Step modules import language selection before recording starts, so the open-file
    # trace cannot discover this required dependency of story and localize.
    bundle = {'exe-facts.json', 'tools/languages.py'} | {r for r in files if r.startswith(('tools/derive/', 'story/base/', 'content/'))
                                   and '__pycache__' not in r}
    if 'tools/city_residents.py' in files:
        bundle.add('tools/city_residents.py')  # also needed when an import came from a cached module
    if source_discs:
        bundle |= {r for r in files if r.startswith('content/imports/releases/')}
        bundle.add('tools/discs.py')
        # A PAL recording never imports this verifier, but the supported Japanese
        # source needs it to check its byte-identical models against the PAL pins.
        bundle.add('tools/dw3release.py')
    other = set()
    for p in sorted(opened):
        if os.path.isabs(p) or p.startswith('extracted/'):
            continue                                       # (/nonexistent, temporary files; the player's files)
        if p in files: bundle.add(p)
        elif os.path.isfile(os.path.join(cand, p)): other.add(p)   # made during the run (not ours to ship)
    say(f'  bundle: {len(bundle)} files ({sum(os.path.getsize(files[r]) for r in bundle) // 1024} KB); '
        f'{len(other)} files the run made and read back')
    for r in sorted(bundle):
        dst = os.path.join(out, 'bundle', *r.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(files[r], dst)
    return sorted(bundle), extract, derive_files(man, dout)


def regional_derive(mapping, extract):
    """Replay when derive consumes the region's own artwork rather than USA bytes."""
    return bool(mapping and (mapping.get('localize_tool') or any(
        mapping['files'].get(q, {}).get('how') == 'own' for q in extract)))


def derive_holes(rel, m, v, base, work, jobs=None, source_discs=None):
    """The derive builder on the player's disc: {disc path: the file made}."""
    root = os.path.join(work, 'root')
    supplied = {s.split('=', 1)[0] for s in source_discs or []}
    missing = set(m.get('source_discs', [])) - supplied
    if missing:
        raise PatchError('source discs required: ' + ', '.join(sorted(missing)) +
                         '; use --source-disc dcb=IMAGE --source-disc dw2=IMAGE --source-disc dw2003=IMAGE')
    bundle = os.path.join(rel, 'bundle')
    files = {os.path.relpath(os.path.join(dp, f), bundle).replace(os.sep, '/'): os.path.join(dp, f)
             for dp, _, fs in os.walk(bundle) for f in fs}
    phase = SCREEN.start if SCREEN is not None else None
    derive_tree(root, files, m['extract'], lambda q: base.data(q), phase)
    if SCREEN is not None:
        SCREEN.start(next(k for k in SCREEN.keys if k.startswith('step:')))
    man, out = derive_run(root, v['local']['recipe'], os.path.join(root, 'exe-facts.json'), jobs=jobs,
                          source_discs=source_discs)
    return derive_files(man, out)


# What apply's screen calls each phase, and the time each takes when the release has no timings of its own (the
# everything disc, 16 CPUs, 2026-10-27; only their proportions matter): derive's steps in the order it runs them.
PHASE_WORDS = dict(check='checking your disc', tools='preparing the build', read='reading the files of your disc',
                   holes='checking the files built', write='writing the patched disc', result='checking the result')
STEP_WORDS = dict(models='building the Digimon models', imports='importing the Digimon from your discs', overlays='building the new Digimon',
                  species='building the Digimon data', sound='building the sound banks', title='drawing the title screen',
                  maps='building the new maps', retouch='retouching the maps', story='compiling the story',
                  screens='adding the new screens', localize='translating the images', signs='translating the map signs',
                  balance='placing the wild Digimon', storycopies='copying the story\'s maps',
                  plan='listing the files')
TIMINGS = dict(check=2, tools=1, read=1, holes=0.2, write=15, result=0.3,
               steps=[['models', 20], ['overlays', 25], ['species', 17], ['sound', 2], ['title', 0], ['maps', 37],
                      ['retouch', 4], ['story', 17], ['screens', 7], ['localize', 6], ['signs', 18], ['balance', 4],
                      ['storycopies', 0], ['plan', 0.3]])


def apply_phases(m, v):
    """[(key, words, seconds)] of an apply of variant v: the release's measured times (make-release, timings.apply)
    or TIMINGS."""
    t = (m.get('timings') or {}).get('apply') or TIMINGS
    ph = [('check', PHASE_WORDS['check'], t['check'])]
    ph += [(k, PHASE_WORDS[k], t[k]) for k in ('tools', 'read')]
    ph += [('step:' + n, STEP_WORDS.get(n, f'building ({n})'), sec) for n, sec in t['steps']]
    ph += [(k, PHASE_WORDS[k], t[k]) for k in ('holes', 'write', 'result')]
    return ph


def cmd_apply3(a, rel, m):
    global SCREEN
    vname = a.variant or m['default']
    if vname not in m['variants']:
        raise PatchError(f'no variant "{vname}" in this release (it has: {", ".join(m["variants"])}).')
    v = m['variants'][vname]
    need = max(tuple(m['python_min']), DERIVE_PYTHON_MIN)
    if sys.version_info[:2] < need:
        raise PatchError(f'this release needs Python {need[0]}.{need[1]} or newer (you have {sys.version.split()[0]}): '
                         'https://www.python.org/downloads/ (README.md, "What you need")')
    src = resolve_bin(a.disc)
    out_dir = os.path.abspath(a.output or os.path.join(os.path.dirname(os.path.abspath(src)), 'patched'))
    out_bin = os.path.join(out_dir, v['output']['name'] + '.bin')
    if os.path.normcase(os.path.realpath(out_bin)) == os.path.normcase(os.path.realpath(src)):
        raise PatchError('the output would overwrite your original disc: choose another -o folder.')
    log = out_bin[:-4] + '.log'
    try:
        os.makedirs(out_dir, exist_ok=True)
        open(log, 'w').close()
    except OSError as e:
        raise PatchError(f'cannot write in {out_dir} ({e.strerror}): choose another folder with -o FOLDER.')
    if not a.verbose:
        print(f'{release_line(m)}, {vname}: patching {os.path.basename(src)}', flush=True)
    SCREEN = Screen(apply_phases(m, v), log, verbose=a.verbose)
    say(f'{release_line(m)} - {vname}: {v["description"]}')
    say(f'release {m["version"]} ({m["commit"]}), Python {sys.version.split()[0]} on {sys.platform}, '
        f'{os.cpu_count()} CPUs; the log: {log}')
    say('1. Checking the disc (' + ', '.join(b['title'] for b in m['bases'].values()) + ')')
    SCREEN.start('check')
    key, src, _ = identify_base(a.disc, m['bases'])
    say(f'   ok: the clean redump disc of {m["bases"][key]["title"]}.')
    p = read_payload3(read_patch_file(rel, v))
    work = tempfile.mkdtemp(prefix='dwpatch-')
    partial = None
    try:
        mp = m['bases'][key].get('mapping')
        mapping = json.load(open(os.path.join(rel, mp), encoding='utf-8')) if mp else None
        base = BaseDisc(key, src, mapping, tool_root=os.path.join(rel, 'bundle'), work=work,
                        source_discs=getattr(a, 'source_disc', None))
        say('2. Building the modded files from your disc')
        if v['local'].get('builder') != 'derive':
            SCREEN.start('build')
        holes = local_holes3(m, v, base, rel, work, a)
        say(f'   ok: {len(holes)} files, all identical to the release.')
        say('3. Patching')
        SCREEN.start('write')
        expect = v['outputs'].get(key, {}).get('sha1')
        fd, partial = tempfile.mkstemp(prefix='dwpatch-', suffix='.part', dir=out_dir)
        os.close(fd)
        sha, _ = build_disc3(p, base, holes, partial, expect)
        SCREEN.start('result')
        os.replace(partial, out_bin)
        cue = write_cue(out_bin)
        if not expect:
            say(f'   (no whole-disc checksum for {m["bases"][key]["title"]} in this release: every file was checked; '
                f'SHA-1 {sha})')
        else:
            say(f'   ok: SHA-1 {sha}, the release\'s for {m["bases"][key]["title"]}.')
    finally:
        if partial is not None:
            try:
                os.remove(partial)
            except FileNotFoundError:
                pass
        shutil.rmtree(work, ignore_errors=True)
    SCREEN.done()
    say(f'\nDone. Load this file in your emulator:\n  {cue}\n(and keep {os.path.basename(out_bin)} next to it)')
    SCREEN.close(); SCREEN = None
    if not a.verbose:
        print(f'\nDone. Load this file in your emulator:\n  {cue}\n(and keep {os.path.basename(out_bin)} next to it; '
              f'what was done is in {os.path.basename(log)})', flush=True)


def read_patch_file(rel_dir, v):
    path = os.path.join(rel_dir, v['patch'])
    if not os.path.exists(path):
        raise PatchError(f'the patch file {v["patch"]} is missing from {rel_dir}.')
    raw = open(path, 'rb').read()
    if hashlib.sha1(raw).hexdigest() != v['patch_sha1']:
        raise PatchError(f'{v["patch"]} is damaged (its SHA-1 does not match the manifest). Download the release again.')
    return raw


# ---------------------------------------------------------------- format 3: make-release side
def _index(U, step=BLOCK):
    idx = {}
    for o in range(0, len(U) - BLOCK + 1, step):
        blk = U[o:o + BLOCK]
        if blk.count(blk[:1]) == BLOCK: continue
        idx.setdefault(hash(blk), o)
    return idx


def _matches(D, U, idx, s=0, e=None):
    """[(start in D, offset in U, length)] of runs of D[s:e] found in U (32 bytes or more), the rest literal."""
    e = len(D) if e is None else e
    out = []; p = lit = s
    while p + BLOCK <= e:
        o = idx.get(hash(D[p:p + BLOCK]))
        if o is None or U[o:o + BLOCK] != D[p:p + BLOCK]:
            p += 1; continue
        L = BLOCK
        while p + L + 256 <= e and o + L + 256 <= len(U) and U[o + L:o + L + 256] == D[p + L:p + L + 256]: L += 256
        while p + L < e and o + L < len(U) and U[o + L] == D[p + L]: L += 1
        while p > lit and o > 0 and U[o - 1] == D[p - 1]: p -= 1; o -= 1; L += 1
        out.append((p, o, L)); p += L; lit = p
    return out


class Pool:
    """Files concatenated for the delta: matches are cut at file boundaries."""
    def __init__(self, named):
        import bisect
        self._bisect = bisect.bisect_right
        self.names = [n for n, _ in named]; self.starts = []; parts = []; o = 0
        for _, b in named:
            self.starts.append(o); parts.append(b); o += len(b)
        self.U = b''.join(parts); self.idx = _index(self.U)

    def runs(self, D, s=0, e=None):
        """[(start in D, file index, offset in file, length)]"""
        out = []
        for p, o, L in _matches(D, self.U, self.idx, s, e):
            while L:
                i = self._bisect(self.starts, o) - 1
                end = self.starts[i + 1] if i + 1 < len(self.starts) else len(self.U)
                k = min(L, end - o); out.append((p, i, o - self.starts[i], k)); p += k; o += k; L -= k
        return out


class Encoder3:
    def __init__(self, usa, mappings, bases):
        """usa: isowriter.Image of the USA disc; mappings {key: mapping json} of the other bases; bases {key: Image}
        (their own code files for the reloc tables)."""
        self.usa, self.mappings, self.bases = usa, mappings, bases
        paths = sorted(usa.files) + ['license_data.dat']
        hows = {q: {m['files'].get(q, {}).get('how', 'missing') for m in mappings.values()} for q in paths}
        self.universal = [q for q in paths if hows[q] <= set(GOOD)]
        self.code_paths = [q for q in paths if 'needs-usa' in hows[q] and hows[q] <= set(GOOD) | {'needs-usa'}]
        self.whole = {q for q in paths if hows[q] <= set(WHOLE)}
        self.sources = []; self.src_id = {}
        self._data = {}
        say(f'  sources: {len(self.universal)} files every base has as the USA ones, {len(self.code_paths)} code files '
            f'copied with each base\'s offsets, {len(self.whole) - len(self.universal)} the base\'s own (movies, '
            'localized images)')
        self.pool = Pool([(q, self.data(q)) for q in self.universal + self.code_paths])
        self.by_sha = {}
        for q in sorted(self.whole):
            self.by_sha.setdefault(hashlib.sha1(self.data(q)).hexdigest(), q)
        self.code = []                                   # [usa src id, offset, length]
        self.blob = bytearray()

    def data(self, q):
        if q not in self._data: self._data[q] = self.usa.license() if q == 'license_data.dat' else self.usa.read(q)
        return self._data[q]

    def sid(self, q):
        if q not in self.src_id: self.src_id[q] = len(self.sources); self.sources.append(q)
        return self.src_id[q]

    def lit(self, b):
        o = len(self.blob); self.blob += b; return ['l', o, len(b)]

    def encode(self, path, D, hole=None, code=True):
        """The operations of one output file (and its byte classes for the audit). code=False (a derived file): no copy
        from the USA executable, overlays or scripts (rule: a derived file is made from the player's files only; what
        such a copy would give is literal, and a literal byte of a derived file makes it a hole)."""
        if hole is not None: return [['h', hole, 0, len(D)]]
        h = hashlib.sha1(D).hexdigest()
        if path in self.whole and hashlib.sha1(self.data(path)).hexdigest() == h: return [['s', self.sid(path)]]
        if h in self.by_sha: return [['s', self.sid(self.by_sha[h])]]
        ops = []; pos = 0; ncode = len(self.universal)
        for p, i, o, n in self.pool.runs(D):
            if i >= ncode and not code: continue
            if p > pos: ops.append(self.lit(D[pos:p]))
            q = self.pool.names[i]
            if i >= ncode:
                self.code.append([self.sid(q), o, n]); ops.append(['r', len(self.code) - 1])
            else:
                ops.append(['c', self.sid(q), o, n])
            pos = p + n
        if pos < len(D): ops.append(self.lit(D[pos:]))
        return ops


def table_offset(exe, img_files, map_path=None, offset=None):
    """FILE_OFFSET_TABLE's offset in the executable: the build's facts (tools/derive facts: file_offset_table), else
    from the linker map; checked against the image's LBAs."""
    iw = _iw()
    t = offset
    if t is None:
        if not map_path or not os.path.exists(map_path):
            raise SystemExit(f'the executable\'s linker map is needed (FILE_OFFSET_TABLE): {map_path} (variant flag map=PATH)')
        for line in open(map_path):
            mm = __import__('re').match(r'\s+(0x[0-9a-f]+)\s+FILE_OFFSET_TABLE\s*$', line)
            if mm: t = int(mm.group(1), 16) - 0x80090000
        if t is None: raise SystemExit(f'{map_path}: no FILE_OFFSET_TABLE')
    where = {q.split('/')[-1]: (lba, n) for q, (lba, n, _) in img_files.items()}
    where['PSX.EXE'] = where['SLUS_010.32']
    ents = iw.file_table_entries(exe, t, names=where)
    wrong = [nm for _, sec, size, nm in ents if nm in where and (sec, size) != where[nm]]
    if not ents or wrong: raise SystemExit(f'{map_path}: the table it points to does not match the image ({wrong[:5]})')
    return dict(file='SLUS_010.32', offset=t, entries=len(ents))


def audit_ops(ops, D, p):
    """Byte counts of one file's operations: moved (whole files of the player's disc), copied, code (copied from each
    base's executable/overlays), literal, of it not zero, hole."""
    r = dict(moved=0, copied=0, code=0, reused=0, literal=0, literal_nonzero=0, hole=0)
    for op in ops:
        t = op[0]
        if t == 's': r['moved'] += len(D)
        elif t == 'c': r['copied'] += op[3]
        elif t == 'o': r['reused'] += op[3]
        elif t == 'r': r['code'] += p['code'][op[1]][2]
        elif t == 'b': r['code'] += op[3]
        elif t == 'l':
            seg = p['blob'][op[1]:op[1] + op[2]]; r['literal'] += len(seg); r['literal_nonzero'] += len(seg) - seg.count(0)
        else: r['hole'] += op[3]
    return r


def authored3(path, extra=()):
    return path in ('SLUS_010.32', 'SYSTEM.CNF') or path.endswith('_REL.BIN') or path in extra


def cmd_make_release(a):
    # Validate before deleting/replacing an existing output folder or invoking a build.
    if a.format != FORMAT or a.holes != 'derive' or a.recipe != 'everything':
        raise PatchError('everything releases require format 3 and the derive recipe everything.')
    if len(a.variant) != 1 or not a.variant[0].startswith('everything='):
        raise PatchError('make-release takes exactly one --variant everything=BIN.')
    target, *flags = a.variant[0].split('=', 1)[1].split(',')
    if not target or any(f.split('=', 1)[0] not in ('map', 'manifest') or '=' not in f for f in flags):
        raise PatchError('everything=BIN accepts only ,map=PATH and ,manifest=PATH.')
    if any('=' not in source or not source.split('=', 1)[1] for source in (a.source_disc or [])):
        raise PatchError('--source-disc requires GAME=IMAGE for each source game.')
    games = [s.split('=', 1)[0] for s in (a.source_disc or [])]
    if len(games) != 3 or set(games) != {'dcb', 'dw2', 'dw2003'}:
        raise PatchError('the everything release needs --source-disc for dcb, dw2 and dw2003, once each.')
    save_check(a)
    return cmd_make_release3(a)


def release_notices(out):
    """Retain project and embedded-font notices beside the release's executable patch."""
    for name in ('LICENSE', 'THIRD-PARTY.md'):
        shutil.copyfile(os.path.join(REPO, name), os.path.join(out, name))
    source = os.path.join(REPO, 'tools', 'font', 'japanese-license')
    shutil.copytree(source, os.path.join(out, 'licenses', 'japanese-font'), dirs_exist_ok=True)
    shutil.copyfile(os.path.join(REPO, 'tools', 'image-license.txt'),
                    os.path.join(out, 'licenses', 'raster.txt'))


def cmd_make_release3(a):
    """Format 3 (see the section above): one package for the USA disc and every --base given."""
    iw = _iw()
    out = os.path.abspath(a.output)
    if os.path.exists(out):
        if not any(os.path.exists(os.path.join(out, f)) for f in ('manifest.json', 'audit.txt')) and os.listdir(out):
            raise SystemExit(f'{out} exists and is not a release folder')
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, 'bases'))
    t_check = time.time()
    h = file_hashes(a.original, 'hashing the original')
    t_check = time.time() - t_check
    if h['sha1'] != ORIGINAL['sha1']: raise SystemExit(f'{a.original} is not the redump disc ({h["sha1"]})')
    usa = iw.Image(a.original)
    commit = git_commit()
    bases_img, mappings, bases_info = {}, {}, {'us': dict(BASES['us'], mapping=None)}
    base_paths = {'us': a.original}
    for spec in a.base:
        key, bpath = spec.split('=', 1)
        if key not in BASES or key == 'us': raise SystemExit(f'--base {key}: one of {", ".join(k for k in BASES if k != "us")}')
        k2, bpath, _ = identify_base(bpath, {key: BASES[key]})
        mp = os.path.join(REPO, 'mods', 'base-discs', f'dw1-{key}.json')
        mappings[key] = json.load(open(mp)); bases_img[key] = iw.Image(bpath); base_paths[key] = bpath
        shutil.copyfile(mp, os.path.join(out, 'bases', os.path.basename(mp)))
        bases_info[key] = dict(BASES[key], mapping=f'bases/{os.path.basename(mp)}')
        if mappings[key].get('localize_tool'):
            say(f'  {key}: its localize files need {mappings[key]["localize_tool"]} at apply time (bundled when present)')
    work = tempfile.mkdtemp(prefix='dwrelease-', dir=a.work)
    try:
        import datacopy
        data_sources = dict(s.split('=', 1) for s in getattr(a, 'source_disc', None) or [])
        mapping_copies = datacopy.copy_mappings(mappings, base_paths, data_sources, work)
        for key, mp in mappings.items():
            with open(os.path.join(out, 'bases', f'dw1-{key}.json'), 'w') as f:
                json.dump(mp, f, indent=2)
        version, date = release_version(a)
        m = dict(format=3, title=a.title, version=version, date=date, commit=commit,
                 bases=bases_info, default=a.variant[0].split('=')[0], extract=[], python_min=[3, 8], variants={})
        say('bundle (tools/derive)')
        t0 = time.time()
        first = a.variant[0].split('=', 1)[1].split(',')[0]
        facts = os.path.join(os.path.dirname(os.path.abspath(first)), os.path.basename(first)[:-4], 'derived',
                             'exe-facts.json')
        bundle, extract, cand = make_bundle_derive(usa, work, out, a.recipe, facts,
                                                  source_discs=getattr(a, 'source_disc', None))
        if getattr(a, 'source_disc', None):
            m['source_discs'] = sorted({s.split('=', 1)[0] for s in a.source_disc})
        m['extract'] = extract
        for key, mp in mappings.items():
            bad = [q for q in extract if mp['files'].get(q, {}).get('how') not in WHOLE]
            if bad: raise SystemExit(f'tools/derive reads {bad[:5]} of the USA disc, which {key} does not have')
        say(f'  ({time.time() - t0:.0f} s) verify: the bundle alone, with only those files of the USA disc')
        ver = os.path.join(work, 'verify')
        vb = os.path.join(out, 'bundle')
        t1 = time.time()
        derive_tree(ver, {os.path.relpath(os.path.join(dp, f), vb).replace(os.sep, '/'): os.path.join(dp, f)
                          for dp, _, fs in os.walk(vb) for f in fs}, [], usa.read)
        t2 = time.time()
        derive_tree(ver, {}, extract, usa.read)
        t3 = time.time()
        vman, vout = derive_run(ver, a.recipe, os.path.join(ver, 'exe-facts.json'), log=os.path.join(work, 'derive-verify.log'),
                                 source_discs=getattr(a, 'source_disc', None))
        t4 = time.time()
        # apply's progress bar: the time of each of its phases here (the same work as the player's: the bundle
        # copied, the extract files written, derive with --jobs, in the order it ran the steps; write: below)
        apply_t = dict(check=round(t_check, 1), tools=round(t2 - t1, 1), read=round(t3 - t2, 1),
                       steps=[[n, st['seconds']] for n, st in vman['steps'].items()], holes=1, write=14, result=0.1)
        local_base = derive_files(vman, vout)
        diff = [d for d in set(cand) | set(local_base) if d not in cand or d not in local_base or
                hashlib.sha1(open(cand[d], 'rb').read()).digest() != hashlib.sha1(open(local_base[d], 'rb').read()).digest()]
        if diff: raise SystemExit(f'the bundle alone builds other files than the clean tree: {sorted(diff)[:5]}')
        m['python_min'] = max(python_min([os.path.join(out, 'bundle', f) for f in bundle]), list(DERIVE_PYTHON_MIN))
        m['python_packages'] = []  # derive uses only the Python standard library
        m['timings'] = dict(bundle_and_verify=round(time.time() - t0), apply=apply_t)
        audit_txt = [f'{a.title} {version} ({commit}), format 3: what each changed file of each patched disc is made '
                     'of, in bytes.', 'moved: whole files of the player\'s disc (their sectors moved); copied: bytes of '
                     'files every base disc has as the USA ones; code: output rebuilt from the player\'s program '
                     'files using copies, address fixups or binary deltas; '
                     'reused: bytes of an earlier file of the same patched disc (translated overlay copies); '
                     'literal: bytes inside the patch (lit!=0: of them, not zero); '
                     'hole: built on the player\'s machine. origin: authored (program or own sources) or derived (must be all '
                     'holes, zero literal bytes). The file system records (directories, path tables) are not in the '
                     'patch: the patcher writes them from the layout.', '']
        errors = []
        gate_plans = {}
        for spec in a.variant:
            name, rest = spec.split('=', 1)
            target, *flags = rest.split(',')
            opt = dict(f.split('=', 1) for f in flags if '=' in f)
            local = dict(builder='derive', recipe=a.recipe)
            mp_ = opt.get('manifest') or os.path.join(os.path.dirname(os.path.abspath(target)),
                                                      os.path.basename(target)[:-4], 'derived', 'manifest.json')
            dman = json.load(open(mp_))
            aut = tuple(dman.get('plan', {}).get('authored', ()))
            gate_plans[name] = dman['plan']
            say(f'variant {name}: {target} {flags}')
            T = iw.Image(target)
            layout = iw.layout_from_image(T)
            lay = iw.Layout(layout)
            mapf = opt.get('map') or os.path.join(os.path.dirname(os.path.abspath(target)),
                                                  os.path.basename(target)[:-4], 'exe', 'SLUS_010.32.elf.map')
            exe_t = T.read('SLUS_010.32')
            fo = None
            ff = os.path.join(os.path.dirname(os.path.abspath(target)), os.path.basename(target)[:-4], 'derived',
                              'exe-facts.json')
            fo = json.load(open(ff)).get('file_offset_table') if os.path.exists(ff) else None
            table = table_offset(exe_t, T.files, mapf, fo)
            enc = Encoder3(usa, mappings, bases_img)
            files = {}; datas = {}; holes = []; hole_bytes = {}
            built = local_base
            lost = [q for q in dman['files'] if q not in built]
            if lost: raise SystemExit(f'{name}: the bundle\'s build did not make {lost[:5]}')
            for q in lay.files():
                D = T.read(q); datas[q] = D; hid = None
                if q in built:
                    if hashlib.sha1(open(built[q], 'rb').read()).digest() != hashlib.sha1(D).digest():
                        errors.append(f'{name}: {q} built locally differs from the build')
                    hid = len(holes)
                ops = enc.encode(q, D, hid, code=authored3(q, aut))
                if hid is not None:
                    holes.append(dict(id=hid, file=q, size=len(D), sha1=hashlib.sha1(D).hexdigest())); hole_bytes[hid] = D
                files[q] = ops
            lic = T.license()
            files['\0license'] = enc.encode('license_data.dat', lic)
            say(f'  {len(files) - 1} files, {sum(1 for o in files.values() if o[0][0] == "s")} whole from the player\'s '
                f'disc, {len(holes)} built locally, {len(enc.code)} code copies')
            import reloc as R
            eligible = {q for q in files if q in datas and authored3(q, aut) and q != table['file'] and
                        files[q][0][0] not in 'sh'}
            reused = R.reuse_outputs(enc, files, datas, eligible, {q for q in datas if authored3(q, aut)}, Pool)
            reloc, fix, lost = R.relocate(enc, files, Pool, say)
            enc.lost = R.compact(enc, files)
            lost = sum(v for q, v in enc.lost.items() if q != '\0license')
            say(f'  code copies: {len(enc.code)} after relocation, {lost} bytes literal (on the USA disc\'s code but not '
                f'found on every base\'s); {reused} bytes copied from earlier files of the patched disc')
            lic_ops = files.pop('\0license')
            p = dict(layout=layout, sources=enc.sources, files=files, license=lic_ops, code=enc.code, reloc=reloc,
                     fix=fix, sha1={q: hashlib.sha1(datas[q]).hexdigest() for q in files if files[q][0][0] != 's'},
                     table=table)
            p['blob'] = bytes(enc.blob)
            import fontcopy
            import fontgen
            font_copies = dict(reason='Compact Latin tables are generated in program deltas from each player font.')
            for source in ('tools/fontgen.py', 'tools/font/b.txt', 'tools/font/extra.txt',
                           'tools/font/original-metrics.json', 'tools/font/japanese.txt',
                           'tools/localize/executable/bank.py', 'tools/localize/executable/us-format-codes.json',
                           'tools/patcher/sdk-messages.json',
                           *(f'text/{lang}/names.json' for lang in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'))):
                dest = os.path.join(out, 'bundle', *source.split('/'))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copyfile(os.path.join(REPO, source), dest)
                if source not in bundle: bundle.append(source)
            data_copies = datacopy.copy_payload(p, base_paths, data_sources, work,
                                                 dict(datas, **{'license_data.dat': lic}),
                                                 os.path.splitext(os.path.abspath(target))[0])
            boot_copies = datacopy.copy_boot_config(p, base_paths, datas)
            enc.sources, enc.code = p['sources'], p['code']
            say(f'  data copies: {data_copies["copied"]} literal bytes copied, '
                f'{len(p["blob"])} remain after BOOT metadata generation (proof: {name}-data-copies.json)')
            with open(os.path.join(out, f'{name}-data-copies.json'), 'w') as f:
                json.dump(dict(payload=data_copies, mappings=mapping_copies, fonts=font_copies, boot=boot_copies), f, indent=2)
            import codecopy
            build_dir = os.path.join(os.path.dirname(os.path.abspath(target)), os.path.basename(target)[:-4])
            delta_report = codecopy.copy_files(p, build_dir, datas, dict(us=usa, **bases_img), say,
                                               plan=dman.get('plan') if dman is not None else None)
            json.dump(delta_report, open(os.path.join(out, name + '-binary-deltas.json'), 'w'), indent=2)
            audit_txt.append(f'binary deltas: {len(delta_report["files"])} files; raw extras per base: ' +
                             ', '.join(f'{key}={counts["extra"]}' for key, counts in delta_report['bases'].items()))
            enc.blob = bytearray(p.pop('blob'))
            j = json.dumps(p, separators=(',', ':')).encode()
            payload = b'DWP3' + struct.pack('<I', len(j)) + j + bytes(enc.blob)
            blob = lzma.compress(payload, preset=9 | lzma.PRESET_EXTREME)
            fn = f'{name}.dwp'; open(os.path.join(out, fn), 'wb').write(blob)
            th = file_hashes(target, 'hashing the target')
            p3 = read_payload3(blob)
            outputs = {}
            for key in base_paths:
                say(f'  applying to {BASES[key]["title"]}')
                bd = BaseDisc(key, base_paths[key], mappings.get(key), tool_root=REPO, work=os.path.join(work, key),
                              source_discs=getattr(a, 'source_disc', None))
                os.makedirs(os.path.join(work, key), exist_ok=True)
                bd.trace = os.path.join(work, key, 'trace.txt')
                ob = os.path.join(work, f'{name}-{key}.bin')
                t0 = time.time()
                hb = hole_bytes
                if regional_derive(mappings.get(key), m['extract']):
                    # rule: a base whose files the build reads are not the USA bytes (the Japanese one's images, made
                    # in our words, or Europe's titles) gives other derived files: record their SHA-1 per base
                    say(f'    tools/derive on {key}\'s own files (its regional artwork)')
                    got = derive_holes(out, m, dict(local=local), bd, os.path.join(work, key, 'derive'),
                                       source_discs=getattr(a, 'source_disc', None))
                    hb = dict(hole_bytes); nb = 0
                    for hh in holes:
                        b = open(got[hh['file']], 'rb').read()
                        if b != hole_bytes[hh['id']]:
                            hh.setdefault('sha1_by_base', {})[key] = hashlib.sha1(b).hexdigest(); hb[hh['id']] = b; nb += 1
                    say(f'    {nb} of {len(holes)} derived files differ on {key}')
                tw = time.time()
                sha, _ = build_disc3(p3, bd, hb, ob, th['sha1'] if key == 'us' else None)
                if key == 'us' and m.get('timings', {}).get('apply'):
                    m['timings']['apply']['write'] = round(time.time() - tw, 1)
                outputs[key] = dict(sha1=sha, size=os.path.getsize(ob))
                say(f'    {sha} ({time.time() - t0:.0f} s)')
                if os.path.exists(bd.trace):                 # the localize tool and what it reads go into bundle/
                    for line in open(bd.trace):
                        q = line.strip()
                        if not q.startswith(REPO + os.sep) or not os.path.isfile(q) or '__pycache__' in q: continue
                        r = os.path.relpath(q, REPO).replace(os.sep, '/')
                        if r.split('/')[0] not in ('tools', 'content'): continue
                        os.makedirs(os.path.dirname(os.path.join(out, 'bundle', r)), exist_ok=True)
                        shutil.copyfile(q, os.path.join(out, 'bundle', r))
                        if r not in bundle: bundle.append(r)
                if a.keep_outputs:
                    os.makedirs(a.keep_outputs, exist_ok=True)
                    shutil.move(ob, os.path.join(a.keep_outputs, f'{name}-{key}.bin'))
                else:
                    os.remove(ob)
            m['variants'][name] = dict(description=DESCRIPTIONS.get(name, name), patch=fn, patch_size=len(blob),
                                       patch_sha1=hashlib.sha1(blob).hexdigest(), local=local,
                                       output=dict(name=f'{a.title} ({name})'), outputs=outputs,
                                       holes=holes)
            say(f'  {fn}: {len(payload)} bytes, {len(blob)} compressed')
            audit_txt.append(f'== {name} ({os.path.basename(target)} -> {fn}, {len(blob)} bytes; bases: {", ".join(base_paths)})')
            for key, counts in enc.reloc_stats.items():
                audit_txt.append(f'code sources on {key}: {counts["absent"]} bytes absent, '
                                 f'{counts["fixed"]} address bytes fixed (after output reuse, before shared-file copies)')
            audit_txt.append(f'{"file":30} {"origin":8} {"moved":>10} {"copied":>8} {"code":>8} {"reused":>8} '
                             f'{"literal":>8} {"lit!=0":>8} {"hole":>8} {"lit_usa":>8}')
            tot = {}
            p3['blob'] = bytes(enc.blob)
            rows = sorted(files, key=lambda q: (not authored3(q, aut), q))
            for q in rows:
                r = audit_ops(files[q], datas[q], p3); org = 'authored' if authored3(q, aut) else 'derived'
                r['lit_usa'] = enc.lost.get(q, 0)
                t = tot.setdefault(org, dict.fromkeys(r, 0))
                for k in t: t[k] += r[k]
                if org == 'derived' and r['literal_nonzero']:
                    errors.append(f'{name}: {q} (derived) has {r["literal_nonzero"]} literal bytes')
                if r['moved'] == 0:
                    audit_txt.append(f'{q:30} {org:8} {r["moved"]:10} {r["copied"]:8} {r["code"]:8} {r["reused"]:8} '
                                     f'{r["literal"]:8} {r["literal_nonzero"]:8} {r["hole"]:8} {r["lit_usa"]:8}')
            for org, t in sorted(tot.items()):
                audit_txt.append(f'{"total " + org:30} {"":8} {t["moved"]:10} {t["copied"]:8} {t["code"]:8} '
                                 f'{t["reused"]:8} {t["literal"]:8} {t["literal_nonzero"]:8} {t["hole"]:8} '
                                 f'{t["lit_usa"]:8}')
            audit_txt.append('(files taken whole from the player\'s disc are not listed; lit_usa: pre-data-pass literal bytes that '
                             'the USA disc\'s executable/overlays/scripts hold but some base\'s do not, so they could '
                             f'not be copied by relocation: {lost} in all, before the separate data-copy pass)')
            audit_txt.append('outputs: ' + ', '.join(f'{k} {v["sha1"]}' for k, v in outputs.items()) + '\n')
        if bundle:
            audit_txt.append(f'bundle/ ({len(bundle)} source/configuration files): ' + ', '.join(bundle))
            audit_txt.append(f'\nfiles the patcher extracts from the player\'s disc ({len(m["extract"])}): '
                             + ', '.join(m['extract']))
        open(os.path.join(out, 'audit.txt'), 'w').write('\n'.join(audit_txt) + '\n')
        if errors:
            raise SystemExit('make-release refused (see audit.txt):\n  ' + '\n  '.join(errors))
        json.dump(m, open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8'), indent=2)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    copy_release_frontend(out)
    import literal_gate
    build_dirs = {spec.split('=', 1)[0]: os.path.splitext(os.path.abspath(
        spec.split('=', 1)[1].split(',')[0]))[0] for spec in a.variant}
    literal_gate.check_release(out, m, base_paths, getattr(a, 'source_disc', None), build_dirs, plans=gate_plans)
    say(f'release in {out}')


def copy_release_frontend(out):
    """Add the standalone player entry point, instructions and project notices."""
    shutil.copyfile(os.path.abspath(__file__), os.path.join(out, 'dwpatch.py'))
    shutil.copyfile(os.path.join(REPO, 'tools', 'isowriter.py'), os.path.join(out, 'isowriter.py'))
    shutil.copyfile(os.path.join(REPO, 'tools', 'patcher', 'fontcopy.py'), os.path.join(out, 'fontcopy.py'))
    readme = os.path.join(REPO, 'docs', 'release', 'README-players.md')
    if os.path.exists(readme):
        with open(readme, encoding='utf-8') as source:
            text = source.read().replace('(../data/source-releases.md)', '(source-releases.md)')
        with open(os.path.join(out, 'README.md'), 'w', encoding='utf-8') as target:
            target.write(text)
    shutil.copyfile(os.path.join(REPO, 'docs', 'data', 'source-releases.md'),
                    os.path.join(out, 'source-releases.md'))
    release_notices(out)


# ---------------------------------------------------------------- command line
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 1 and os.path.isfile(argv[0]):          # a disc dropped onto the script
        argv = ['apply', argv[0]]
    ap = argparse.ArgumentParser(description='Digimon World mod patcher (bring your own disc).')
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('apply', help='patch your disc')
    p.add_argument('disc', help='your Digimon World .cue or .bin')
    p.add_argument('-o', '--output', help='folder for the patched disc (default: "patched" next to your disc)')
    p.add_argument('--variant', choices=('everything',), help='everything (the default)')
    p.add_argument('--source-disc', action='append', metavar='GAME=IMAGE',
                   help='source image for model imports: dcb, dw2, dw2003 (repeat for each game)')
    p.add_argument('--release', help='the release folder (default: this script\'s folder)')
    p.add_argument('-v', '--verbose', action='store_true', help='print every detail instead of the progress bar (they '
                   'always go to the log file next to the patched disc)')
    p = sub.add_parser('check', help='check a disc only'); p.add_argument('disc'); p.add_argument('--release')
    p = sub.add_parser('info', help='what the release contains'); p.add_argument('--release')
    p = sub.add_parser('make-release', help='(developers) build a release')
    p.add_argument('--original', required=True); p.add_argument('--variant', action='append', required=True,
                                                               help='everything=BIN[,map=PATH][,manifest=PATH]')
    p.add_argument('-o', '--output', required=True); p.add_argument('--title', default='Digimon World Mod')
    p.add_argument('--version', help='the release\'s version (default: tools/version.py, the tag vX.Y.Z on HEAD or a '
                   'development version; the date is always the tag\'s or the commit\'s)')
    p.add_argument('--work', help='folder for temporary files (about 700 MB)')
    p.add_argument('--source-disc', action='append', metavar='GAME=IMAGE',
                   help='source image for model imports: dcb, dw2, dw2003 (repeat for each game)')
    p.add_argument('--format', type=int, choices=(3,), default=FORMAT)
    p.add_argument('--base', action='append', default=[], help='(format 3) REL=BIN: another base disc the package '
                   'serves (eu fr de es it jp1): its copy table and output checksum are made from it')
    p.add_argument('--recipe', choices=('everything',), default='everything', help='(format 3, --holes derive) the tools/derive recipe the '
                   'variant was built from (tools/derive/recipes/NAME.json)')
    p.add_argument('--holes', choices=('derive',), default='derive',
                   help='build derived files from the four player discs with tools/derive')
    p.add_argument('--keep-outputs', help='keep the per-base patched discs in this folder')
    p.add_argument('--save-check-emu', action='store_true', help='also load every published release\'s save on the '
                   'first variant\'s disc in the emulator (tools/dev/saves/releases.py emu; the file check always runs)')
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help(); return 2
    try:
        {'apply': cmd_apply, 'check': cmd_check, 'info': cmd_info, 'make-release': cmd_make_release}[a.cmd](a)
    except PatchError as e:
        return _stop(f'ERROR: {e}')
    except KeyboardInterrupt:
        return _stop('stopped.')
    except Exception as e:
        if SCREEN is None: raise
        import traceback
        SCREEN.write_raw(traceback.format_exc())
        if isinstance(e, OSError):                     # (a full disk, a folder that cannot be written)
            return _stop(f'ERROR: {e.strerror or e}' + (f': {e.filename}' if e.filename else ''))
        return _stop('ERROR: the patcher failed unexpectedly (a bug: please send us the log).')
    return 0


def _stop(msg):
    """apply's end on an error: the bar's line closed, the message, and where the log is."""
    global SCREEN
    if SCREEN is None:
        say(f'\n{msg}'); return 1
    sc, SCREEN = SCREEN, None
    sc.done(ok=False)
    sc.log(f'\n{msg}')
    sc.close()
    if not sc.verbose:
        print(f'\n{msg}', flush=True)
    print(f'\nWhat was done, step by step, is in this file:\n  {sc.log_path}', flush=True)
    return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):              # (a piped Windows stream is not UTF-8: errors must still print)
        stream.reconfigure(errors='replace')
    code = main()
    if os.name == 'nt' and len(sys.argv) == 2 and os.path.isfile(sys.argv[1]):
        input('Press Enter to close.')                      # a disc dropped onto the script: keep the window open
    sys.exit(code)
