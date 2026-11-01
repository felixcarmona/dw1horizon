"""The story build: the readable DWS of story/base is the source of DG.SCN and MAPHEAD.SCN (docs/mods/dws.md section 3).

    python3 tools/dws.py story-build [SOURCE.dws ...] -o build/full/DG.SCN [--mods all|none|a,b] [--exe ...]
    python3 tools/dws.py story-base [--refresh]                 # only (re)generate story/base
    python3 tools/dws.py story-section 2 6 [-o FILE]            # one event of story/base, standalone (to read or to diff)
    python3 tools/dws.py story-verify A/DG.SCN A/MAPHEAD.SCN B/DG.SCN B/MAPHEAD.SCN

story/base is made from the US disc (`extracted/SCN/`) by the beautifier (`decompile-all --readable`, every event proven
against the disc), with its text as keys into text/us/dialogue.json (made from the disc, gitignored: no dialogue is ever
committed). story/base itself is committed, keys only, like the decompilation's code;
`story-base --reproduce` compares fresh generation with the committed files, checking both hashes and a reason for
each reviewed Horizon edit in base/authored.json. The build then

  1. compiles story/base (one program for the 222 scripts, one for MAPHEAD) and splices each event in place of the body
     of its section in the disassembly of the disc (the method of the verified `readable` disc),
     with the script's `shared` blocks (the code several sections reach) appended; a section an override replaces keeps
     its original body (the override is the new code);
  2. compiles the mod layer as one program on top of that: the given sources (dev-save, EXTRA_STORY) and every override
     of the selected mods (story/mods/<mod>/overrides/script_NNN/secN.dws or .patch, maphead/secN.*), with the usual
     insert/replace of tools/dws/backend.py, which now reads the spliced base instead of the disc;
  3. assembles DG.SCN (bytecode --compact, as the verified disc) and MAPHEAD.SCN.

With a freshly generated original base and no mod, the result is the verified `readable` disc's DG.SCN and MAPHEAD.SCN;
the committed base also includes Horizon edits. `story-verify` proves
any two builds equivalent section by section (flowcmp over the whole script from each section's entry)."""
import glob, hashlib, json, os, re, shutil, sys, tempfile
from . import backend as BE, build as B, textx
from .diag import DwsError
from dws import bytecode

ROOT = B.ROOT
BASE = os.path.join(ROOT, 'story', 'base')
MODS = os.path.join(ROOT, 'story', 'mods')
CORE = os.path.join(ROOT, 'story', 'core')
GENERATED = ('zones', 'maphead', 'names.dws')          # what story-base writes into story/base (gitignored)
STAMP = '.stamp.json'
OVERRIDE_PATH = re.compile(r'^(?:script_(\d{3})|maphead)/sec(\d+)\.(dws|patch)$')
TERMINATORS = {'END_SECTION', 'END_SCRIPT', 'JUMP_TO', 'JUMP_RETURN', 'JUMP_TO_FILE', 'SWITCH', 'SWITCH_W'}


def rel(p):
    return os.path.relpath(p, ROOT)


# ------------------------------------------------------------------------------------------------ story/base
def inputs_digest(lang='en'):
    """What story/base is made from: the disc's scripts, the names, the standard library and the tools."""
    h = hashlib.sha1()
    files = [BE.DG_SCN, BE.MAPHEAD_SCN, os.path.join(ROOT, 'story', 'names.toml'), os.path.join(ROOT, 'tools', 'dws', 'bytecode', '__init__.py')] + \
        sorted(glob.glob(os.path.join(CORE, '*.dws'))) + sorted(glob.glob(os.path.join(ROOT, 'tools', 'dws', '**', '*.py'), recursive=True))
    for f in files:
        if not os.path.exists(f): continue
        h.update(rel(f).replace(os.sep, '/').encode() + b'\0')
        with open(f, 'rb') as fh: h.update(hashlib.sha1(fh.read()).digest())
    # the species names: the generated scripts name NPCs Species.<Name><id> (a renamed species changes them)
    for d in (os.environ.get('SPECIES_CONTENT') or os.path.join(ROOT, 'content', 'species')).split(os.pathsep):
        for p in sorted(glob.glob(os.path.join(d, '*.json'))):
            h.update(os.path.basename(p).encode() + b'\0')
    return h.hexdigest()


def ensure_text(lang='en', log=print):
    p = textx.BANK
    if not os.path.exists(p):
        bank = textx.extract(); textx.write_bank(bank, p, lang)
        log(f'story: {len(bank)} text keys of your disc -> {rel(p)} (gitignored)')
    return p


def base_ready(base=BASE):
    """story/base is owned source (published, edited, a deleted script is a script the game does not
    have): it is made from a disc only when the folder does not exist, or by an explicit `dws story-base --refresh`."""
    return os.path.isdir(base) and any(os.path.exists(os.path.join(base, g)) for g in GENERATED)


def ensure_base(base=BASE, refresh=False, log=print, check=False):
    """story/base from the disc of this machine, when it is missing or was made from other inputs. -> True if (re)made."""
    if not refresh and base_ready(base): return False
    from . import readable
    ensure_text(log=log)
    os.makedirs(base, exist_ok=True)
    parent = os.path.dirname(os.path.abspath(base))
    tmp = tempfile.mkdtemp(prefix='.base-gen-', dir=parent)        # same depth as story/base: the relative imports hold
    before = set(glob.glob(os.path.join(ROOT, 'build', 'lift-*')))
    from .py import naming as N
    prev = N.BASE
    try:
        lifted, mhl, names = readable.lift_disc()
        stats = {}
        readable.write(tmp, lifted, mhl, names, stats, root_readme=False)
        N.use_base(tmp)                            # the screens, NPCs and sections of the views: the story being made
        from .py import view as PV, stubs
        PV.write_base(tmp, names)                  # the Python view beside each script.dws, and maphead/hooks.py (milestone 3b)
        stubs.write_base_pyi(log=log)              # what mods import from it (typings/dw/base/sNNN.pyi)
        if check:                                  # the views lowered and proven against the disc (milestone 4a)
            from .py import lower as PL
            _, bad = PL.check_base(tmp, lifted, mhl, log=log)
            if bad: raise DwsError('the Python view of story/base does not lower to the proven story: ' + '; '.join(bad[:3]), None)
        for g in GENERATED:
            dst = os.path.join(base, g)
            if os.path.isdir(dst): shutil.rmtree(dst)
            elif os.path.exists(dst): os.remove(dst)
            os.replace(os.path.join(tmp, g), dst)
        sm = readable.summarize(readable.rows(lifted, mhl))['all']
        json.dump({'inputs': inputs_digest(), 'scripts': len(lifted), 'proven_events': stats.get('proven_events', 0),
                   'sections': {k: sm[k] for k in ('sections', 'readable', 'shared-exit', 'partial', 'literal', 'port-only')}},
                  open(os.path.join(base, STAMP), 'w'), indent=1)
        log(f'story: {rel(base)} made from your disc: {len(lifted)} scripts + MAPHEAD, {sm["sections"]} sections '
            f'({sm["readable"]} readable), {stats.get("proven_events", 0)} events proven against the disc')
    finally:
        N.use_base(prev)
        shutil.rmtree(tmp, ignore_errors=True)
        for d in set(glob.glob(os.path.join(ROOT, 'build', 'lift-*'))) - before: shutil.rmtree(d, ignore_errors=True)
    return True


