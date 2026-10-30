"""Text extractor: the dialogue of the player's own DG.SCN / MAPHEAD.SCN -> a text bank with
one stable key per utterance or menu option, and the keyed (lossless) DWS form of a script.

Keys are positional, per section (docs/mods/translating.md 2.2):
  s002.sec6.u0      utterance 0 of section 6 of script 2: one text box, i.e. a run of SHOW_TEXTBOX in a row (its
                    pages; a label between two of them starts a new utterance, since code jumps there)
  s002.sec6.m1.o0   option 0 of menu 1 (one SET_SELECTION) of that section
  m1230.u0          MAPHEAD section 1230 (m1230.m0.o1 its menus)
The US bank (`text-extract`) gives an utterance its exact pages, a list of pages of rows (a list of rows when it is
one page), so the story build makes the disc's bytes; another text source may give a string, which the compiler wraps
into rows and pages. An option is a string. The {player}, {color 6}... escapes stay in the text."""
import json, os, re, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROW = re.compile(r'^(\s+)"((?:[^"\\]|\\.)*)"\s*(?:;.*)?$')
LABEL_LINE = re.compile(r'^([A-Za-z_][\w.]*):')
SEC_LABEL = re.compile(r'^sec\d+\w*$')
OPTION_KEY = re.compile(r'\.m\d+\.o\d+$')
BANK_DIR = os.path.join(ROOT, 'text', 'us')                       # the US disc's text (gitignored): dialogue.json
BANK = os.path.join(BANK_DIR, 'dialogue.json')


def unescape(body):
    if '\\{' in body: raise ValueError('\\{ in a text row (the font has no brace)')
    return re.sub(r'\\(["\\])', r'\1', body)


def key_prefix(name):
    """name: 'script_002.scn.txt' -> ('s002', None); 'maphead.scn.txt' -> ('m', 'sec')."""
    m = re.match(r'script_(\d+)\.scn\.txt$', name)
    return f's{int(m.group(1)):03d}' if m else None


class Keyer:
    """The text keys of one script, instruction by instruction in address order: the one definition every form uses
    (the bank, the lossless form, the port form, the readable story)."""
    def __init__(self, kind, sid=None):
        self.kind, self.sid = kind, sid
        self.cur = 'pre'; self.u = 0; self.m = 0; self.chain = False

    def prefix(self):
        if self.kind == 'maphead':
            mm = re.match(r'sec(\d+)$', self.cur)
            return f'm{mm.group(1)}' if mm else f'm.{self.cur}'
        return f's{self.sid:03d}.{self.cur}'

    def label(self, name):
        if SEC_LABEL.match(name): self.cur = name; self.u = 0; self.m = 0
        self.chain = False                                  # code jumps here: a new utterance starts

    def ins(self, name, rows):
        """-> the keys of this instruction's statement: [utterance] for the first page of an utterance, [] for a page
        that continues it, the option keys of a menu, [] for the rest."""
        if name == 'SHOW_TEXTBOX':
            if self.chain: return []
            self.chain = True; self.u += 1
            return [f'{self.prefix()}.u{self.u - 1}']
        self.chain = False
        if name == 'SET_SELECTION':
            self.m += 1
            return [f'{self.prefix()}.m{self.m - 1}.o{k}' for k in range(rows)]
        if rows: raise ValueError(f'{name}: text rows on an instruction that takes none')
        return []


def is_option(key):
    return bool(OPTION_KEY.search(key))


def keyed(lines, kind, sid=None):
    """The lossless form: an utterance becomes one `text("key")` line below its first SHOW_TEXTBOX (the SHOW_TEXTBOX
    lines that continue it are left out: the key gives their pages back), a menu one `text("key")` line per option.
    Returns (new lines, {key: value}): an utterance's value is its pages of rows (a list of rows when it is one page),
    an option's its row."""
    blocks = []                                         # [line, [rows]]: a line of the assembly and the text rows below it
    for line in lines:
        r = ROW.match(line)
        if r:
            if not blocks: raise ValueError(f'a text row before any instruction: {line.strip()}')
            blocks[-1][1].append((r.group(1), unescape(r.group(2)))); continue
        blocks.append([line, []])
    kr = Keyer(kind, sid); bank = {}; out = []; last = None
    for line, rows in blocks:
        code = line.split(';', 1)[0].strip()
        m = LABEL_LINE.match(code) if code and not code.startswith('.') else None
        if m: kr.label(m.group(1)); code = code[m.end():].strip()
        name = code.split()[0] if code else None
        if name is None and not rows: out.append(line); continue
        if name and name.startswith('.'): kr.chain = False; ks = []           # a directive (.byte, .section...)
        else: ks = kr.ins(name or '', len(rows))
        if name == 'SHOW_TEXTBOX':
            page = [t for _, t in rows]
            if ks:
                last = ks[0]; bank[last] = [page]; out.append(line)
                out.append(f'{rows[0][0] if rows else "        "}text("{last}")')
            else:
                bank[last].append(page)
            continue
        out.append(line)
        if name == 'SET_SELECTION':
            for k, (ind, t) in zip(ks, rows): bank[k] = t; out.append(f'{ind}text("{k}")')
        elif rows: raise ValueError(f'{name}: text rows below an instruction that takes none')
    for k, v in bank.items():
        if isinstance(v, list) and len(v) == 1: bank[k] = v[0]          # one page: a list of rows
    return out, bank


