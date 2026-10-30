"""`extract-text DISC`: the text of any known disc, in the one key format of the US story (docs/reference/text-sources.md).

    python3 tools/dws.py extract-text DISC.bin|DISC.cue|DISC.iso|extracted-dir [-o text/<source>]

The disc is identified by checksum (tools/discs.py); an unknown one is refused ("closest is ..."). Written, all gitignored
(the text of a disc is never committed):

    text/<source>/dialogue.json   US-keyed utterances and menu options of DG.SCN and MAPHEAD (s002.sec6.u0, s002.sec6.m0.o1,
                                  m1230.u0): the source's own pages of rows (a list of rows when it is one page); what the
                                  US structure has no place for is kept under x.<source>.<its own key>
    text/<source>/names.json      the executable's names and strings by key (item.38.name, ui.STR_...; tools/localize/executable/extract.py)
    text/<source>/report.csv      one row per key: aligned | us-only | src-only, and the page counts on each side

Alignment (2.3): a script by docs/data/script-map-us-jp.csv (the JP numbering of jp, jp-rev1 and es-fan), a section by its
id, an utterance by aligning the section's skeleton (its instructions without text, operands that name labels or scripts
masked; an utterance or a menu is one token) with the US one. Decoding: jp and jp-rev1 are real Shift-JIS (cp932);
es-fan redraws glyphs, so its codes go through docs/data/es-fan-glyphs.csv (tools/dws/text/esglyphs.py) first."""
import csv, difflib, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import discs
from dws import bytecode                                   # noqa: E402
from dws import textx                                  # noqa: E402

SCRIPT_MAP = os.path.join(ROOT, 'docs', 'data', 'script-map-us-jp.csv')
LABELISH = re.compile(r'\b(?:L\d+|sec\d+\w*)\b')


# ------------------------------------------------------------------------------------------------ the disc
def open_disc(path):
    """-> (registry entry, read(name) -> bytes or None). Refuses an unknown disc."""
    d, how, info = discs.identify(path)
    if how not in ('image', 'files'):
        near = f'; closest is {d["id"]} ({", ".join(k for k, v in info.items() if d["files"].get(k) == v)} match)' if d else ''
        raise SystemExit(f'{path}: not a known disc{near}. Known: ' + ', '.join(x['id'] for x in discs.DISCS) +
                         ' (tools/discs.py list); a new disc needs an entry in tools/discs.py and, for a new layout, a profile here')
    p = discs.image_of(path)
    if os.path.isdir(p):
        def read(name):
            q = os.path.join(p, *name.split('/'))
            return open(q, 'rb').read() if os.path.exists(q) else None
    else:
        img = discs.Image(p)
        read = img.find
    return d, read


def container(dg):
    """The entries of a DG.SCN, tolerant: es-fan pads the file after the sentinel (the table ends at the first offset that
    is not a sector boundary, or that goes back)."""
    try:
        offs = bytecode.container_entries(dg)
    except bytecode.BytecodeError:
        offs = []; p = 0
        while p + 4 <= bytecode.SECTOR:
            o = int.from_bytes(dg[p:p + 4], 'little')
            if o % bytecode.SECTOR or o < bytecode.SECTOR or (offs and o <= offs[-1]) or o > len(dg): break
            offs.append(o); p += 4
    return [dg[offs[n]:offs[n + 1]] for n in range(len(offs) - 1)]


def disassemble(dg, mh):
    """-> ({script: assembly text}, MAPHEAD assembly, {script: why it was skipped})."""
    out, skipped = {}, {}
    for n, e in enumerate(container(dg)):
        try:
            out[n] = bytecode.disassemble_script(e, f'script {n}')[0]
        except (bytecode.BytecodeError, IndexError, KeyError, ValueError) as ex:
            skipped[n] = str(ex)
    return out, bytecode.disassemble_script(mh, 'MAPHEAD')[0], skipped


