"""`dws text sync [MOD ...]`: the text banks of the mods written in Python (docs/mods/story-language.md, section 1).

A new line of a mod is typed where it is said (`say("Thank you!")`); its key is the hash of its words (`<mod>.<sha1>[:8]`,
tools/dws/py/lower.py text_key), so a line that moves keeps its key and its translations. This writes

    story/mods/<mod>/text/en.json      the named lines (t("name"): written there by the modder, kept) and the snapshot of the
                                       others: key -> the words, in source order, and `_where` (key -> where it is, who says it,
                                       which page or which menu option)
    story/mods/<mod>/text/<lang>.json  kept: key -> translation; an edited line (a new key) gets the translation of the old
                                       line of the same handler that is gone, marked "~fuzzy " for the translator (not shipped
                                       until the marker is dropped); keys of lines that are gone are dropped. A named line keeps
                                       its key when its English changes: its translation stays and is listed under "_changed"
                                       (the English it was made from is kept under "_source")

The build reads the named lines from en.json; the other lines' words are in the sources; translations are loaded by key
(tools/dws/py/modtext.py checks them)."""
import difflib, glob, json, os
from .. import build as B

ROOT = B.ROOT
FUZZY = '~fuzzy '


MODS = os.path.join(ROOT, 'story', 'mods')


def mod_sources(mod, mods=None):
    """A mod's .py files: src/**/*.py, or, for a mod that keeps them elsewhere, the globs of `sources = [...]` in its mod.toml
    (relative to the mod's folder; the same files its build.sh gives the compiler)."""
    d = os.path.join(mods or MODS, mod)
    found = sorted(glob.glob(os.path.join(d, 'src', '**', '*.py'), recursive=True))
    toml = os.path.join(d, 'mod.toml')
    if not found and os.path.exists(toml):
        from ..minitoml import load_toml
        for g in load_toml(toml).get('sources', []):
            found += sorted(glob.glob(os.path.join(d, g), recursive=True))
    return found


def collect(mod, mods=None):
    """-> ({key: words}, {key: line info}) of a mod's .py files, in source order (file by file, line by line)."""
    from . import lower as PL
    texts = {}; info = {}; claims = PL.Claims()
    for f in mod_sources(mod, mods):
        m, _, _ = PL.lower_file(f, claims=claims)
        texts.update(m.texts)
        for k, v in m.text_info.items(): info.setdefault(k, v)
    order = sorted(info, key=lambda k: (info[k]['path'], info[k]['line'], info[k]['col']))
    return {k: texts[k] for k in order if k in texts}, {k: info[k] for k in order}


def describe(i):
    """The `_where` of a line: its place and what it is, so a translator knows who speaks and what is a menu option:
    `courier.py:12 asks: courier (Gotsumon) says, page 1 of 2`, `courier.py:14 asks: option yes of the tamer's menu`."""
    s = f'{os.path.basename(i["path"])}:{i["line"]} {i["handler"]}'
    if i.get('kind') == 'option': return s + f': option {i.get("option")} of {i.get("who", "the tamer")}\'s menu'
    s += f': {i.get("who", "?")} says'
    return s + (f', page {i["page"]} of {i["of"]}' if i.get('of', 1) > 1 else '')


def place(w):
    """`courier.py:12 asks: ...` (or the older `courier.py:asks`) -> (file, handler): what an edited line must share with a gone
    one to get its translation as ~fuzzy."""
    import re
    m = re.match(r'^([^:]+):(?:\d+ )?([^:,\s]+)', w or '')
    return (m.group(1), m.group(2)) if m else (w, None)


def sync(mod, log=print, mods=None):
    from . import lower as PL
    tdir = os.path.join(mods or MODS, mod, 'text'); os.makedirs(tdir, exist_ok=True)
    texts, info = collect(mod, mods)
    where = {k: describe(i) for k, i in info.items()}
    en = os.path.join(tdir, 'en.json')
    old = json.load(open(en, encoding='utf-8')) if os.path.exists(en) else {}
    old_where = old.get('_where', {}) if isinstance(old.get('_where'), dict) else {}
    named = PL.named_keys(old, mod)                              # the modder's own: kept as they are, in their order
    named_where = {f'{mod}:{n}': n for n in named}
    snap = {'_about': f'the lines of {mod}. Named lines (t("name") in src/) are written here and are yours to edit. The others are '
                      f'the lines written in src/*.py, keyed by the hash of their words: `dws text sync` writes them from the sources, '
                      f'and the sources win (an edit here is overwritten). Translations go in <lang>.json by the same keys '
                      f'(docs/mods/translating.md).',
            '_where': {**{named_where[k]: v for k, v in where.items() if k in named_where}, **{k: v for k, v in where.items() if k in texts}}}
    snap.update(named)
    snap.update(texts)
    open(en, 'w', encoding='utf-8').write(json.dumps(snap, ensure_ascii=False, indent=1) + '\n')
    gone = {k: v for k, v in old.items() if not k.startswith('_') and k not in texts and k not in named}
    n_fuzzy = 0; n_changed = 0
    for p in sorted(glob.glob(os.path.join(tdir, '*.json'))):
        lang = os.path.basename(p)[:-5]
        if lang == 'en' or '.' in lang: continue
        tr = json.load(open(p, encoding='utf-8'))
        out = {k: v for k, v in tr.items() if k.startswith('_') and k not in ('_source', '_changed')}
        source = dict(tr.get('_source') or {}); changed = dict(tr.get('_changed') or {})
        for n, words in named.items():                          # a named line: its translation stays; a changed English is noted
            if n not in tr: continue
            out[n] = tr[n]
            if n in source and source[n] != words and n not in changed: changed[n] = source[n]; n_changed += 1
            source[n] = words
        used = set()
        for k in texts:
            if k in tr: out[k] = tr[k]; continue
            if k in old: continue                     # an old line nobody translated yet: nothing to carry
            cands = [g for g in gone if g in tr and g not in used and place(old_where.get(g)) == place(where.get(k))]
            if cands:
                best = max(cands, key=lambda g: difflib.SequenceMatcher(None, str(gone[g]), texts[k]).ratio()); used.add(best)
                t = tr[best]; t = t[len(FUZZY):] if isinstance(t, str) and t.startswith(FUZZY) else t
                out[k] = FUZZY + t if isinstance(t, str) else t; n_fuzzy += 1
        for k, v in tr.items():                                 # a key that was never a line here (mistyped?): kept, `check --lang` says it
            if not k.startswith('_') and k not in out and k not in old and k not in texts: out[k] = v
        source = {n: w for n, w in source.items() if n in named and n in out}
        changed = {n: w for n, w in changed.items() if n in named and n in out}
        if source: out['_source'] = source
        if changed: out['_changed'] = changed
        open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    n = len(texts) + len(named)
    log(f'{mod}: {n} line{"s" if n != 1 else ""} -> {os.path.relpath(en, ROOT) if en.startswith(ROOT) else en}'
        + (f' ({len(named)} named)' if named else '')
        + (f'; {n_fuzzy} translation(s) carried as ~fuzzy (not shipped until the marker is dropped)' if n_fuzzy else '')
        + (f'; {n_changed} named line(s) whose English changed: listed under "_changed" in the translations' if n_changed else ''))
    return texts


