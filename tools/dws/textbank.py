"""Text banks: key -> text, in JSON files.

A value is a string (wrapped into lines and pages by the compiler), a list of strings (one
page with exactly those rows) or a list of lists (several pages). Order of loading, later wins:
  text/us/dialogue.json       extracted from the player's own disc (gitignored; `dws text-extract`): only for TEXT=us (and
                              a TEXT_ZONES test build, whose other zones stay US English)
  text/ours/dialogue*         our English, under any other source but ours itself: what that source lacks (a language of ours
                              like text/es/ falls back to it silently; a disc's source lists it, `missing_in_source`)
  text/<TEXT>/dialogue.json   the chosen text source (TEXT=ours|us|jp|jp-rev1|es-fan; `dws extract-text DISC` makes the
                              disc ones, text/ours/ is committed): rule: a source other than us never reads text/us/ (the
                              base disc may be another release, docs/mods/data-sources.md)
  text/<lang>.json            the project's own text
  <source>.<lang>.json        next to each .dws source (e.g. first-quest.en.json)
  --text FILE                 extra banks
The ORIGINAL game text never goes into a committed file: the story source holds keys only."""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ORIGINAL_KEY = re.compile(r'^[sm]\d+\.')          # s002.sec6.u0, s002.sec6.m1.o0, m117.u0: keys made by text-extract
EXTRACT_HINT = ('extract the texts from your own disc first: python3 tools/dws.py text-extract '
                '(writes text/us/dialogue.json from extracted/SCN/; the original dialogue is never committed)')


SOURCES = ('us', 'ours', 'jp', 'jp-rev1', 'es-fan')
CJK = re.compile('[\u3040-\u30ff\u3400-\u9fff]')      # kana, kanji: a line a translation left in Japanese (no glyphs)
# characters of the other sources that the target's font (the US one, plus the F0xx glyphs its mod executable has) does not
# have: the first of their replacements the font has (a tuple: in order of preference)
FIT = {'…': '...', '‥': ('…', '..'), '♪': '', '〜': ('~', '-'), '～': ('~', '-'), '~': '-', '–': '-', '—': '-', '―': ('—', '-'),
       '“': '"', '”': '"', '‘': "'", '’': "'", '（': ('(', ''), '）': (')', ''), '％': ('%', ''), '／': ('/', '-'),
       '(': '', ')': '', '/': '-', '*': '', '&': 'y', '%': '', '#': '', '_': ' ', '<': '"', '>': '"', '[': '', ']': ''}


_SINGLE = []
PAGES = os.path.join(ROOT, 'text', 'ours', 'pages.json')     # the US pages of the single-page keys (numbers only, committed)
_PAGES = {}
# TEXT_ZONES=zone,...: a test build of only those zones of a source (backend.configure sets it for a build; the environment's
# by default)
TEXT_ZONES = os.environ.get('TEXT_ZONES', '').replace(',', ' ').split()


def single_page_keys():
    """The keys of the lines the game's C code shows as one box each, never a second page: the texts of MAPHEAD's table
    sections (1220-1253 that start with a table of jumps: the shopkeepers' lines, the item keeper's...), which the code reads by
    entry (script_common.c getShopkeeperLine, resolveMapHeadEntry) and shows with one showTextbox. From story/base."""
    if not _SINGLE:
        import glob
        keys = set()
        for f in glob.glob(os.path.join(ROOT, 'story', 'base', 'maphead', 'global-*.dws')):
            src = open(f, encoding='utf-8').read()
            for m in re.finditer(r'section\((\d+)\)[^\n]*\n(.*?)(?=\n    section\(|\Z)', src, re.S):
                body = [l.strip() for l in m.group(2).split('\n') if l.strip() and not l.strip().startswith('//')]
                if len(body) > 1 and body[0].startswith('goto ') and body[1].startswith('goto '):
                    keys |= set(re.findall(r'text\("(m\d+\.[^"]+)"\)', m.group(2)))
        _SINGLE.append(frozenset(keys))
    return _SINGLE[0]