# ------------------------------------------------------------------------------------------------ decoding
def codec_for(disc):
    """-> f(code) -> str for one 2-byte glyph code (not a control code), by the disc's profile."""
    if disc['id'] == 'us':
        return lambda code: bytecode.SJIS2CHAR.get(code, '{sjis %04x}' % code)
    table = {}
    if disc['id'] == 'es-fan':
        from dws.text import esglyphs
        table = esglyphs.load()
    def dec(code):
        if code in table: return table[code]
        try:
            ch = bytes([code >> 8, code & 0xFF]).decode('cp932')
        except UnicodeDecodeError:
            return '{sjis %04x}' % code
        return unicodedata.normalize('NFKC', ch) if disc['lang'] != 'ja' else ch
    dec.tidy = lambda t: tidy(t, disc)
    return dec


ES_GAP = re.compile(r'([.,;:!?»])(?=[A-Za-z0-9ÁÉÍÓÚÑÜáéíóúñü¿¡«])')


def tidy(text, disc):
    """es-fan draws its punctuation in a fixed 12-px cell, so the gap after a period or a comma is part of the glyph: with
    a proportional font it needs a space (`hambre.¿Tienes` -> `hambre. ¿Tienes`). Not between digits (1.5)."""
    if disc['id'] != 'es-fan': return text
    return ES_GAP.sub(lambda m: m.group(1) if m.group(1) in '.,' and m.start() > 0 and text[m.start() - 1].isdigit()
                      and text[m.end()].isdigit() else m.group(1) + ' ', text).rstrip()


def decode_row(s, dec):
    """A row as bytecode writes it (the US font's letters, {sjis XXXX}, {player}...) -> the source's text: its glyph codes
    decoded, the control codes kept as the escapes the compiler reads."""
    warn = lambda m: None
    lines = bytecode.text_units(s, 'row', {}, warn)
    out = []
    for b in lines:
        p = 0; cur = []
        while p < len(b):
            c = b[p]; a = b[p + 1] if p + 1 < len(b) else 0
            if c == 0x03:
                cur.append('{raw %s}' % b[p:p + 4].hex(' ')); p += 4; continue
            if c in bytecode.CTRL:
                name, arg = bytecode.CTRL[c]
                cur.append('{%s %d}' % (name, a) if arg else '{%s}' % name if a == 0 else '{raw %02x %02x}' % (c, a))
                p += 2; continue
            cur.append(dec((c << 8) | a) if c >= 0x80 else '{raw %02x %02x}' % (c, a)); p += 2
        out.append(''.join(cur))
    return '{br}'.join(out)


# ------------------------------------------------------------------------------------------------ skeletons
class Tok:
    """One element of a section's skeleton: an instruction (its text-free form), or an utterance ('U') or menu ('M') with
    its keys and the pages / options of the source."""
    __slots__ = ('t', 'key', 'pages', 'opts', 'owner')

    def __init__(self, t, key=None, pages=None, opts=None, owner=None):
        self.t, self.key, self.pages, self.opts, self.owner = t, key, pages, opts, owner


def skeleton(ins):
    f = [x for x in (bytecode.BYNAME.get(ins.name, (None, ''))[1] or '').split() if x != '_']
    args = []
    for k, a in enumerate(ins.args):
        if k < len(f) and f[k] in ('s', 'l'): a = '*'
        args.append(LABELISH.sub('L', a))
    return ins.name + ' ' + ','.join(args)


def sections(txt, kind, sid):
    """-> {section label: [Tok]} with the textx.Keyer keys (the source's own numbering)."""
    _, items, _ = bytecode.parse_script_text(txt, f'script {sid}')
    kr = textx.Keyer(kind, sid); out = {}; cur = None; owner = None
    for it in items:
        if it[0] == 'label':
            kr.label(it[1])
            if textx.SEC_LABEL.match(it[1]): cur = out.setdefault(it[1], []); owner = None
            continue
        ins = it[1]
        if ins.name.startswith('.'): kr.chain = False; continue
        ks = kr.ins(ins.name, len(ins.strings))
        if cur is None: continue
        if ins.name == 'SET_DIALOG_OWNER': owner = ins.args[0]
        if ins.name == 'SHOW_TEXTBOX':
            if ks: cur.append(Tok('U', ks[0], [list(ins.strings)], owner=owner))
            else: cur[-1].pages.append(list(ins.strings))
            continue
        if ins.name == 'SET_SELECTION':
            cur.append(Tok('M', ks[0].rsplit('.', 1)[0], opts=list(zip(ks, ins.strings)), owner=owner)); continue
        cur.append(Tok(skeleton(ins)))
    return out


