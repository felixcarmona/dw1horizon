"""The text of the mods written in Python, as a build loads it (docs/mods/translating.md, "A mod's translation").

A mod's lines are of two kinds: written in place (`say("Thank you!")`, keyed by the hash of the words: `<mod>.<sha1>[:8]`) and
named (`say(t("intro.hello"))`, the English in the mod's text/en.json under that name). `--lang X` loads text/X.json by the same
keys (a named line by its name) and says what is wrong with it, at the line the key belongs to:

  * a value marked `~fuzzy ` (`text sync` carried it from an edited line) is not shipped: the English is shown, with a warning;
  * a value with a character the target's font lacks, or an unknown escape, is an error;
  * the mod's lines X does not translate are one warning (they stay English), the keys of X that are no line of the mod one more;
  * a language no bank of the build has is an error (a typo, or a bank not written yet); a mod of several without it, a warning;
  * a named line whose English changed since it was translated (`text sync` lists it under `_changed`) is a note.

Without --lang, the named lines of en.json no file uses are a note (when every file of the mod is in the build)."""
import json, os, re
from ..diag import DwsError
from . import lower as PL

FUZZY = '~fuzzy '


def rel(p):
    """A path as a writer reads it: from the working directory when it is below it, else as it is."""
    if not os.path.isabs(p): return p
    r = os.path.relpath(p)
    return p if r.startswith('..') else r


def where_text(info):
    """`courier.py:12 asks, option yes` for a key of the mod (its line, its handler, what it is)."""
    if not info: return ''
    s = f'{os.path.basename(info["path"])}:{info["line"]} {info["handler"]}'
    if info.get('kind') == 'option': s += f', option {info.get("option")}'
    elif info.get('of', 1) > 1: s += f', page {info["page"]} of {info["of"]}'
    return s


def pos(info, bank_path):
    return (info['path'], info['line'], info['col']) if info else (rel(bank_path), 1, 1)


def file_key(mod, k):
    """A key as a bank file writes it -> the build's: `<mod>.<hash>` as it is, a name as `<mod>:<name>`."""
    m = PL.HASH_KEY.match(k)
    return k if m and m.group(1) == mod else f'{mod}:{k}'


def shown_key(mod, k):
    return k.split(':', 1)[1] if k.startswith(mod + ':') else k


def flat(v):
    if isinstance(v, str): return [v]
    return [x for y in v for x in flat(y)]