def us_page_counts():
    """{key: pages} of the single-page keys in the game's own (US) text: how many pages the game shows of each (m1230.u0, the
    shopkeepers' lines, has 14: getShopkeeperLine picks one by page). Committed as numbers (text/ours/pages.json, written by
    `dws text-extract`), so the check works without the US text; a single-page key it lacks is an error, not a silent 1."""
    if not _PAGES:
        try: d = json.load(open(PAGES, encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise ValueError(f'{os.path.relpath(PAGES, ROOT)}: cannot read the page counts of the single-page lines ({e}); '
                             'python3 tools/dws.py text-extract writes it from your disc')
        _PAGES.update({k: v for k, v in d.items() if not k.startswith('_')})
        miss = sorted(single_page_keys() - set(_PAGES))
        if miss:
            raise ValueError(f'{os.path.relpath(PAGES, ROOT)} has no page count for {len(miss)} single-page key(s) of story/base '
                             f'({", ".join(miss[:6])}); python3 tools/dws.py text-extract writes it from your disc')
    return _PAGES


def write_us_pages(bank, path=PAGES):
    """text/ours/pages.json from the US bank {key: text}: the page count of every single-page key (numbers, no text)."""
    pages = {k: len(v) if isinstance(v, list) and v and isinstance(v[0], list) else 1
             for k, v in bank.items() if k in single_page_keys()}
    out = {'_comment': 'How many pages the US game shows of each line of a MAPHEAD table (textbank.single_page_keys): numbers '
                       'only, made from the disc by `tools/dws.py text-extract`; TextBank.single_page_overflow checks a source '
                       'against them.'}
    out.update(sorted(pages.items(), key=lambda kv: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', kv[0])]))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=0); f.write('\n')
    _PAGES.clear()
    return len(pages)


def source_dir(name):
    """text/<name>/ when it holds a text source (dialogue.json, or dialogue/*.json as text/ours/), else None: a new language of
    the game is a folder of its own, by the same keys (docs/mods/translating.md)."""
    d = os.path.join(ROOT, 'text', name)
    ok = re.fullmatch(r'[a-z][a-z0-9_-]*', name) and (os.path.exists(os.path.join(d, 'dialogue.json')) or os.path.isdir(os.path.join(d, 'dialogue')))
    return d if ok else None


class TextBank:
    def __init__(self, lang='en', source='us'):
        if source not in SOURCES and not source_dir(source):
            have = [d for d in sorted(os.listdir(os.path.join(ROOT, 'text'))) if source_dir(d)] if os.path.isdir(os.path.join(ROOT, 'text')) else []
            raise ValueError(f'TEXT={source}: no text/{source}/ (a text source is a folder text/<name>/ with dialogue.json or '
                             f'dialogue/*.json by the keys of the US story, as text/ours/; the discs\' are us, jp, jp-rev1, es-fan: '
                             f'`dws extract-text DISC`)' + (f'; here: {", ".join(have)}' if have else ''))
        self.lang = lang; self.data = {}; self.files = []; self.original_loaded = False
        self.source = source; self.from_source = set(); self.unfit = {}; self.untranslated = set()
        self.rewrapped = set()                             # keys whose pages had a row too wide for the target: wrapped again
        self.origin = {}                                   # key -> the file its text was read from (the last one that gave it)
        self.us_pages = dict(us_page_counts())            # key -> how many pages the game's own (US) text has

    def load(self, path, original=False):
        try:
            d = json.load(open(path, encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise ValueError(f'{path}: cannot read the text bank ({e})')
        if not isinstance(d, dict):
            raise ValueError(f'{path}: a text bank is a JSON object key -> text')
        for k, v in d.items():
            if k.startswith('_'): continue
            self.check_value(path, k, v)
            self.data[k] = v; self.origin[k] = path
        self.files.append(path)
        if original: self.original_loaded = True

    @staticmethod
    def check_value(path, k, v):
        ok = isinstance(v, str) or (isinstance(v, list) and v and
                                    (all(isinstance(x, str) for x in v) or
                                     all(isinstance(x, list) and all(isinstance(y, str) for y in x) for x in v)))
        if not ok:
            raise ValueError(f'{path}: key "{k}": a string, a list of rows or a list of pages is expected')

    def load_defaults(self, sources=(), extra=()):
        from .textx import BANK
        # rule: only TEXT=us reads the US text (text/us/, gitignored), and a test build of some zones of a source (TEXT_ZONES:
        # the other zones stay US English, on the USA disc)
        if (self.source == 'us' or TEXT_ZONES) and os.path.exists(BANK): self.load(BANK, original=True)
        if self.source not in SOURCES: self.load_source('ours')    # a language of ours (text/es/): what it lacks stays our English
        elif self.source not in ('us', 'ours'): self.load_source('ours', fallback=True)   # a disc's source: what it lacks is ours, listed
        if self.source != 'us': self.load_source(self.source)
        p = os.path.join(ROOT, 'text', f'{self.lang}.json')
        if os.path.exists(p): self.load(p)
        for s in sources:
            side = os.path.splitext(s)[0] + f'.{self.lang}.json'
            if os.path.exists(side): self.load(side)
        for e in extra: self.load(e)

    def load_source(self, src, fallback=False):
        """text/<src>/: dialogue.json (and, for ours, dialogue/*.json): the keys of the US story; `x.<src>.` keys (what the
        US structure has no place for) are not loaded. Values are fitted to the game's font (`fit`). fallback: the keys are not
        the chosen source's (`missing_in_source` lists those the source does not replace)."""
        d = os.path.join(ROOT, 'text', src)
        files = [os.path.join(d, 'dialogue.json')] if os.path.exists(os.path.join(d, 'dialogue.json')) else []
        if os.path.isdir(os.path.join(d, 'dialogue')):
            only = TEXT_ZONES                                                    # a test build of some zones only
            files += sorted(os.path.join(d, 'dialogue', f) for f in os.listdir(os.path.join(d, 'dialogue'))
                            if f.endswith('.json') and (not only or f[:-5] in only))
        if not files and src != 'ours' and not os.path.isdir(os.path.join(d, 'dialogue')):   # a language still empty: all ours
            raise ValueError(f'TEXT={src}: text/{src}/dialogue.json does not exist; make it from your own disc: '
                             f'python3 tools/dws.py extract-text YOUR-{src.upper()}-DISC.cue')
        for p in files:
            data = json.load(open(p, encoding='utf-8'))
            for k, v in data.items():
                if k.startswith(('_', 'x.')) or v in ('', [], None): continue
                self.check_value(p, k, v)
                if CJK.search(json.dumps(v, ensure_ascii=False)):
                    from . import backend as BE
                    absent = set(CJK.findall(json.dumps(v, ensure_ascii=False))) - BE.FONT['chars']
                    if absent and src == 'ja':
                        raise ValueError(f'{p}: {k}: Japanese glyphs missing: {"".join(sorted(absent))}')
                    if absent:
                        self.untranslated.add(k)
                        continue
                self.data[k] = self.fit(k, v); self.origin[k] = p
                if not fallback: self.from_source.add(k)
            self.files.append(p)

    def source_of(self, key):
        """The bank file a key's text comes from when it is not the game's own (US) text or a line of a source: a translation,
        a text source, a side bank; None for the US bank and for the words of a .py line."""
        from .textx import BANK
        p = self.origin.get(key)
        return None if p is None or os.path.abspath(p) == os.path.abspath(BANK) else p

    def single_page_overflow(self, key, pages):
        """A key of a line the game's code shows one box at a time (`single_page_keys`) whose text takes more pages than the
        game's own: the extra page is never shown. -> a message, or None."""
        if key not in single_page_keys(): return None
        us = self.us_pages.get(key, 1)
        if pages <= us: return None
        where = self.source_of(key)
        if where and not os.path.relpath(where).startswith('..'): where = os.path.relpath(where)
        return (f'{key} takes {pages} pages{f" in {where}" if where else ""}, and the game shows it '
                f'{"one page" if us == 1 else f"{us} pages"} (a line of a MAPHEAD table: its code shows each entry as one box, '
                'getShopkeeperLine / resolveMapHeadEntry): the rest would never be shown')

    def missing_in_source(self):
        """The keys of the US story the chosen source does not give (they stay our English, text/ours)."""
        if self.source == 'us': return []
        return sorted(k for k in self.data if ORIGINAL_KEY.match(k) and k not in self.from_source)

    def fit(self, key, v):
        """A value of another source, for the game's font: characters it has no glyph for are replaced (FIT) or dropped (and
        counted in self.unfit); a page whose rows are too wide becomes a string the compiler wraps."""
        from . import backend as BE
        from dws import bytecode
        ok = set(bytecode.CHAR2SJIS) | BE.FONT['chars'] | {' '}

        def row(t):
            out = []; i = 0
            while i < len(t):
                c = t[i]
                if c == '{':
                    j = t.find('}', i)
                    if j > i: out.append(t[i:j + 1]); i = j + 1; continue
                if c in ok: out.append(c)
                elif c in FIT:
                    f = FIT[c] if isinstance(FIT[c], tuple) else (FIT[c],)
                    out.append(next((x for x in f if all(y in ok for y in x)), f[-1]))
                else:
                    d = BE.strip_char(c)
                    if d and all(x in ok for x in d): out.append(d)
                    else: self.unfit[c] = self.unfit.get(c, 0) + 1
                i += 1
            return re.sub(r'  +', ' ', ''.join(out)).strip()
        if isinstance(v, str): return row(v)
        pages = [v] if all(isinstance(x, str) for x in v) else v
        pages = [[row(r) for r in p] for p in pages]
        if any(not BE.fits(r, packed=BE.packed_key(key)) for p in pages for r in p):
            self.rewrapped.add(key)        # e.g. text/ours paged for font b (62-byte rows) built for the original font
            return ' '.join(r for p in pages for r in p if r)                 # wrapped by the compiler
        return pages

    def get(self, key):
        """Returns ('wrap', str) | ('pages', [[row...]...]) or None."""
        v = self.data.get(key)
        if v is None: return None
        if isinstance(v, str): return ('wrap', v)
        if all(isinstance(x, str) for x in v): return ('pages', [list(v)])
        return ('pages', [list(p) for p in v])

    def missing_message(self, key):
        if ORIGINAL_KEY.match(key) and self.source != 'us':
            return (f'text key "{key}" is a line of the game\'s story and TEXT={self.source} does not give it (no text/us/ fallback '
                    'under another source)', f'add it to text/ours/dialogue/ (our English){"" if self.source == "ours" else f" or to text/{self.source}/"}')
        if ORIGINAL_KEY.match(key) and not self.original_loaded:
            return f'text key "{key}" is an original-game line and text/us/dialogue.json does not exist', EXTRACT_HINT
        near = [k for k in self.data if k.split('.')[0] == key.split('.')[0]][:3]
        h = ('similar keys: ' + ', '.join(near)) if near else \
            f'banks loaded: {", ".join(self.files) or "none"}; add the key to a bank (docs/mods/dws.md)'
        return f'text key "{key}" not found', h