def disassemble(tmp=None, dg=None, maphead=None):
    """Disassembly of the disc's scripts, cached under build/dws-dis/ (keyed by size and mtime of the two files)."""
    import hashlib
    from . import bytecode
    dg = dg or os.path.join(ROOT, 'extracted/SCN/DG.SCN'); maphead = maphead or os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')
    for p in (dg, maphead):
        if not os.path.exists(p):
            raise FileNotFoundError(f'{os.path.relpath(p, ROOT)} not found: extract the disc first (tools/extract.sh)')
    sig = hashlib.sha1(''.join(f'{p}:{os.path.getsize(p)}:{os.path.getmtime(p)}' for p in (dg, maphead)).encode() +
                       bytecode.source_digest().encode()).hexdigest()[:12]
    base = os.path.join(ROOT, 'build', 'dws-dis', sig)
    d, m = os.path.join(base, 'dg'), os.path.join(base, 'mh')
    if not os.path.exists(os.path.join(base, 'done')):
        os.makedirs(base, exist_ok=True)
        if os.path.join(ROOT, 'tools') not in sys.path: sys.path.insert(0, os.path.join(ROOT, 'tools'))
        from dws import bytecode
        for src, dst in ((dg, d), (maphead, m)):
            r = bytecode.dis(src, dst)
            if r.returncode: raise ValueError(f'bytecode dis {src}: {r.stderr.strip()}')
        open(os.path.join(base, 'done'), 'w').close()
    return d, m


def extract(dg=None, maphead=None):
    """Returns the whole bank {key: text} of the disc."""
    bank = {}
    with tempfile.TemporaryDirectory() as tmp:
        d, m = disassemble(tmp, dg, maphead)
        for f in sorted(os.listdir(d)):
            mm = re.match(r'script_(\d+)\.scn\.txt$', f)
            if mm:
                _, b = keyed(open(os.path.join(d, f), encoding='utf-8').read().split('\n'), 'script', int(mm.group(1)))
                bank.update(b)
        _, b = keyed(open(os.path.join(m, 'maphead.scn.txt'), encoding='utf-8').read().split('\n'), 'maphead')
        bank.update(b)
    return bank


def write_bank(bank, path, lang='en', source='us'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {'_comment': f'Original game text ({lang}, disc {source}), extracted from your own disc by `tools/dws.py text-extract`. '
                       f'Copyrighted: never commit this file (text/{source}/ is gitignored).'}
    out.update(bank)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=0); f.write('\n')


def keyed_all():
    """{script id: DWS source} for every script of DG.SCN, and the MAPHEAD source (one disassembly)."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        d, m = disassemble(tmp)
        for f in sorted(os.listdir(d)):
            mm = re.match(r'script_(\d+)\.scn\.txt$', f)
            if mm:
                sid = int(mm.group(1))
                lines, _ = keyed(open(os.path.join(d, f), encoding='utf-8').read().split('\n'), 'script', sid)
                out[sid] = render(lines, sid)
        lines, _ = keyed(open(os.path.join(m, 'maphead.scn.txt'), encoding='utf-8').read().split('\n'), 'maphead')
    return out, render_maphead(lines)


def render(lines, sid):
    while lines and not lines[-1].strip(): lines.pop()
    head = [f'// script {sid} of DG.SCN in the lossless form (tools/dws.py text-keyed {sid}): instructions verbatim,',
            '// dialogue as keys of text/us/dialogue.json. Compiles back to the original bytes.']
    return '\n'.join(head + [f'script {sid} lossless {{'] + lines + ['}', ''])


def render_maphead(lines):
    while lines and not lines[-1].strip(): lines.pop()
    head = ['// MAPHEAD.SCN in the lossless form: instructions verbatim, dialogue as keys of text/us/dialogue.json.']
    return '\n'.join(head + ['maphead lossless {'] + lines + ['}', ''])


def keyed_script(sid):
    """DWS source of script `sid` in the lossless, keyed form: every instruction verbatim, every utterance and option a key."""
    with tempfile.TemporaryDirectory() as tmp:
        d, _ = disassemble(tmp)
        f = os.path.join(d, f'script_{sid:03d}.scn.txt')
        if not os.path.exists(f): raise FileNotFoundError(f'script {sid} does not exist (DG.SCN has 0-221)')
        lines, _b = keyed(open(f, encoding='utf-8').read().split('\n'), 'script', sid)
    return render(lines, sid)


def keyed_maphead():
    with tempfile.TemporaryDirectory() as tmp:
        _, m = disassemble(tmp)
        lines, _b = keyed(open(os.path.join(m, 'maphead.scn.txt'), encoding='utf-8').read().split('\n'), 'maphead')
    return render_maphead(lines)