def align(us, src):
    """Pairs the utterances and menus of two skeletons of one section. -> [(us Tok, src Tok)]."""
    a = [t.t for t in us]; b = [t.t for t in src]
    pairs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == 'equal':
            pairs += [(us[i1 + k], src[j1 + k]) for k in range(i2 - i1) if us[i1 + k].t in ('U', 'M')]
        elif op == 'replace':
            x = [t for t in us[i1:i2] if t.t in ('U', 'M')]; y = [t for t in src[j1:j2] if t.t in ('U', 'M')]
            if [t.t for t in x] == [t.t for t in y]: pairs += list(zip(x, y))
    return pairs


def script_map():
    """{US script: source (JP) script} of docs/data/script-map-us-jp.csv."""
    return {int(r['us_script']): int(r['jp_script']) for r in csv.DictReader(open(SCRIPT_MAP)) if r['us_script']}


# ------------------------------------------------------------------------------------------------ the bank
def pages_value(pages, dec):
    pg = [[dec.tidy(decode_row(r, dec)) for r in p] for p in pages]
    return pg[0] if len(pg) == 1 else pg


def dialogue(disc, read, us_dis=None, log=print):
    """-> (bank {key: value}, report rows) of the disc's DG.SCN and MAPHEAD, US-keyed."""
    dg, mh = read('SCN/DG.SCN'), read('SCN/MAPHEAD.SCN')
    if dg is None or mh is None: raise SystemExit('the disc has no SCN/DG.SCN or SCN/MAPHEAD.SCN')
    src_scripts, src_mh, skipped = disassemble(dg, mh)
    for n, why in skipped.items(): log(f'  {disc["id"]}: script {n} skipped ({why})')
    dec = codec_for(disc)
    if disc['id'] == 'us':                                   # the reference: textx's own bank (what the story build reads)
        bank = {}
        for n, txt in src_scripts.items(): bank.update(textx.keyed(txt.split('\n'), 'script', n)[1])
        bank.update(textx.keyed(src_mh.split('\n'), 'maphead')[1])
        return bank, [(k, 'aligned', len(v) if isinstance(v, list) and v and isinstance(v[0], list) else 1,
                       len(v) if isinstance(v, list) and v and isinstance(v[0], list) else 1, k) for k, v in bank.items()]
    us_scripts, us_mh = us_dis or us_disassembly()
    smap = script_map()
    bank, report, used = {}, [], set()
    jobs = [('maphead', None, us_mh, src_mh)] + [('script', u, us_scripts[u], src_scripts.get(smap.get(u)))
                                                  for u in sorted(us_scripts)]
    for kind, u, utxt, stxt in jobs:
        ss = sections(stxt, kind, smap.get(u) if u is not None else None) if stxt else {}
        used = set()                                           # ids of this job's source tokens that found a US place
        for lab, utoks in sections(utxt, kind, u).items():
            pairs = align(utoks, ss.get(lab, []))
            got = {id(x): y for x, y in pairs}
            for t in utoks:
                if t.t not in ('U', 'M'): continue
                y = got.get(id(t))
                if y is None:
                    report += [(k, 'us-only', len(t.pages) if t.t == 'U' else 1, 0, '') for k in
                               ([t.key] if t.t == 'U' else [k for k, _ in t.opts])]
                    continue
                used.add(id(y))
                if t.t == 'U':
                    bank[t.key] = pages_value(y.pages, dec)
                    report.append((t.key, 'aligned', len(t.pages), len(y.pages), y.key))
                else:
                    for n, (k, _) in enumerate(t.opts):
                        if n < len(y.opts):
                            bank[k] = dec.tidy(decode_row(y.opts[n][1], dec)); report.append((k, 'aligned', 1, 1, y.opts[n][0]))
                        else: report.append((k, 'us-only', 1, 0, ''))
        for lab, stoks in ss.items():                          # what the US structure has no place for
            for y in stoks:
                if y.t not in ('U', 'M') or id(y) in used: continue
                for k, v in ([(y.key, pages_value(y.pages, dec))] if y.t == 'U' else [(k, dec.tidy(decode_row(s, dec))) for k, s in y.opts]):
                    bank[f'x.{disc["id"]}.{k}'] = v; report.append((f'x.{disc["id"]}.{k}', 'src-only', 0, len(y.pages) if y.t == 'U' else 1, k))
    mapped = set(smap.get(u) for u in us_scripts)
    for n in sorted(set(src_scripts) - mapped):                # source scripts with no US counterpart (JP 203, 211, 224)
        for lab, stoks in sections(src_scripts[n], 'script', n).items():
            for y in stoks:
                if y.t == 'U':
                    bank[f'x.{disc["id"]}.{y.key}'] = pages_value(y.pages, dec)
                    report.append((f'x.{disc["id"]}.{y.key}', 'src-only', 0, len(y.pages), y.key))
                elif y.t == 'M':
                    for k, s in y.opts:
                        bank[f'x.{disc["id"]}.{k}'] = dec.tidy(decode_row(s, dec)); report.append((f'x.{disc["id"]}.{k}', 'src-only', 0, 1, k))
    return bank, report


