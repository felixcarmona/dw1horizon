"""The executable's and overlays' text of a disc, by the decompilation's text keys (docs/reference/text-sources.md 2.9).

The key list is decomp/text/<dir>/<file>.yaml (the decompilation's own key -> text layer, compiled by
decomp/tools/gen_text.py): every string entry (`strings:` blocks, single blocks) and every row of a table. Keys:

    <dir>.<SYMBOL>          a named string: main.STR_MOVE_NAME_SPIT_FIRE is not a table row, main.STR_YOUR_NAME,
                            btl.BTL_STR_DROPPED, kar.KAR_STR_PENGUINMON ...
    <dir>.<BLOCK>.<i>       row i of a table: main.MOVE_NAMES.12 (technique 12), main.ITEM_NAMES.38 (item 38),
                            main.ITEM_DESCS.38, main.DIGIMON_NAMES.1, main.ITEM_MENU_LABELS.0, main.STAT_LABELS.5
    <dir>.<BLOCK>           a single entry (main.STR_IS_SICK)

Only the keys and the addresses come from the decompilation; the text is read from the player's disc: a named string
at its symbol's address in config/<version>/symbols*.txt (us, jp, jp_rev1), a table through its pointers (MOVE_NAMES,
ITEM_DESCS) or its records (ITEM_PARA names, DIGIMON_DATA names...). es-fan (the jp executable patched, no symbols of
its own) keeps the tables where jp has them and repoints the strings: a table is read through its pointers, and a named
string through the code and data that refer to it in jp (the same instructions in es-fan give its new address)."""
import glob, os, re, struct, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DECOMP = os.path.join(ROOT, 'decomp')
# embedded tables: the strings live inside records (the C writes them with a macro); table symbol, stride, size
EMBEDDED = {'ITEM_NAMES': ('ITEM_PARA', 0x20, 20), 'DIGIMON_NAMES': ('DIGIMON_DATA', 0x34, 20),
            'ITEM_MENU_LABELS': ('ITEM_MENU_LABELS', 8, 8), 'STAT_LABELS': ('MAIN_D_80124C0C', 12, 12)}


def load_yaml(path):
    try:
        import yaml
        return yaml.load(open(path, encoding='utf-8'), Loader=yaml.BaseLoader)
    except ImportError:
        raise SystemExit('the executable text needs PyYAML (pip install pyyaml, or the project venv)')


LANG = {'us': 'en_us', 'jp': 'ja', 'jp_rev1': 'ja'}


def entry_text(entry, release):
    """The text gen_text.py would give an entry for a release (only to tell which strings it merged into one)."""
    lang = LANG.get(release, 'ja')
    for k in (f'{lang}@{release}', lang):
        if isinstance(entry, dict) and k in entry: return None if entry[k] == 'NULL' else entry[k]
    return None


def inventory(release=None):
    """[(key, dir, kind, ref, text)] in the yaml order: kind 'sym' (ref = symbol) or 'row' (ref = (block, index)). With a
    release, a named string that gen_text.py merged into an earlier identical one of the same file (`#define A B`: no
    symbol of its own) refers to that one's symbol, and `text` is the decompilation's text for that release: used only
    to find a string that has no symbol, never written out (the text written is the disc's)."""
    out = []
    for f in sorted(glob.glob(os.path.join(DECOMP, 'text', '*', '*.yaml'))):
        d = os.path.basename(os.path.dirname(f)); first = {}
        def sym(name, entry):
            t = entry_text(entry, release) if release else None
            if t is None: return (name if not release else None), None     # no text in this release: not on its disc
            return first.setdefault(t, name), t
        for block, body in load_yaml(f).items():
            if 'strings' in body:
                out += [(f'{d}.{n}', d, 'sym') + sym(n, e) for n, e in body['strings'].items()]
            elif 'entries' not in body:
                out.append((f'{d}.{block}', d, 'sym') + sym(block, body))
            else:
                for i, e in enumerate(body['entries']):
                    if isinstance(e, dict) and e.get('name') and block not in EMBEDDED: sym(e['name'], e)
                out += [(f'{d}.{block}.{i}', d, 'row', (block, i), None) for i in range(len(body['entries']))]
    return out