def tree_files(root):
    """{relative path: bytes} of the generated part of a story/base folder (GENERATED; no __pycache__)."""
    out = {}
    for g in GENERATED:
        p = os.path.join(root, g)
        if os.path.isfile(p): out[g] = open(p, 'rb').read(); continue
        for dp, dn, fn in os.walk(p):
            dn[:] = [d for d in dn if d != '__pycache__']
            for f in fn:
                if f.endswith('.pyc'): continue
                q = os.path.join(dp, f); out[os.path.relpath(q, root).replace(os.sep, '/')] = open(q, 'rb').read()
    return out


def reproduce(base=BASE, log=print):
    """Regenerate the original in a scratch folder; compare every file, checking both pins of reviewed authored edits.
    -> [unexpected paths] (empty: unchanged originals and authored edits all match)."""
    tmp = tempfile.mkdtemp(prefix='.base-repro-', dir=os.path.dirname(os.path.abspath(base)))   # same depth: imports hold
    try:
        ensure_base(tmp, refresh=True, log=lambda m: None)
        a, b = tree_files(base), tree_files(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    approved_path = os.path.join(base, 'authored.json')
    approved = json.load(open(approved_path, encoding='utf-8'))['files'] if os.path.exists(approved_path) else {}
    bad = reproduction_differences(a, b, approved)
    if bad:
        log(f'story: {rel(base)} differs from a fresh generation from your disc in {len(bad)} files: '
            + ', '.join(bad[:5]) + (' ...' if len(bad) > 5 else '') + '\n'
            '  - if you changed what it is made from (tools/dws, tools/dws/bytecode/__main__.py, story/names.toml, story/core, the species '
            'names), run `python3 tools/dws.py story-base --refresh` and commit story/base with that change;\n'
            '  - if you did not, check that extracted/ is the US disc: python3 tools/discs.py identify extracted')
    else:
        log(f'story: {rel(base)} matches original generation and {len(approved)} reviewed authored files ({len(a)} files)')
    return bad


def reproduction_differences(authored, original, approved):
    """Unchanged files must reproduce exactly; authored edits pin both the original generator and the reviewed source."""
    def sha(data): return hashlib.sha256(data).hexdigest() if data is not None else None
    bad = []
    for k in sorted(set(authored) | set(original) | set(approved)):
        a, b = authored.get(k), original.get(k)
        if k in approved:
            pin = approved[k]
            if (a == b or not pin.get('reason') or sha(a) != pin['authored_sha256']
                    or sha(b) != pin['original_sha256']): bad.append(k)
        elif a != b: bad.append(k)
    return bad


def base_files(base=BASE):
    scripts = sorted(glob.glob(os.path.join(base, 'zones', '*', '*', 'script.dws')))
    mh = sorted(glob.glob(os.path.join(base, 'maphead', '*.dws')))
    names = [os.path.join(base, 'names.dws')] if os.path.exists(os.path.join(base, 'names.dws')) else []
    return scripts, mh, names


def script_file(base, sid):
    for p in base_files(base)[0]:
        if re.match(rf's{sid:03d}(-|$)', os.path.basename(os.path.dirname(p))): return p
    return None


def maphead_file(base, sec):
    for fn in (f'screen{sec:03d}.dws', f'global-{sec:04d}.dws'):
        p = os.path.join(base, 'maphead', fn)
        if os.path.exists(p): return p
    return None


EVENT_HEAD = re.compile(r'^    (\S.*\{)    // section (\d+)\b.*$')


def event_source(base, sid, sec):
    """The standalone DWS of one event of story/base (`script N { npc ...; <event> }`, no imports: the build compiles
    overrides with story/core and story/base/names.dws loaded). -> (text, base file) or raises DwsError."""
    path = script_file(base, sid) if sid != 'maphead' else maphead_file(base, sec)
    where = f'script {sid}' if sid != 'maphead' else 'MAPHEAD'
    if not path: raise DwsError(f'{where} has no file in {rel(base)} (run `dws story-base`)', None)
    lines = open(path, encoding='utf-8').read().split('\n')
    npcs = [l for l in lines if re.match(r'^    npc \w+ = \d+;', l)]
    start = next((i for i, l in enumerate(lines) if (m := EVENT_HEAD.match(l)) and int(m.group(2)) == sec), None)
    if start is None:
        raise DwsError(f'{where} section {sec} is not an event of {rel(path)} (left in the port form, or no such section)', None)
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == '    }')
    head = 'maphead {' if sid == 'maphead' else f'script {sid} {{'
    out = [f'// {where} section {sec} of story/base ({rel(path)}): made from your disc by `dws story-section`. Do not commit a copy;',
           '// commit an override you wrote, or a .patch.', head]
    if npcs: out += npcs + ['']
    out += lines[start:end + 1] + ['}', '']
    return '\n'.join(out), path


# ------------------------------------------------------------------------------------------------ overrides
class Override:
    def __init__(self, mod, path, sid, sec, kind):
        self.mod, self.path, self.sid, self.sec, self.kind = mod, path, sid, sec, kind
        self.compiled = path                    # the file compiled (a .patch is materialized into the work directory)

    def __repr__(self):
        return f'mod {self.mod} ({rel(self.path)})'