def us_disassembly():
    """The US scripts, from extracted/SCN (the project's disc)."""
    d, m = textx.disassemble()
    scripts = {}
    for f in sorted(os.listdir(d)):
        mm = re.match(r'script_(\d+)\.scn\.txt$', f)
        if mm: scripts[int(mm.group(1))] = open(os.path.join(d, f), encoding='utf-8').read()
    return scripts, open(os.path.join(m, 'maphead.scn.txt'), encoding='utf-8').read()


# ------------------------------------------------------------------------------------------------ main
def write(outdir, disc, bank, report, extra=None):
    os.makedirs(outdir, exist_ok=True)
    note = (f'The text of the disc {disc["id"]} ({disc["title"]}), extracted from your own disc by `tools/dws.py extract-text`. '
            f'Copyrighted: never commit it (text/{disc["id"]}/ is gitignored).')
    with open(os.path.join(outdir, 'dialogue.json'), 'w', encoding='utf-8') as f:
        json.dump({'_comment': note, **bank}, f, ensure_ascii=False, indent=0); f.write('\n')
    for name, data in (extra or {}).items():
        with open(os.path.join(outdir, name), 'w', encoding='utf-8') as f:
            json.dump({'_comment': note, **data}, f, ensure_ascii=False, indent=0); f.write('\n')
    with open(os.path.join(outdir, 'report.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['key', 'status', 'us_pages', 'src_pages', 'src_key'])
        w.writerows(sorted(report, key=lambda r: natural(r[0])))


def natural(k):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', k)]


def summary(report):
    c = {}
    for r in report: c[r[1]] = c.get(r[1], 0) + 1
    utt = [r for r in report if '.u' in r[0] and not r[0].startswith('x.')]
    al = [r for r in utt if r[1] == 'aligned']
    return c, len(al), len(utt), sum(1 for r in al if r[2] != r[3])


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='dws.py extract-text', description=__doc__.split('\n')[0])
    ap.add_argument('disc'); ap.add_argument('-o', help='output folder (default text/<source>/)')
    ap.add_argument('--dialogue-only', action='store_true', help='skip the executable text')
    ap.add_argument('--base', metavar='DISC', help='es-fan: the Japanese disc it was made from (jp), to find its repointed strings '
                    'through the code that refers to them (without it, only the tables are read)')
    a = ap.parse_args(argv)
    disc, read = open_disc(a.disc)
    out = a.o or os.path.join(ROOT, 'text', disc['id'])
    print(f'{a.disc}: {disc["id"]} ({disc["title"]})')
    bank, report = dialogue(disc, read)
    extra = {}
    if not a.dialogue_only:
        from localize.executable import extract as exe
        if exe is not None:
            ref_read = None
            if disc.get('decomp') is None and a.base:
                bd, ref_read = open_disc(a.base)
                if bd['id'] != disc['base']: raise SystemExit(f'--base {a.base} is {bd["id"]}; {disc["id"]} was made from {disc["base"]}')
            names, rep2 = exe.extract(disc, read, ref_read)
            extra['names.json'] = names; report += rep2
    write(out, disc, bank, report, extra)
    c, al, utt, pd = summary(report)
    print(f'{os.path.relpath(out, ROOT)}/: {len(bank)} dialogue keys; utterances aligned {al} of {utt} US ({pd} with another '
          f'number of pages); ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())) + ' (report.csv; gitignored)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