class Version:
    """The symbols and binaries of one decomp version (us, jp, jp_rev1) of a disc."""
    def __init__(self, ver, read):
        self.ver, self.read = ver, read
        cfg = os.path.join(DECOMP, 'config', ver)
        self.sym = {}                                   # symbol -> (address, file name of its binary)
        self.bins = {}                                  # file name -> (bytes, vram of offset 0)
        main = None
        for y in glob.glob(os.path.join(cfg, '*.yaml')):
            t = open(y, encoding='utf-8').read()
            m = re.search(r'target_path:\s*\S*/([^/\s]+)', t)
            seg = re.search(r'start:\s*(0x[0-9A-Fa-f]+|\d+)\s*\n\s*vram:\s*(0x[0-9A-Fa-f]+)', t)
            if not m or not seg: continue
            fname, base = m.group(1), int(seg.group(2), 16) - int(seg.group(1), 0)
            name = os.path.splitext(os.path.basename(y))[0]
            self.bins[name] = (fname, base)
            if name == 'main': main = fname
        for sf in sorted(glob.glob(os.path.join(cfg, 'symbols*.txt'))):
            ov = re.match(r'symbols_?(\w*)\.txt$', os.path.basename(sf)).group(1) or 'main'
            for line in open(sf, encoding='utf-8'):
                m = re.match(r'\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+)', line)
                if m: self.sym.setdefault(m.group(1), (int(m.group(2), 16), ov if ov in self.bins else 'main'))
        self.cache = {}

    def blob(self, ov):
        if ov not in self.cache:
            fname, base = self.bins[ov]
            b = self.read(fname)
            self.cache[ov] = (b, base)
        return self.cache[ov]

    def at(self, ov, addr, n=None):
        """Bytes at an address of a binary: n bytes, or up to the NUL."""
        b, base = self.blob(ov)
        if b is None: return None
        p = addr - base
        if not 0 <= p < len(b): return None
        if n is not None: return b[p:p + n]
        e = b.index(0, p) if 0 in b[p:] else len(b)
        return b[p:e]

    def find(self, ov, text):
        """The address of a NUL-terminated string with this text (cp932, as gen_text.py writes it), or None."""
        b, base = self.blob(ov)
        if b is None or text is None: return None
        try:
            pat = text.encode('cp932') + b'\0'
        except UnicodeEncodeError:
            return None
        p = b.find(pat)
        while p > 0 and b[p - 1] != 0: p = b.find(pat, p + 1)           # a whole string, not the tail of another
        return None if p < 0 else base + p


def decoder(disc):
    table = {}
    if disc['id'] == 'es-fan':
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        from dws.text import esglyphs
        table = esglyphs.load()
    if disc['id'] == 'us':                         # the US font draws 81A2 as × and 817E as △ (tools/dws/bytecode/__main__.py, "Text")
        table = {0x81A2: '×', 0x817E: '△'}
    ja = disc['lang'] == 'ja'

    def dec(b):
        out = []; p = 0
        while p < len(b):
            c = b[p]
            if c >= 0x80 and p + 1 < len(b):
                code = (c << 8) | b[p + 1]; p += 2
                if code in table: out.append(table[code]); continue
                try:
                    ch = bytes([code >> 8, code & 0xFF]).decode('cp932')
                except UnicodeDecodeError:
                    out.append('{sjis %04x}' % code); continue
                out.append(ch if ja else unicodedata.normalize('NFKC', ch)); continue
            out.append(chr(c) if 0x20 <= c < 0x7F else '{raw %02x}' % c); p += 1
        return ''.join(out)
    return dec


# ------------------------------------------------------------------------------------------------ es-fan: follow references
def refs_to(blob, base, addr):
    """Where a binary refers to `addr`: [('word', offset)] for 32-bit data words, [('hilo', lui offset, lo offset)]
    for a lui/addiu (or ori) pair of MIPS code."""
    out = []
    w = struct.pack('<I', addr)
    p = blob.find(w)
    while p >= 0:
        if p % 4 == 0: out.append(('word', p))
        p = blob.find(w, p + 1)
    hi = ((addr + 0x8000) >> 16) & 0xFFFF; lo = addr & 0xFFFF
    for p in range(0, len(blob) - 4, 4):
        ins = struct.unpack_from('<I', blob, p)[0]
        if ins >> 26 != 0x0F or ins & 0xFFFF != hi: continue          # lui rt, hi
        rt = (ins >> 16) & 31
        for q in range(p + 4, min(p + 64, len(blob) - 4), 4):
            j = struct.unpack_from('<I', blob, q)[0]
            if j >> 26 in (0x09, 0x0D) and (j >> 21) & 31 == rt and j & 0xFFFF == lo:
                out.append(('hilo', p, q)); break
    return out


def follow(blob, ref):
    if ref[0] == 'word': return struct.unpack_from('<I', blob, ref[1])[0]
    hi = struct.unpack_from('<I', blob, ref[1])[0] & 0xFFFF; j = struct.unpack_from('<I', blob, ref[2])[0]
    lo = j & 0xFFFF
    if j >> 26 == 0x09 and lo & 0x8000: lo -= 0x10000
    return ((hi << 16) + lo) & 0xFFFFFFFF if j >> 26 == 0x09 else (hi << 16) | lo