def mods_with_python():
    return sorted(m for m in os.listdir(MODS) if mod_sources(m))


REVIEW_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mod text review</title><style>
:root{--bg:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#e3e3e8;--warn:#b25000;--miss:#c0392b;--head:#f5f5f7}
@media (prefers-color-scheme: dark){:root{--bg:#1c1c1e;--fg:#f2f2f7;--mute:#a1a1a6;--line:#38383a;--warn:#ff9f0a;--miss:#ff453a;--head:#2c2c2e}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 16px}
table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{border-bottom:1px solid var(--line);padding:6px;vertical-align:top;text-align:left;word-wrap:break-word}
th{background:var(--head)}td.k{font-family:ui-monospace,monospace;font-size:12px;color:var(--mute)}.m{color:var(--miss)}.w{color:var(--warn)}
</style></head><body><h3>__TITLE__</h3><table><thead><tr>__HEAD__</tr></thead><tbody>__BODY__</tbody></table></body></html>
"""


def review(mod, mods=None, out=None):
    """`dws text review MOD`: the mod's lines in source order, English beside each translation, with where they are, who says
    them and their state (missing, ~fuzzy, English changed) -> build/text-review/<mod>/review.csv and index.html."""
    import csv, html
    tdir = os.path.join(mods or MODS, mod, 'text')
    sync(mod, log=lambda m: None, mods=mods)                    # (en.json as the sources say now)
    en = json.load(open(os.path.join(tdir, 'en.json'), encoding='utf-8'))
    where = en.get('_where', {})
    langs = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(tdir, '*.json'))
                   if os.path.basename(p) != 'en.json' and '.' not in os.path.basename(p)[:-5])
    trs = {l: json.load(open(os.path.join(tdir, f'{l}.json'), encoding='utf-8')) for l in langs}
    rows = []
    for k, v in en.items():
        if k.startswith('_'): continue
        r = {'key': k, 'where': where.get(k, ''), 'en': v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}
        for l in langs:
            t = trs[l].get(k)
            st = ('missing' if t is None else '~fuzzy' if isinstance(t, str) and t.startswith('~fuzzy') else
                  'English changed' if k in (trs[l].get('_changed') or {}) else '')
            r[l] = '' if t is None else (t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)); r[f'{l} state'] = st
        rows.append(r)
    out = out or os.path.join(ROOT, 'build', 'text-review', mod); os.makedirs(out, exist_ok=True)
    cols = ['key', 'where', 'en'] + [c for l in langs for c in (l, f'{l} state')]
    with open(os.path.join(out, 'review.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
    E = html.escape
    head = ''.join(f'<th>{E(c)}</th>' for c in ['key', 'where / who', 'en'] + langs)
    body = ''.join('<tr><td class="k">' + E(r['key']) + '</td><td class="k">' + E(r['where']) + '</td><td>' + E(r['en']) + '</td>'
                   + ''.join(f'<td>{E(r[l])}' + (f' <span class="{"m" if r[l + " state"] == "missing" else "w"}">({E(r[l + " state"])})</span>'
                                                   if r[l + ' state'] else '') + '</td>' for l in langs) + '</tr>' for r in rows)
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(
        REVIEW_PAGE.replace('__TITLE__', E(f'{mod}: {len(rows)} lines, ' + (', '.join(langs) or 'no translation yet')))
        .replace('__HEAD__', head).replace('__BODY__', body))
    todo = {l: sum(1 for r in rows if r[f'{l} state']) for l in langs}
    print(f'{mod}: {len(rows)} lines -> {os.path.relpath(out, ROOT)}/review.csv and index.html'
          + ''.join(f'; {l}: {n} to do' for l, n in todo.items()))
    return 0