def find_overrides(mods_root=MODS, only=None):
    """[Override] of story/mods/*/overrides. only: None (every mod), [] (none) or the mod names."""
    out = []; names = sorted(d for d in os.listdir(mods_root) if os.path.isdir(os.path.join(mods_root, d))) if os.path.isdir(mods_root) else []
    if only:
        missing = [m for m in only if m not in names]
        if missing: raise DwsError(f'no mod {", ".join(missing)} in {rel(mods_root)}', None)
    for mod in names:
        if only is not None and mod not in only: continue
        if only is None and not enabled(os.path.join(mods_root, mod)): continue     # `enabled = false`: only when named
        od = os.path.join(mods_root, mod, 'overrides')
        for dp, dn, fn in (os.walk(od) if os.path.isdir(od) else ()):
            dn.sort()
            for f in sorted(fn):
                if not f.endswith(('.dws', '.patch')): continue
                p = os.path.join(dp, f); r = os.path.relpath(p, od).replace(os.sep, '/')
                m = OVERRIDE_PATH.match(r)
                if not m:
                    raise DwsError(f'{rel(p)}: an override is overrides/script_NNN/secN.dws (or .patch) or overrides/maphead/secN.dws: '
                                   'the path names the section it replaces', None)
                out.append(Override(mod, p, 'maphead' if m.group(1) is None else int(m.group(1)), int(m.group(2)), m.group(3)))
    seen = {}
    for o in out:
        k = (o.sid, o.sec)
        if k in seen:
            raise DwsError(f'{"MAPHEAD" if o.sid == "maphead" else f"script {o.sid}"} section {o.sec} is overridden twice: '
                           f'{seen[k]} and {o}; one section has one override (merge them, or drop one mod with --mods)', None)
        seen[k] = o
    return out


def enabled(mod_dir):
    p = os.path.join(mod_dir, 'mod.toml')
    if not os.path.exists(p): return True
    from .minitoml import load_toml
    return load_toml(p).get('enabled', True) is not False


HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def apply_patch(text, patch, where):
    """A unified diff (`diff -u` of the `story-section` text and the edited one) applied to `text`. Context must match."""
    lines = text.split('\n'); plines = patch.split('\n'); hunks = []; i = 0
    while i < len(plines):
        m = HUNK.match(plines[i])
        if not m: i += 1; continue
        old, new = [], []; i += 1
        while i < len(plines) and not plines[i].startswith('@@'):
            l = plines[i]
            if l.startswith(' ') or l == '': old.append(l[1:]); new.append(l[1:])
            elif l.startswith('-') and not l.startswith('--- '): old.append(l[1:])
            elif l.startswith('+') and not l.startswith('+++ '): new.append(l[1:])
            elif l.startswith('\\'): pass
            else: break
            i += 1
        while old and new and old[-1] == '' and new[-1] == '' and i >= len(plines): old.pop(); new.pop()
        hunks.append((int(m.group(1)), old, new))
    if not hunks: raise DwsError(f'{where}: no hunk (a unified diff: diff -u base.dws mine.dws > {os.path.basename(where)})', None)
    shift = 0
    for n, (at, old, new) in enumerate(hunks, 1):
        want = max(at - 1 + shift, 0)
        cands = [k for k in range(len(lines) - len(old) + 1) if lines[k:k + len(old)] == old]
        if not cands:
            raise DwsError(f'{where}: hunk {n} (line {at}) does not match the event in story/base: the base was made from '
                           'another disc or tool version, or the patch was made against another section; '
                           'regenerate it from `dws story-section`', None)
        k = min(cands, key=lambda c: abs(c - want))
        lines[k:k + len(old)] = new; shift += len(new) - len(old)
    return '\n'.join(lines)


def materialize(overrides, base, work):
    """Each .patch becomes a .dws in work/patched/<mod>/...; .dws overrides compile where they are."""
    for o in overrides:
        if o.kind != 'patch': continue
        src, _ = event_source(base, o.sid, o.sec)
        text = apply_patch(src, open(o.path, encoding='utf-8').read(), rel(o.path))
        d = os.path.join(work, 'patched', o.mod, 'maphead' if o.sid == 'maphead' else f'script_{o.sid:03d}')
        os.makedirs(d, exist_ok=True)
        o.compiled = os.path.join(d, f'sec{o.sec}.dws'); open(o.compiled, 'w', encoding='utf-8').write(text)


def override_banks(overrides, lang):
    """Text of the mods that override: <override>.<lang>.json beside a file, story/mods/<mod>/text/<lang>.json."""
    out = []
    for o in overrides:
        mod_dir = o.path[:o.path.rindex(os.sep + 'overrides' + os.sep)]
        for p in (os.path.splitext(o.path)[0] + f'.{lang}.json', os.path.join(mod_dir, 'text', f'{lang}.json')):
            if os.path.exists(p) and p not in out: out.append(p)
    return out


# ------------------------------------------------------------------------------------------------ splice events
def chunks_of(lines):
    """Splits the text of a script at its section labels. -> (header lines, [chunk lines])"""
    labs = set(m.group(1) for l in lines for m in [re.match(r'\.section\s+\d+\s+(\S+)', l)] if m)
    first = next((i for i, l in enumerate(lines) if re.match(r'(\w+):', l) and re.match(r'(\w+):', l).group(1) in labs), None)
    if first is None: return lines, []
    head = lines[:first]; ch = []; cur = []
    for l in lines[first:]:
        m = re.match(r'(\w+):', l)
        if m and m.group(1) in labs and cur: ch.append(cur); cur = []
        cur.append(l)
    ch.append(cur)
    return head, ch


def label_refs(lines):
    refs = set()
    for l in lines:
        if l.startswith('    ') and not l.startswith('     '):
            body = re.sub(r';\s*0x[0-9a-f]+.*$', '', l[4:])
            refs.update(re.findall(r'\b(L\d+|sec\d+|q_\w+|u\d+_\w+|dws_\w+)\b', body))
    return refs


def prefixed(gen, prefix):
    """The labels a generated event defines, renamed `prefix + label` (the mod layer compiled on top has its own counter).
    Shared labels (`sh_NAME`, one namespace per script) keep their names: other events jump to them."""
    defs = {m.group(1) for l in gen for m in [re.match(r'([A-Za-z_]\w*):', l)] if m and not m.group(1).startswith('sh_')}
    if not defs: return gen
    rx = re.compile(r'\b(' + '|'.join(re.escape(d) for d in sorted(defs, key=len, reverse=True)) + r')\b')
    return [l if re.match(r'^\s+"', l) else rx.sub(lambda m: prefix + m.group(1), l) for l in gen]