# ------------------------------------------------------------------------------------------------ extraction
def extract(disc, read, ref_read=None, log=print):
    """-> ({key: text}, report rows) of the disc's executable and overlays. ref_read: for a patched disc (es-fan), a
    reader of its base disc (jp), to find where the base refers to each named string."""
    ver = disc.get('decomp') or ('jp' if disc.get('base') == 'jp' else None)
    if ver is None: return {}, []
    patched = disc.get('decomp') is None                        # es-fan: the jp layout, strings repointed
    v = Version(ver, read)
    ref = Version(ver, ref_read) if patched and ref_read else None
    dec = decoder(disc)
    yaml_cache = {}
    out, report = {}, []
    for key, d, kind, r, text in inventory(ver):
        try:
            raw = None
            if kind == 'sym':
                if r is None: report.append((key, 'absent', 0, 0, f'not in the {ver} release')); continue
                if r in v.sym: addr, ov = v.sym[r]
                else:                                                   # no symbol: where the binary has these bytes
                    ov = d if d in v.bins else 'main'
                    addr = (ref or v).find(ov, text)
                    if addr is None: report.append((key, 'missing', 0, 0, f'no symbol {r} in {ver}, text not found')); continue
                if patched and not ref: report.append((key, 'missing', 0, 0, 'a repointed string: give --base (the jp disc)')); continue
                if patched: addr = relocated(ref, v, ov, addr)
                raw = v.at(ov, addr)
            else:
                block, i = r
                if block in EMBEDDED:
                    tsym, stride, size = EMBEDDED[block]
                    if tsym not in v.sym: report.append((key, 'missing', 0, 0, f'no symbol {tsym} in {ver}')); continue
                    addr, ov = v.sym[tsym]
                    raw = v.at(ov, addr + i * stride, size)
                    raw = raw.split(b'\0')[0] if raw is not None else None
                else:
                    if block not in v.sym: report.append((key, 'missing', 0, 0, f'no symbol {block} in {ver}')); continue
                    addr, ov = v.sym[block]
                    lines = table_lines(d, block, yaml_cache)
                    pw = v.at(ov, addr + 4 * i * lines, 4)
                    if pw is None: raw = None
                    else:
                        p = struct.unpack('<I', pw)[0]
                        raw = b'' if p == 0 else v.at(ov, p)
            if raw is None: report.append((key, 'missing', 0, 0, 'address outside the binary')); continue
            from dws.text.extract import tidy
            out[key] = tidy(dec(raw), disc) if disc['id'] == 'es-fan' else dec(raw); report.append((key, 'aligned', 1, 1, ''))
        except (OSError, ValueError, KeyError) as e:
            report.append((key, 'missing', 0, 0, str(e)))
    return out, report


def table_lines(d, block, cache):
    f = [p for p in glob.glob(os.path.join(DECOMP, 'text', d, '*.yaml'))]
    for p in f:
        if p not in cache: cache[p] = load_yaml(p)
        if block in cache[p]:
            ln = cache[p][block].get('lines')
            return 1 if ln is None or isinstance(ln, dict) else int(ln)      # per-release line counts are eu only
    return 1


def relocated(ref, v, ov, addr):
    """es-fan: the address the patched binary uses for what jp has at `addr` (the same reference sites)."""
    rb, rbase = ref.blob(ov); pb, pbase = v.blob(ov)
    if rb is None or pb is None: return addr
    seen = {}
    for r in refs_to(rb, rbase, addr):
        a = follow(pb, r)
        seen[a] = seen.get(a, 0) + 1
    return max(seen, key=seen.get) if seen else addr


def own_keys():
    """{key: English} of the project's own executable text: the yaml entries the mod patch series adds (mods/patches,
    e.g. 0090's main.LAB_STR_*, shop.STR_IN_HAND), read from the patches (the one source of the build)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'mods', 'patches', '*.patch'))):
        d = None; sym = None
        for line in open(p, encoding='utf-8', errors='replace'):
            m = re.match(r'diff --git a/text/(\w+)/\w+\.yaml ', line)
            if m: d = m.group(1); continue
            if line.startswith('diff --git'): d = None; continue
            if d is None or not line.startswith('+'): continue
            m = re.match(r'\+    (\w+):\s*$', line)
            if m: sym = m.group(1); continue
            m = re.match(r'\+      en_us:\s*(.*)$', line)
            if m and sym:
                t = m.group(1).strip()
                if len(t) >= 2 and t[0] == t[-1] == '"': t = t[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                out[f'{d}.{sym}'] = t; sym = None
    return out