def load_banks(prog, mods, texts):
    """mods: {mod: its folder}; texts: {mod: {'info': {key: line info}, 'used': named lines used, 'files': .py files built}}."""
    lang = prog.bank.lang; warn = prog.warn.items; lacking = []; have = {}
    for mod, mdir in sorted(mods.items()):
        t = texts.get(mod) or {'info': {}, 'used': set(), 'files': set()}
        info = t['info']
        en_path = os.path.join(mdir, 'text', 'en.json')
        try: en = json.load(open(en_path, encoding='utf-8')) if os.path.exists(en_path) else {}
        except ValueError as e: prog.errors.append(DwsError(f'cannot read {rel(en_path)}: {e}', None)); continue
        names = PL.named_keys(en, mod)
        from .. import recruitment
        if mod == recruitment.MOD and recruitment.ACTIVE.get():
            t['used'].add(recruitment.LINE)
            info.setdefault(recruitment.KEY, {'path': en_path, 'line': 1, 'col': 1,
                                               'handler': 'extended recruitment'})
        from .textsync import mod_sources
        whole = set(map(os.path.abspath, mod_sources(mod, os.path.dirname(mdir)))) <= t['files']
        if whole:
            for name in names:
                if name not in t['used']:
                    prog.notes.append(f'{rel(en_path)}: note: the named line "{name}" is used by no file of {mod} (t("{name}"))')
        if lang == 'en': continue
        tdir = os.path.join(mdir, 'text')
        have[mod] = sorted(f[:-5] for f in os.listdir(tdir) if f.endswith('.json') and f != 'en.json' and '.' not in f[:-5]) \
            if os.path.isdir(tdir) else []
        p = os.path.join(tdir, f'{lang}.json')
        if not os.path.exists(p): lacking.append(mod); continue
        try: tr = json.load(open(p, encoding='utf-8'))
        except ValueError as e: prog.errors.append(DwsError(f'cannot read {rel(p)}: {e}', (rel(p), 1, 1))); continue
        if not isinstance(tr, dict): prog.errors.append(DwsError(f'{rel(p)}: a text bank is a JSON object key -> text', (rel(p), 1, 1))); continue
        prog.bank.files.append(p)
        unknown = []; done = set()
        for k, v in tr.items():
            if k.startswith('_'): continue
            key = file_key(mod, k); i = info.get(key)
            if i is None:
                if whole or not (PL.HASH_KEY.match(k) or key in {f'{mod}:{n}' for n in names}): unknown.append(k)
                continue
            try: prog.bank.check_value(p, k, v)
            except ValueError as e: prog.errors.append(DwsError(str(e).split(': ', 1)[-1], pos(i, p))); continue
            if isinstance(v, str) and v.startswith('~fuzzy'):
                warn.append(DwsError(f'{lang}.json: {k} is marked ~fuzzy (the English of this line changed and `text sync` carried the old '
                                     'translation): the English is shown until the translator reads it again and drops the marker', pos(i, p),
                                     f'compare it with the line here; then remove "~fuzzy " in {rel(p)}'))
                done.add(key); continue
            bad = False
            for row in flat(v):
                if key == recruitment.KEY and recruitment.ACTIVE.get():
                    if row.count('{species}') != 1:
                        prog.errors.append(DwsError(f'{lang}.json, {k}: expected exactly one {{species}}', pos(i, p)))
                        bad = True
                    row = row.replace('{species}', '')
                errs, _ = PL.font_problems(row)
                for msg, hint in errs + [(e, None) for e in PL.escape_problems(row)]:
                    prog.errors.append(DwsError(f'{lang}.json, {k}: {msg}', pos(i, p), hint)); bad = True
            if bad: done.add(key); continue
            prog.bank.data[key] = PL.resolve_escapes(v); prog.bank.origin[key] = p; done.add(key)
        missing = sorted((k for k in info if k not in done), key=lambda k: (info[k]['path'], info[k]['line'], info[k]['col']))
        if missing:
            shown = ', '.join(f'{shown_key(mod, k)} ({where_text(info[k])})' for k in missing[:6]) + (', ...' if len(missing) > 6 else '')
            warn.append(DwsError(f'{len(missing)} of {len(info)} lines of {mod} have no {lang} translation (they stay English): {shown}',
                                 (rel(p), 1, 1), f'add them to {rel(p)} by the keys of text/en.json (`dws text sync {mod}` writes it)'))
        if unknown:
            base = [k for k in unknown if re.match(r'^[sm]\d+\.', k)]
            warn.append(DwsError(f'{lang}.json has {len(unknown)} key(s) that are no line of {mod}: {", ".join(unknown[:6])}'
                                 + (', ...' if len(unknown) > 6 else '') + ' (a mistyped key, or a line that is gone)', (rel(p), 1, 1),
                                 'the keys are those of text/en.json'
                                 + ('; a line of the game (s178.sec5.u0) is not changed by a mod\'s bank: text/ours or TEXT= is how the '
                                    'game\'s own lines change' if base else '')))
        for k, was in (tr.get('_changed') or {}).items():
            key = file_key(mod, k)
            prog.notes.append(f'{rel(p)}: note: the English of "{k}" ({where_text(info.get(key))}) changed since it was translated '
                              f'(it was: {was!r}): read the translation again, then remove its entry from "_changed"')
    if lang != 'en' and lacking:
        other = any(os.path.basename(f) == f'{lang}.json' for f in prog.bank.files)
        if len(lacking) == len(mods) and not other:
            langs = sorted({x for v in have.values() for x in v})
            prog.errors.append(DwsError(f'--lang {lang}: no bank of the build is in {lang}: ' + ', '.join(
                f'{m} has no text/{lang}.json' for m in lacking), None,
                (f'the languages these mods have: {", ".join(langs)}; ' if langs else '') +
                f'a translation is text/{lang}.json beside text/en.json, by the same keys (docs/mods/translating.md)'))
        else:
            for m in lacking:
                warn.append(DwsError(f'{m} has no text/{lang}.json: its lines stay English', (rel(os.path.join(mods[m], 'text')), 1, 1)))