def splice_events(lines, events, genf, prefix='b', shared=()):
    """Replaces, in the disassembly text `lines`, the body of each section that has a generated event (tools/dws/testing/sweep.py
    build_readable, the verified disc), and appends the script's `shared` blocks. The events of story/base reach the code
    they share through those blocks and the section entries (`secN`), never through a label inside another section's
    body; a body that a chunk staying from the disc still jumps into (a dead copy, a section no event replaces) is kept.
    -> (lines, spliced, kept, {sections spliced})"""
    head, ch = chunks_of(lines); spliced = kept = 0; done = set()
    labs = {m.group(2): int(m.group(1)) for l in lines for m in [re.match(r'\.section\s+(\d+)\s+(\S+)', l)] if m}
    chunk_of = {}
    for i, c in enumerate(ch):
        m = re.match(r'(\w+):', c[0])
        if m: chunk_of.setdefault(labs.get(m.group(1)), i)
    defs = [set(re.match(r'(\w+):', l).group(1) for l in c if re.match(r'(\w+):', l)) for c in ch]
    heads = [re.match(r'(\w+):', c[0]).group(1) if re.match(r'(\w+):', c[0]) else None for c in ch]
    gens = {}
    for sec, rep, code, ents, path in events:
        if sec not in chunk_of or not rep: kept += 1; continue
        gen = genf(sec, rep, code, ents, path)
        real = [l for l in gen if l.strip() and not l.lstrip().startswith(';')]
        if real and real[-1].strip() not in ('END_SECTION', 'END'): gen = gen + ['    END_SECTION']
        orig = [l.split(';')[0].split() for l in ch[chunk_of[sec]][1:] if l.startswith('    ') and not l.strip().startswith(('"', ';'))]
        orig = [x[0] for x in orig if x]
        real = [l.strip().split()[0] for l in gen if l.strip() and not l.lstrip().startswith((';', '"')) and not re.match(r'^\w+:', l)]
        if orig[:2] == ['JUMP_TO', 'JUMP_TO'] and orig[-1] != 'END_SECTION' and len(real) > 1 and real[-1] == 'END_SECTION' and real[-2] in TERMINATORS \
                and not re.match(r'^\w+:', [l for l in gen if l.strip() and not l.lstrip().startswith(';')][-2]):
            # the original section ends at its jump (a jump table runs on into the next section's: MAPHEAD 1220-1230):
            # no END_SECTION after it, so the layout of the tables is the original's
            k = max(k for k, l in enumerate(gen) if l.strip() == 'END_SECTION'); gen = gen[:k] + gen[k + 1:]
        gens[chunk_of[sec]] = (sec, prefixed(gen, f'{prefix}{sec}_'))
    allowed = set(heads) | {l for _, g in gens.values() for m in [re.match(r'(sh_\w+):', x) for x in g] if m for l in [m.group(1)]}
    for _, code, _ in shared:
        allowed |= {m.group(1) for x in code for m in [re.match(r'(\w+):', x)] if m}
    while True:                                            # the chunks that stay must not lose a label they jump to
        stay = [j for j in range(len(ch)) if j not in gens]
        outside = set().union(*[label_refs(ch[j]) for j in stay]) if stay else set()
        for _, code, _ in shared: outside |= {r for r in label_refs(code) if not r.startswith('sh_')}
        drop = [i for i in gens if (defs[i] - {heads[i]}) & outside]
        drop += [i for i, (_, g) in gens.items() if i not in drop and
                 any(r not in allowed and r not in {m.group(1) for x in g for m in [re.match(r'(\w+):', x)] if m} for r in label_refs(g))]
        if not drop: break
        for i in drop: del gens[i]; kept += 1
    for i, (sec, g) in gens.items():
        ch[i] = [f'{heads[i]}:'] + g + ['']; spliced += 1; done.add(sec)
    out = head + [l for c in ch for l in c]
    for name, code, path in shared:
        out += ['', f'    ; --- shared {name} ({os.path.basename(path)})'] + code
    return out, spliced, kept, done


def repoint(lines, sec, code, lab):
    """An event that cannot take the place of the section's body (other code jumps into it): the section starts at new
    code appended to the text, the old body stays for those jumps (what backend.apply does for a `replace`)."""
    k = next((k for k, l in enumerate(lines) if re.match(rf'\.section\s+{sec}\s+\S+', l)), None)
    if k is None: raise DwsError(f'MAPHEAD has no section {sec}', None)
    lines = list(lines); lines[k] = f'.section {sec} {lab}'
    end = code if code and code[-1].strip() in ('END_SECTION', 'END') else code + ['    END_SECTION']
    return lines + ['', f'{lab}:'] + end


def is_jump_table(gen):
    real = [l.strip().split()[0] for l in gen if l.strip() and not l.lstrip().startswith((';', '"')) and not re.match(r'^\w+:', l)]
    return real[:2] == ['JUMP_TO', 'JUMP_TO']


def generate_text(title, info, order, genf):
    """The assembly text of one script (or MAPHEAD) made from its compiled sources alone: the section table of its `sections`
    list (the original header's order; without one, the events in source order), each event under `secN:` in that order,
    then its shared blocks and subroutines. Nothing of the disc is read. -> lines"""
    events = {}
    for e in info['events']:
        if e[0] in events: raise DwsError(f'{title}: two events for section {e[0]} ({rel(events[e[0]][4])}, {rel(e[4])})', None)
        events[e[0]] = e
    shared = {name: code for name, code, _ in info.get('shared', [])}
    entries = list(order[0]) if order else [(n, None) for n in events]
    listed = {n for n, nm in entries if nm is None}
    entries += [(n, None) for n in events if n not in listed]          # events the list does not name (a mod's new section)
    hdr = []; seen = set()
    for n, name in entries:
        if name is not None:
            if name not in shared: raise DwsError(f'{title}: `sections ... {n} as {name}`: there is no `shared {name} {{ }}`', None)
            hdr.append(f'.section {n} sh_{name}')
        else:
            if n in seen: raise DwsError(f'{title}: section {n} is listed twice; a second entry is `{n} as NAME` (a shared block)', None)
            if n not in events: continue               # its event was deleted: the section does not exist (patch 0112)
            hdr.append(f'.section {n} sec{n}')
        seen.add(n)
    out = [f'; {title}: generated from the story sources by tools/dws/basebuild.py (nothing of the disc is kept)', ''] + hdr
    for n, name in entries:
        if name is not None or n not in events: continue
        gen = genf(*events[n])
        real = [l for l in gen if l.strip() and not l.lstrip().startswith(';')]
        if real and real[-1].strip() not in ('END_SECTION', 'END'): gen = gen + ['    END_SECTION']
        elif is_jump_table(gen) and len(real) > 1 and real[-1].strip() == 'END_SECTION' and not re.match(r'^\w+:', real[-2]) \
                and real[-2].strip().split()[0] in TERMINATORS:
            # a jump table runs on into the next section's (MAPHEAD 1220-1230: the engine indexes past its end): no END_SECTION
            k = max(k for k, l in enumerate(gen) if l.strip() == 'END_SECTION'); gen = gen[:k] + gen[k + 1:]
        out += ['', f'sec{n}:'] + prefixed(gen, f'b{n}_')
    for name, code, path in info.get('shared', []):
        out += ['', f'    ; --- shared {name} ({os.path.basename(path)})'] + prefixed(code, 'b_')
    if info.get('subs'): out += ['', '    ; --- subroutines (JUMP_AND_LINK targets)'] + info['subs']
    return out + ['']


