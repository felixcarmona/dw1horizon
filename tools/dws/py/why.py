"""`dws why NPC [--as "Horn=ASKED, invited"]`: for an NPC of a mod written in Python (or a base NPC that mods add guarded
handlers to), where it is declared, when it appears and which of its talk handlers answers, in the order they are tried.
With `--as`, each guard is evaluated for that state (quest stages by name, flags `name` or `name=0`); a guard that tests
something else is `?`. (`dws why` without a Python NPC of that name explains the base game's presence rules: citycli.)"""
import ast, glob, os, re
from .. import build as B

ROOT = B.ROOT


def parse_as(text):
    state = {}
    for part in filter(None, (p.strip() for p in (text or '').split(','))):
        k, _, v = part.partition('=')
        state[k.strip()] = v.strip() if v else '1'
    return state


def evaluate(node, m, state):
    """True / False / None (unknown) of a guard under `state`."""
    if isinstance(node, ast.BoolOp):
        vals = [evaluate(v, m, state) for v in node.values]
        if isinstance(node.op, ast.And):
            return False if False in vals else (None if None in vals else True)
        return True if True in vals else (None if None in vals else False)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        v = evaluate(node.operand, m, state)
        return None if v is None else not v
    def stage(q):
        v = state.get(q)
        return m.quests[q]['stages'].index(v) if v in m.quests[q]['stages'] else (0 if v is None else None)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in m.quests:
        s = stage(node.value.id)
        return None if s is None else s == m.quests[node.value.id]['stages'].index(node.attr)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
            and node.func.value.id in m.quests and node.func.attr in ('before', 'reached'):
        q = node.func.value.id; s = stage(q); i = m.quests[q]['stages'].index(node.args[0].attr)
        return None if s is None else (s < i if node.func.attr == 'before' else s >= i)
    if isinstance(node, ast.Name) and node.id in m.flags:
        return state.get(node.id, '0') not in ('0', 'false', 'False', 'no')
    return None


def describe(m, src, node):
    from .lower import Body
    try:
        pre = []; dws = Body(m, None, 'why').cond(node, pre)
    except Exception as e:
        dws = f'({e})'
    return ast.get_source_segment(src, node), dws


def mods_files(paths=None):
    """The .py files of the mods: story/mods/*/src, or of the mod folders and files given (as `check` takes them)."""
    if not paths: return sorted(glob.glob(os.path.join(ROOT, 'story', 'mods', '*', 'src', '**', '*.py'), recursive=True))
    from ..cli import mod_files
    return [f for f in mod_files(paths) if f.endswith('.py')]


def why(name, as_text=None, out=print, files=None):
    """-> True if `name` is an NPC of a .py file (printed), False otherwise."""
    from .lower import Module, Claims
    state = parse_as(as_text); found = False; claims = Claims()
    for f in (mods_files() if files is None else files):
        try:
            m = Module(f, claims=claims).read()
        except Exception:
            continue
        if name not in m.npcs: continue
        d = m.npcs[name]; src = m.src; rel = os.path.relpath(f, ROOT) if os.path.abspath(f).startswith(ROOT + os.sep) else f
        if not found:
            mark = lambda v: '' if not state else {True: '  [true]', False: '  [false]', None: '  [?]'}[v]
        found = True
        owner = next((n for n, x in m.npcs.items() if x.get('taken') == name), None)
        if d.get('base') and owner:                  # take_over(name): the mod's own name for it answers
            out(f'{name}: an NPC of the base story (script {d["script"]}, slot {d["slot"]}), taken over by {m.mod or rel} as {owner} '
                f'({rel}:{m.npcs[owner]["node"].lineno}): its talk is the mod\'s')
            name, d = owner, m.npcs[owner]
        elif d.get('base'):
            out(f'{name}: an NPC of the base story (script {d["script"]}, slot {d["slot"]}); {rel} adds handlers to it')
        elif d.get('taken'):
            out(f'{name}: {rel}:{d["node"].lineno}, take_over({d["taken"]}): screen {d["screen_id"]}, slot {d["slot"]}, '
                f'owned by {m.mod or "this file"}; when it is there is the base\'s rule')
        else:
            scr = m.screens[d['screen']]
            out(f'{name}: {rel}:{d["node"].lineno}, screen {scr["ids"][0]}{" (new)" if scr["new"] else ""}, slot {d["slot"]}, '
                f'owned by {m.mod or "this file"}')
            if 'when' in d['kw']:
                py, dws = describe(m, src, d['kw']['when'])
                out(f'  there when: {py}  ->  {m.presence(d["kw"]["when"])}{mark(evaluate(d["kw"]["when"], m, state))}')
            else:
                out('  there: always (no presence rule)')
        hs = [h for h in m.handlers if h.kind == 'talk' and h.arg == name]
        out('  on_talk, tried in order:' if hs else '  no talk handler in this file')
        answered = False
        for k, h in enumerate(hs, 1):
            if h.when is None:
                line = f'    {k}. {h.fn.name} (line {h.fn.lineno}): always'
                if state and not answered: line += '  <- answers'; answered = True
                out(line); continue
            py, dws = describe(m, src, h.when)
            v = evaluate(h.when, m, state)
            line = f'    {k}. {h.fn.name} (line {h.fn.lineno}): when {py}  ->  {dws}{mark(v)}'
            if v and not answered: line += '  <- answers'; answered = True
            out(line)
        if d.get('base'): out('    else: the base\'s own talk')
    return found


def why_name(name, out=print):
    """A name of the game's story that is not an NPC (a flag such as meat_farm_explained, a variable): where story/base sets
    and reads it, which is what `why` can say of it. -> True if story/base uses it."""
    import re
    hits = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'story', 'base', '**', '*.py'), recursive=True)):
        for n, l in enumerate(open(f, encoding='utf-8'), 1):
            if re.search(rf'\b{re.escape(name)}\b', l): hits.append(f'  {os.path.relpath(f, ROOT)}:{n}: {l.strip()[:110]}')
    if not hits: return False
    out(f'{name}: not an NPC; a name of the game\'s story (story/names.toml). Where story/base uses it ({len(hits)}):')
    for h in hits[:30]: out(h)
    if len(hits) > 30: out(f'  ... (grep -rn "\\b{name}\\b" story/base)')
    return True