def maphead_drift(mh_files):
    """How the lowered hooks.py differs from story/base's MAPHEAD DWS in what the names are read from (the script each screen
    sets, the Digimon placed), or None."""
    from .py import naming as N
    low = N.maphead_facts([open(f, encoding='utf-8').read() for f in mh_files]); dws = N.base_maphead()
    first = lambda f: {s: a[0] for s, (a, _) in f.items() if a and s <= 254}
    if first(low) != first(dws): return 'sets other scripts on some screens'
    if sorted(x for _, d in low.values() for x in d) != sorted(x for _, d in dws.values() for x in d): return 'places other Digimon'
    return None


def compile_base_story(base, work, lang, text, exclude, mh_overrides, mh_gen, report, from_py=True, text_source='us', exe='original'):
    """story/base -> work/dis (the 222 scripts as assembly text, the container index, a header) and work/MAPHEAD.SCN, made from
    the sources alone (see docs/mods/dws.md): every script, its section table and every section come
    from story/base; the container's size is the USA DG.SCN's (BE.DG_SCN_SIZE, its FILE_OFFSET_TABLE entry; build-disc.py pads
    to it). A section a mod's override replaces keeps its base code, unreached (the mod layer points the section table at the override, as backend.apply does).
    mh_overrides: [(sec, rep, code, ents, path)] of MAPHEAD overrides (compiled in the mod layer, mh_gen: its gen_event)."""
    scripts, mh_files, names = base_files(base)
    if not scripts or not mh_files: raise DwsError(f'{rel(base)} is empty: run `dws story-base`', None)
    if from_py:                                   # the base is built from its Python view (lowered); the .dws is the intermediate
        from .py import lower as PL
        pyd = os.path.join(work, 'base-py'); shutil.rmtree(pyd, ignore_errors=True)
        scripts, mh_files = PL.lower_base(base, pyd)
        report.append(f'story: built from the Python view: {len(scripts)} scripts and MAPHEAD lowered from story/base/**/*.py')
        drift = maphead_drift(mh_files)
        if drift: report.append(f'warning: story/base/maphead/hooks.py {drift} than the DWS beside it (maphead/*.dws), which the '
                                'names mods import from dw.base follow (naming.maphead_facts); make them agree')
    else:
        report.append('story: built from the DWS of story/base (--from-dws)')
    dis = os.path.join(work, 'dis')
    shutil.rmtree(dis, ignore_errors=True); os.makedirs(dis)
    # the base compiles for the original executable; another text source needs the target's font (the mod executable's
    # accents, docs/mods/font.md), so it compiles for that executable
    sexe = 'original' if text_source == 'us' else exe
    compile_base_story.fallback = []
    prog = B.compile_sources(scripts + names, sexe, lang, text, text_source=text_source)
    if text_source != 'us':
        miss = prog.bank.missing_in_source()
        report.append(f'story: text source {text_source}: {len(prog.bank.from_source)} keys; {len(miss)} keys of the US story it '
                      f'does not give stay in our English' + (f' ({", ".join(miss[:6])}{" ..." if len(miss) > 6 else ""})' if miss else ''))
        if prog.bank.unfit:
            report.append(f'story: text source {text_source}: characters without a glyph dropped: ' +
                          ', '.join(f'{c!r} x{n}' for c, n in sorted(prog.bank.unfit.items(), key=lambda x: -x[1])[:12]))
        compile_base_story.fallback = miss
    compile_base_story.rewrapped = set(prog.bank.rewrapped) if text_source != 'us' else set()
    orders = getattr(prog.b, 'orders', {})
    extra = sorted(set(prog.b.scripts) - set(range(BE.FIRST_NEW_SCRIPT)))
    if extra: raise DwsError(f'story/base has script(s) {extra[:10]} past the disc\'s {BE.FIRST_NEW_SCRIPT}: a new script belongs in a mod', None)
    n_scripts = BE.FIRST_NEW_SCRIPT
    absent = [sid for sid in range(n_scripts) if sid not in prog.b.scripts]
    if absent: report.append(f'story: {len(absent)} script(s) without a source are empty (no sections): {absent[:12]}'
                             f'{" ..." if len(absent) > 12 else ""}')
    built = 0; entries = []
    for sid in range(n_scripts):
        # a script with no source is one the game does not have: an empty section table (patch 0112: a section that is
        # not in the table runs nothing; the container keeps its entry, the game finds scripts by number)
        info = prog.b.scripts.get(sid) or {'events': [], 'shared': []}
        lines = generate_text(f'script {sid}', info, orders.get(sid), prog.b.gen_event)
        fn = f'script_{sid:03d}.scn.txt'
        open(os.path.join(dis, fn), 'w', encoding='utf-8').write('\n'.join(lines))
        try: size = len(bytecode.assemble_script('\n'.join(lines), fn, {'quiet': True})[0])
        except bytecode.BytecodeError as e: raise DwsError(f'story/base script {sid} does not assemble: {e}', None)
        if sid and size > bytecode.MAP_SCRIPT_MAX:
            raise DwsError(f'story/base script {sid} takes {size} bytes; the engine\'s script buffer holds {bytecode.MAP_SCRIPT_MAX} '
                           '(the beautifier fits it: `lift.fit`; regenerate with `dws story-base --refresh`)', None)
        open(os.path.join(dis, fn), 'w', encoding='utf-8').write('\n'.join(lines))
        entries.append(f'.entry {sid} {fn} {max(1, -(-size // bytecode.SECTOR))}'); built += len(info['events'])
    open(os.path.join(dis, 'header.bin'), 'wb').write(bytes(bytecode.SECTOR))     # the offset table (bytecode fills it); the rest zero
    open(os.path.join(dis, 'dg.scn.lst'), 'w').write('\n'.join(
        ['; index of the DG.SCN container for tools/dws/bytecode/__main__.py asm (generated from story/base)',
         f'.container DG.SCN {BE.DG_SCN_SIZE}', '.header header.bin'] + entries) + '\n')
    def make_mh(extra):
        mprog = B.compile_sources(mh_files + names, sexe, lang, list(text) + extra, text_source=text_source)
        minfo = {'events': getattr(mprog.b, 'mh_events', []), 'shared': getattr(mprog.b, 'mh_shared', [])}
        gen_event = mprog.b.gen_event
        # The unmodified engine keeps its small MAPHEAD buffer and original quiz.
        # The everything driver uses the mods opcode profile with the expanded
        # engine's explicit 32 KB buffer; it needs the appended quiz table too.
        if exe != 'original' and BE.MAPHEAD_LIMIT >= 0x8000 and any(e[0] == 1238 for e in minfo['events']):
            quiz = B.compile_sources([os.path.join(ROOT, 'story/new-game-quiz.dws')] + names,
                                     sexe, lang, list(text) + extra, text_source=text_source)
            event = quiz.b.mh_events[0]
            minfo['events'] = [event if e[0] == 1238 else e for e in minfo['events']]
            gen_event = lambda *e: quiz.b.gen_event(*e) if e[0] == 1238 else mprog.b.gen_event(*e)
        new = generate_text('MAPHEAD', minfo, getattr(mprog.b, 'orders', {}).get('maphead'), gen_event)
        done = set()
        if mh_overrides:                       # MAPHEAD overrides (compiled with the mod layer): in place, or at new code
            new, _, _, done = splice_events(new, mh_overrides, mh_gen, prefix='o')
            for sec, rep, code, ents, path in mh_overrides:
                if sec in done: continue
                new = repoint(new, sec, prefixed(mh_gen(sec, rep, code, ents, path), f'o{sec}_'), f'dws_mh{sec}_override')
        mh_txt = os.path.join(work, 'maphead.scn.txt'); open(mh_txt, 'w', encoding='utf-8').write('\n'.join(new))
        mh = os.path.join(work, 'MAPHEAD.SCN')
        big = 0x10000 if text_source != 'us' else max(BE.MAPHEAD_LIMIT, 0x8000 if exe in ('species', 'story-state') else 0)   # checked below (a source may not fit)
        r = bytecode.asm(mh_txt, mh, maphead_max=big, pack_ascii=BE.PACK_ASCII)
        if r.returncode: raise DwsError('story MAPHEAD: ' + (r.stderr.strip() or r.stdout.strip())[-1500:], None)
        return mprog, minfo, done, mh
    mprog, minfo, done, mh = make_mh([])
    if text_source != 'us':
        rw = sorted(compile_base_story.rewrapped | mprog.bank.rewrapped)
        if rw:       # a source paged for another font (text/ours: font b's 62-byte rows): wrapped again, never cut
            report.append(f'story: note: text source {text_source}: {len(rw)} hand-paged keys have rows too wide for font '
                          f'{BE.FONT["name"]} and are wrapped again for it ({", ".join(rw[:6])}{" ..." if len(rw) > 6 else ""})')
    limit = BE.MAPHEAD_LIMIT
    if os.path.getsize(mh) > limit and text_source != 'us':
        # another source's MAPHEAD text may not fit the engine's buffer (Spanish: ~5 KB more): the MAPHEAD keys that grew
        # most stay in our English (text/ours) until it fits, and are listed; rule: never the US text (text/us/ is only TEXT=us's)
        if text_source == 'ours':
            raise DwsError(f'story MAPHEAD.SCN is {os.path.getsize(mh)} bytes with TEXT=ours; the buffer holds {limit}: shorten the '
                           'MAPHEAD lines (m12xx keys) of text/ours/', None)
        from .textbank import TextBank
        ob = TextBank(lang, 'ours'); ob.load_source('ours')
        us = ob.data; cur = mprog.bank.data
        grown = sorted((k for k in mprog.bank.from_source if re.match(r'm\d', k)),
                       key=lambda k: len(json.dumps(us.get(k, ''))) - len(json.dumps(cur[k])))
        kept = []; tmpbank = os.path.join(work, 'maphead-ours-fallback.json')
        while os.path.getsize(mh) > limit and grown:
            over = os.path.getsize(mh) - limit
            n = max(4, min(len(grown), over // 40 + 1))
            kept += grown[:n]; grown = grown[n:]
            json.dump({k: us[k] for k in kept if k in us}, open(tmpbank, 'w', encoding='utf-8'), ensure_ascii=False)
            mprog, minfo, done, mh = make_mh([tmpbank])
        report.append(f'story: text source {text_source}: MAPHEAD.SCN would not fit its {limit}-byte buffer; {len(kept)} MAPHEAD keys '
                      f'stay in our English ({", ".join(kept[:6])}{" ..." if len(kept) > 6 else ""})')
        compile_base_story.fallback = sorted(set(getattr(compile_base_story, 'fallback', [])) | set(kept))
    built += len(minfo['events'])
    if mh_overrides:
        report.append(f'story: MAPHEAD sections overridden: {", ".join(str(e[0]) for e in mh_overrides)} '
                      f'({len(done)} in place, {len(mh_overrides) - len(done)} at new code)')
    if os.path.getsize(mh) > BE.MAPHEAD_LIMIT:
        raise DwsError(f'story MAPHEAD.SCN is {os.path.getsize(mh)} bytes; the game buffer holds {BE.MAPHEAD_LIMIT}', None)
    report.append(f'story: generated from story/base: {n_scripts} scripts and MAPHEAD, {built} events, nothing of the disc kept; '
                  f'MAPHEAD {os.path.getsize(mh)} bytes')
    return dis, mh


# ------------------------------------------------------------------------------------------------ the build
def parse_mods(arg):
    """--mods: 'all' (default: every mod with overrides/), 'none', or a comma list."""
    if arg in (None, '', 'all'): return None
    if arg == 'none': return []
    return [m.strip() for m in arg.split(',') if m.strip()]


def build(sources, out, exe='original', lang='en', text=(), lock=None, update_lock=False, profile='original', base=BASE,
          mods=None, refresh=False, log=print, mods_root=MODS, from_py=True, text_source='us', strict=False):
    from . import recruitment
    # The font/executable target is shared by original and extended passes.
    # Only the extended story supplies this mod's sources; --mods none always
    # selects the original story, even with a developer main source.
    owner = os.path.join(ROOT, 'story', 'mods', recruitment.MOD)
    extended = mods != [] and any(os.path.commonpath((owner, os.path.abspath(p))) == owner for p in sources)
    with recruitment.story(extended):
        return _build(sources, out, exe, lang, text, lock, update_lock, profile, base,
                      mods, refresh, log, mods_root, from_py, text_source, strict)


def _build(sources, out, exe='original', lang='en', text=(), lock=None, update_lock=False, profile='original', base=BASE,
          mods=None, refresh=False, log=print, mods_root=MODS, from_py=True, text_source='us', strict=False):
    """story/base (+ overrides of the mods) + `sources` -> DG.SCN at `out`. -> (prog, report, run dir, MAPHEAD path).
    from_py: the base is its Python view (story/base/**/*.py, lowered: the default); False builds it from the generated DWS beside it
    (byte for byte the same, `story-base --check` and test_dws prove it)."""
    report = []
    ensure_base(base, refresh, log=log)
    from .py import naming as N
    if os.path.abspath(base) != os.path.abspath(N.BASE): N.use_base(os.path.abspath(base))   # (what mods import: this base)
    work = os.path.join(os.path.dirname(os.path.abspath(out)), 'story')
    os.makedirs(work, exist_ok=True)
    overrides = find_overrides(mods_root, mods)
    materialize(overrides, base, work)
    by_file = {os.path.abspath(o.compiled): o for o in overrides}
    prelude = []
    if overrides:                               # overrides see what the base files see: story/core and story/base/names.dws
        prelude = sorted(glob.glob(os.path.join(CORE, '*.dws'))) + base_files(base)[2]
    # the mod layer first (its overrides decide what the base keeps), then story/base
    files = prelude + list(sources) + [o.compiled for o in overrides]
    try:
        prog = B.compile_sources(files, exe, lang, list(text) + override_banks(overrides, lang), lock, update_lock, profile,
                                 text_source=text_source)
    except B.DwsErrors as e:
        for x in e.errors:
            o = by_file.get(os.path.abspath(x.pos[0])) if getattr(x, 'pos', None) and isinstance(x.pos, tuple) else None
            if o and o.kind == 'patch': x.msg = f'{x.msg} (in {rel(o.path)}, applied to story/base)'
        raise
    comp = prog.b
    exclude = set(); mh_over = []
    # who replaces what: one section, one replacement (named by mod)
    def who(path):
        o = by_file.get(os.path.abspath(path)); return repr(o) if o else rel(path)
    for sid, info in sorted(comp.scripts.items()):
        by = {}
        for sec, rep, code, ents, path in info['events']:
            by.setdefault(sec, []).append((rep, path))
            o = by_file.get(os.path.abspath(path))
            if o:
                if o.sid != sid or o.sec != sec:
                    raise DwsError(f'{rel(o.path)} is the override of {"MAPHEAD" if o.sid == "maphead" else f"script {o.sid}"} section {o.sec} '
                                   f'(by its path) but has an event for script {sid} section {sec}', None)
                if sid >= BE.FIRST_NEW_SCRIPT: raise DwsError(f'{o}: overrides replace sections of story/base (scripts 0-221)', None)
                if rep: exclude.add((sid, sec))
        for sec, evs in by.items():
            if len(evs) > 1 and any(r for r, _ in evs):
                raise DwsError(f'script {sid} section {sec} is replaced by one and also changed by another: '
                               + ', '.join(f'{who(p)}{" (replace)" if r else " (insert)"}' for r, p in evs)
                               + '; one section takes one replacement: merge them, or leave a mod out (--mods / STORY_MODS)', None)
    for o in overrides:
        if o.sid != 'maphead' and not any(by_file.get(os.path.abspath(e[4])) is o for e in comp.scripts.get(o.sid, {}).get('events', [])):
            raise DwsError(f'{o}: no event for script {o.sid} section {o.sec} in it', None)
    for e in getattr(comp, 'mh_events', []) or []:
        o = by_file.get(os.path.abspath(e[4]))
        if not o:
            raise DwsError(f'{rel(e[4])}: `maphead {{ section(n) }}` events of a mod source are not applied; '
                           'write them as an override: story/mods/<mod>/overrides/maphead/secN.dws', None)
        if o.sid != 'maphead' or o.sec != e[0]:
            raise DwsError(f'{rel(o.path)}: its MAPHEAD event is section {e[0]}, its path says {o.sid} section {o.sec}', None)
        if not e[1]: raise DwsError(f'{o}: a MAPHEAD override replaces its section (`section({e[0]}) replace {{ }}`)', None)
        if any(x[0] == e[0] for x in mh_over): raise DwsError(f'MAPHEAD section {e[0]} is overridden twice', None)
        mh_over.append(e)
    for o in overrides:
        if o.sid == 'maphead' and not any(e[0] == o.sec for e in mh_over): raise DwsError(f'{o}: no `maphead {{ section({o.sec}) replace }}` in it', None)
    comp.mh_events = []
    font = dict(BE.FONT); stripped = set(BE.FONT['stripped']); limit = BE.MAPHEAD_LIMIT; slots = dict(BE.NPC_SLOTS)
    dis, mh = compile_base_story(base, work, lang, text, exclude, mh_over, comp.gen_event, report, from_py=from_py, text_source=text_source, exe=exe)
    if text_source != 'us':
        fb = os.path.join(os.path.dirname(os.path.abspath(out)), 'text-fallback.txt')
        open(fb, 'w', encoding='utf-8').write(''.join(k + '\n' for k in compile_base_story.fallback))
        report.append(f'story: {len(compile_base_story.fallback)} keys fall back to our English (listed in {rel(fb)})')
        if strict and compile_base_story.fallback:
            raise DwsError(f'TEXT={text_source} --strict: {len(compile_base_story.fallback)} keys are not in text/{text_source}/ '
                           f'(or did not fit): {", ".join(compile_base_story.fallback[:8])} ... ({rel(fb)})', None)
    for sid, sec in sorted(exclude):
        f = os.path.join(dis, f'script_{sid:03d}.scn.txt')
        if not os.path.exists(f) or not re.search(rf'^\.section\s+{sec}\s', open(f, encoding='utf-8').read(), re.M):
            o = next(o for o in overrides if o.sid == sid and o.sec == sec)
            raise DwsError(f'{o}: script {sid} has no section {sec} in story/base (the disc); an override replaces a section of story/base '
                           '(a new section belongs in the mod\'s src/)', None)
    BE.FONT.update(font); BE.FONT['stripped'] = stripped | BE.FONT['stripped']; BE.MAPHEAD_LIMIT = limit; BE.NPC_SLOTS.update(slots)
    saved = BE.DIS_CACHE, BE.MAPHEAD_SCN
    try:
        BE.DIS_CACHE, BE.MAPHEAD_SCN = dis, mh
        rep, run = B.assemble(prog, out, exe, compact=True)
    finally:
        BE.DIS_CACHE, BE.MAPHEAD_SCN = saved
    if comp.maphead is None:
        comp.maphead = os.path.join(run, 'MAPHEAD.SCN'); shutil.copyfile(mh, comp.maphead)
    if overrides:
        report.append('warning: overrides/ (and .patch files) are deprecated: a mod writes its own NPC or a guarded handler in Python '
                      '(docs/mods/story-language.md): ' + ', '.join(sorted({o.mod for o in overrides})))
    if overrides: report.append('story: overrides: ' + ', '.join(f'{o.mod}:{"maphead" if o.sid == "maphead" else o.sid}/{o.sec}'
                                                               f'{" (patch)" if o.kind == "patch" else ""}' for o in overrides))
    return prog, report + rep, run, comp.maphead


# ------------------------------------------------------------------------------------------------ equivalence of two builds
STOPS = {'END_SECTION', 'END_SCRIPT', 'JUMP_TO', 'JUMP_RETURN', 'JUMP_TO_FILE'}


def flow_text(e, title):
    """Disassembly of what can run in one script (or MAPHEAD), by following the code from every section entry (any layout,
    tails and dead code ignored). Jump tables (a section that starts with two JUMP_TOs: the engine indexes the entries) are
    roots too. -> (text lines, {root name: label})."""
    hdr, secs = bytecode.parse_header(e)
    roots = {}; todo = []; labels = {}
    for sid, off in secs:
        if f'sec{sid}' in roots: continue            # a repeated id: getScriptSection takes the first
        roots[f'sec{sid}'] = off; todo.append(off)
    ins = {}; prev = {}
    while todo:
        p = todo.pop()
        if p in ins or p >= len(e): continue
        n, tg = bytecode.instr_length(e, p)
        if n is None: raise DwsError(f'{title}: unknown opcode {e[p]:#04x} at {p:#x} on a path', None)
        ins[p] = n; todo += tg
        for t in tg: labels.setdefault(t, f'L{t:x}')
        if e[p] == 0x10 and e[p + n:p + n + 2] == b'\x12\x00': ins[p + n] = 2; prev[p + n] = 0x10; nxt = p + n + 2
        else: nxt = p + n
        name = bytecode.dis_instr(e, p, n, {t: f'L{t:x}' for t in tg})[0][0].split()[0]
        if name not in STOPS: todo.append(nxt)
    for name, off in list(roots.items()):          # jump tables: entry k is the instruction at section + 4k
        k = 1; p = off
        while p in ins and e[p] == bytecode_op('JUMP_TO') and ins[p] == 4:
            q = off + 4 * k
            if q >= len(e) or e[q] != bytecode_op('JUMP_TO'): break
            roots[f'{name}#{k}'] = q; labels.setdefault(q, f'L{q:x}')
            if q not in ins:
                n, tg = bytecode.instr_length(e, q); ins[q] = n
                for t in tg:
                    labels.setdefault(t, f'L{t:x}')
                    stack = [t]
                    while stack:
                        r = stack.pop()
                        if r in ins or r >= len(e): continue
                        m, tg2 = bytecode.instr_length(e, r)
                        if m is None: raise DwsError(f'{title}: unknown opcode at {r:#x}', None)
                        ins[r] = m; stack += tg2
                        for t2 in tg2: labels.setdefault(t2, f'L{t2:x}')
                        nm = bytecode.dis_instr(e, r, m, {t2: f'L{t2:x}' for t2 in tg2})[0][0].split()[0]
                        if nm not in STOPS: stack.append(r + m)
            p = q; k += 1
    for name, off in roots.items(): labels.setdefault(off, f'L{off:x}')
    out = []
    for p in sorted(ins):
        if p in labels: out.append(f'{labels[p]}:')
        lines, _ = bytecode.dis_instr(e, p, ins[p], labels, prev.get(p))
        out += ['    ' + lines[0]] + ['        ' + x for x in lines[1:]]
    return out, {name: labels[off] for name, off in roots.items()}


def bytecode_op(name):
    return next(k for k, v in bytecode.OPS.items() if v[0] == name)


def compare_entries(ea, eb, title):
    """-> (equal roots, [(root, why)]): every section (and jump-table entry) of two builds of one script, by flowcmp."""
    from . import flowcmp
    if ea.rstrip(b'\0') == eb.rstrip(b'\0'):
        return len(flow_text(ea, title)[1]), []
    la, ra = flow_text(ea, title); lb, rb = flow_text(eb, title)
    eq = 0; bad = []
    for r in sorted(set(ra) | set(rb), key=lambda x: (len(x), x)):
        if r not in ra or r not in rb: bad.append((r, f'only in {"the first" if r in ra else "the second"}')); continue
        try:
            if flowcmp.compare(_from(la, ra[r]), _from(lb, rb[r]))['equal']: eq += 1
            else: bad.append((r, 'not equivalent'))
        except ValueError as x:
            bad.append((r, f'cannot compare: {x}'))
    return eq, bad


def _from(lines, label):
    """The text seen from one entry: from its label to the end, then the start (every jump target is in it)."""
    k = lines.index(f'{label}:')
    return lines[k:] + ['    ZZ_END_OF_TEXT'] + lines[:k]


def verify(dg_a, mh_a, dg_b, mh_b, log=print, skip=(0,)):
    """Two DG.SCN/MAPHEAD.SCN pairs, section by section: the code each section can run, compared by control flow (flowcmp:
    the same instructions with the same operands, text rows and choices on every path; layout, jump threading and redundant
    owner changes aside). Script 0 is skipped (unused: getScript(0) is MAPHEAD). -> number of differences."""
    da, db = open(dg_a, 'rb').read(), open(dg_b, 'rb').read()
    oa, ob = bytecode.container_entries(da), bytecode.container_entries(db)
    bad = []; total = eq_all = same = 0
    if len(oa) != len(ob): bad.append(('DG.SCN', '-', f'{len(oa) - 1} scripts against {len(ob) - 1}'))
    for n in range(min(len(oa), len(ob)) - 1):
        if n in skip: continue
        ea, eb = da[oa[n]:oa[n + 1]], db[ob[n]:ob[n + 1]]
        eq, b = compare_entries(ea, eb, f'script {n}')
        total += eq + len(b); eq_all += eq; same += not b and ea.rstrip(b'\0') == eb.rstrip(b'\0')
        bad += [(f'script {n}', r, w) for r, w in b]
    meq, mb = compare_entries(open(mh_a, 'rb').read(), open(mh_b, 'rb').read(), 'MAPHEAD')
    bad += [('MAPHEAD', r, w) for r, w in mb]
    log(f'DG.SCN: {total} sections and jump-table entries in {min(len(oa), len(ob)) - 1 - len(skip)} scripts, {eq_all} equivalent '
        f'({same} scripts byte-identical); MAPHEAD: {meq + len(mb)}, {meq} equivalent')
    for f, r, w in bad[:40]: log(f'  differs: {f} {r}: {w}')
    if len(bad) > 40: log(f'  ... {len(bad) - 40} more')
    return len(bad)
