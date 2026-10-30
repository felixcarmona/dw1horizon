"""Pipeline: .dws files -> Program (declarations, events) -> backend.py (patching DG.SCN, MAPHEAD,
.MAP files) -> bytecode -> DG.SCN, optionally a disc."""
import os, re, subprocess, sys, tempfile
from . import backend as BE
from .diag import DwsError
from .gen import Program, is_wide_line, is_story_line
from .textbank import TextBank
from .alloc import Allocator
from .targets import profile_pool

ROOT = BE.ROOT
ROW_KEY = re.compile(r'^(\s*)text\("([^"]+)"\)\s*$')


class DwsErrors(Exception):
    def __init__(self, errors, warnings=()):
        self.errors, self.warnings = errors, list(warnings)


def compile_sources(files, exe='original', lang='en', text=(), lock=None, update_lock=False, profile='original', text_source='us'):
    BE.set_font(exe)                                   # the extra glyphs the target executable has (docs/mods/font.md)
    # The integrated engine trims NPC animations too. Read the built target instead of
    # assuming only the parked story-state engine has memreclaim.
    heap_map = (os.environ.get('DW_HEAP_MAP') or os.path.join(BE.exe_dir(exe), 'SLUS_010.32.elf.map')) if exe != 'original' else None
    try:
        with open(heap_map, errors='replace') as f:
            BE.TRIMMED_NPCS = 'npc_anim_trim.c.o' in f.read()
    except (OSError, TypeError):
        BE.TRIMMED_NPCS = False

    BE.NPC_SLOTS['max'] = 16 if exe == 'story-state' else 8
    BE.MAPHEAD_LIMIT = BE.MAPHEAD_MAX_GIVEN or BE.MAPHEAD_LIMITS[exe]   # MAPHEAD_SCRIPT_BUFFER of the target executable
    bank = TextBank(lang, text_source); bank.load_defaults(sources=files, extra=text)
    alloc = Allocator(lock, profile_pool(profile)); b = BE.Backend()
    prog = Program(b, bank, alloc, max_opcode_level={'original': 0, 'mods': 1, 'species': 1, 'story-state': 2}[exe]); prog.profile = profile; prog.exe = exe
    prog.bank_files = bank.files; prog.bank = bank; prog.notes = []
    files = py_sources(files, prog)
    for f in files:
        try:
            prog.load(f)
        except DwsError as e:
            prog.errors.append(e)
    if not prog.errors:
        prog.generate()
    if not prog.errors and exe == 'original':          # raw asm can hide wide opcodes
        for sid, info in b.scripts.items():
            for sec, rep, code, ents, path in info['events']:
                for l in code:
                    if is_wide_line(l):
                        prog.errors.append(DwsError(f'script {sid} section {sec}: "{l.strip()}" is a wide instruction, '
                                                    'which the original executable does not have', None,
                                                    'compile with --exe mods or use ids of 255 or less'))
    if not prog.errors and exe != 'story-state':             # raw asm can hide the story-state opcodes too
        for sid, info in b.scripts.items():
            for sec, rep, code, ents, path in info['events']:
                for l in code:
                    if is_story_line(l):
                        prog.errors.append(DwsError(f'script {sid} section {sec}: "{l.strip()}" is a story-variable instruction '
                                                    '(story-state engine), which this executable does not have', None, 'compile with --exe story-state'))
    for e in prog.errors + prog.warn.items: e.pos = source_pos(e.pos)        # a statement lowered from a .py: its line there
    if prog.errors:
        raise DwsErrors(prog.errors, prog.warn.items)
    if update_lock and lock:
        alloc.write_lock(lock)
    return prog


def save_locks():
    """The numbers new names got in their mod's reserved range, into its save.lock (append-only). Called when the whole
    command succeeded: a run that failed (a file that does not compile, a screen without room) leaves the lock as it was."""
    from .py import lower as PL
    PL.save_locks()


def source_pos(pos):
    """A position in a file lowered from a .py (build/py-lowered/) -> that .py file, its line (the source map: `// @py N`) and
    the column of the line's first word; any other position is returned as it is. A writer never sees the lowered DWS."""
    if not pos or len(pos) < 2 or not pos[0]: return pos
    from .py.lower import LINEMAP
    from .diag import SOURCES
    lm = LINEMAP.get(os.path.abspath(str(pos[0])))
    if not lm: return pos
    py = lm[2]; ln = lm[1].get(pos[1]) or 1
    if py not in SOURCES:
        try: SOURCES[py] = open(py, encoding='utf-8').read().split('\n')
        except OSError: SOURCES[py] = []
    line = SOURCES[py][ln - 1] if 0 < ln <= len(SOURCES[py]) else ''
    return (py, ln, len(line) - len(line.lstrip()) + 1)


def backend_error(e):
    """BE.BackendError -> DwsError at the source line (the .py one for a story file)."""
    return DwsError(e.msg, source_pos(e.pos), getattr(e, "hint", None))


def py_sources(files, prog):
    """A `.py` story file is lowered to DWS (tools/dws/py/lower.py) and compiled as such: its declarations, script part and
    MAPHEAD part are files in build/py-lowered/ (errors point at the .py: the lowering checks the subset first). The new lines
    of a mod go into the bank by their keys; the mod's text/<lang>.json (translations by key) is loaded after them."""
    if not any(str(f).endswith('.py') for f in files): return files
    from .py import lower as PL
    PL.TARGET['exe'] = getattr(prog, 'exe', 'original')     # (which species a partner can be: lower.partner_tree)
    try:
        return lower_py(files, prog, PL)
    finally:
        PL.TARGET['exe'] = 'original'                       # (a `dws lower` or `why` after it reads the original engine's)


def lower_py(files, prog, PL):
    out = []; os.makedirs(PL.LOWERED, exist_ok=True); mods = {}; owners = {}; texts = {}
    claims = PL.Claims(); prog.notes = []     # the run's new NPCs: slots in load order, talk sections (lower.Claims)
    given = {os.path.abspath(str(f)): f for f in files}
    failed = set(); said = set(); lowered = set()     # files whose lowering failed / succeeded; errors already reported (once)
    def report(e):
        for x in getattr(e, 'errors', [e]):
            pos = x.pos or ()
            key = (x.msg, (os.path.abspath(str(pos[0])),) + tuple(pos[1:]) if pos else ())
            if key not in said: said.add(key); prog.errors.append(x)
    def lower_dep(d):
        """A sibling's declarations, even when it is not given itself (its errors once; the importer is then not compiled:
        its `import ...decl.dws` would only repeat that the sibling failed)."""
        d = os.path.abspath(d)
        if d in failed: return False
        if d not in lowered:                      # (lowered again in every run: a declarations file left by an earlier run may be stale)
            try:
                m2, _, _ = PL.lower_file(given.get(d, d), claims=claims)      # (as the writer spelled it, when it was given too)
                if m2.decl_text:
                    open(PL.lowered_path(d, 'decl'), 'w', encoding='utf-8').write(m2.decl_text)
                    PL.py_linemap(PL.lowered_path(d, 'decl'), os.path.relpath(d, ROOT), m2.decl_text, str(given.get(d, d)))
                lowered.add(d)
            except DwsError as e:
                failed.add(d); report(e); return False
        return True
    for f in files:
        if not str(f).endswith('.py'): out.append(f); continue
        try:
            m, sc, mh = PL.lower_file(f, claims=claims)
        except DwsError as e:
            failed.add(os.path.abspath(f)); report(e); continue
        lowered.add(os.path.abspath(f))
        prog.notes += [n for n in m.notes if n not in prog.notes]
        eng = m.engine_errors(prog.max_opcode_level, getattr(prog, 'exe', 'original'), getattr(prog, 'profile', 'original'))
        if eng: prog.errors.extend(eng); continue            # (said at the npc() line, in place of what the back end would say)
        for k, v in list(m.texts.items()) + list(m.named.items()): prog.bank.data.setdefault(k, PL.resolve_escapes(v))
        if m.mod:
            mods[m.mod] = m.mod_dir; t = texts.setdefault(m.mod, {'info': {}, 'used': set(), 'files': set()})
            for k, v in m.text_info.items(): t['info'].setdefault(k, v)
            t['used'] |= m.named_used; t['files'].add(os.path.abspath(f))
        for key in m.ownership():
            here = os.path.relpath(f, ROOT)
            if key in owners and owners[key][0] != m.mod:
                prog.errors.append(DwsError(f'{key[0]} {key[1:]} is owned by two mods: {owners[key][0]} ({owners[key][1]}) and {m.mod} '
                                            f'({here})', None, 'one mod owns an NPC or a screen; the other adds guarded handlers'))
            elif key in owners and owners[key][1] != here:
                prog.errors.append(DwsError(f'{key[0]} {key[1:]} is declared in two files of {m.mod}: {owners[key][1]} and {here}', None,
                                            'one NPC per slot: the next one goes in the next free slot'))
            owners.setdefault(key, (m.mod, here))
        for part, txt in (('decl', m.decl_text), ('script', sc), ('maphead', mh)):
            if txt:
                p = PL.lowered_path(f, part); open(p, 'w', encoding='utf-8').write(txt)
                PL.py_linemap(p, os.path.relpath(os.path.abspath(f), ROOT), txt, str(f))
        if not all([lower_dep(d) for d in m.deps]): continue
        for part, txt in (('script', sc), ('maphead', mh)):
            if txt: out.append(PL.lowered_path(f, part))
    from .py import modtext
    modtext.load_banks(prog, {m: (d or os.path.join(ROOT, 'story', 'mods', m)) for m, d in mods.items()}, texts)
    for mod, mdir in sorted(mods.items()):
        toml = os.path.join(mdir or '', 'mod.toml')
        if mdir and os.path.exists(toml):
            from .minitoml import load_toml
            name = load_toml(toml).get('name')
            if name is not None and name != mod:
                prog.notes.append(f'{os.path.relpath(toml)}: note: name = "{name}" is not the folder\'s name ({mod}): the folder is the '
                                  f'mod\'s name (its save numbers, its text keys, `dws why`); rename one of them')
    return out


def lossless_text(prog, text, where):
    """The lossless form with its keys replaced by the rows of the bank: an option key is one row; an utterance key gives
    the rows of its first page and a SHOW_TEXTBOX with the rows of each further page (a string value is wrapped)."""
    from .textx import is_option
    out = []
    for i, line in enumerate(text.split('\n')):
        m = ROW_KEY.match(line)
        if m:
            key = m.group(2); r = prog.bank.get(key)
            if r is None:
                msg, hint = prog.bank.missing_message(key); raise DwsError(msg, (where, 0, 0), hint)
            if is_option(key):
                if r[0] != 'wrap': raise DwsError(f'text key "{key}" is a menu option: one row', (where, 0, 0))
                out.append(f'{m.group(1)}{BE.quote(r[1])}'); continue
            pages = BE.wrap(r[1], 3, BE.packed_key(key)) if r[0] == 'wrap' else r[1]
            for row in ([] if BE.packed_key(key) else [x for p in pages for x in p]):
                if '{raw ' not in row and not BE.fits(BE.plain(row), packed=False):
                    raise DwsError(f'text key "{key}": row "{row}" is {BE.row_size(BE.plain(row), False)}; the game shows it in '
                                   f'a box other than the dialogue box (box 1-3), whose rows are not packed: '
                                   f'{BE.MAX_UNITS} units and {BE.MAX_PX} px a row with every font', (where, 0, 0),
                                   'shorten the row (docs/mods/font.md "Packed rows")')
            for n, page in enumerate(pages):
                if n: out.append('    SHOW_TEXTBOX')
                out += [f'{m.group(1)}{BE.quote(row)}' for row in page]
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


def prune_runs(max_age_h=24):
    """Removes the run-*/check-* directories of builds older than a day: each build leaves one (about 3 MB), and
    thousands of them filled build/dws with tens of GB."""
    import shutil, time
    limit = time.time() - max_age_h * 3600
    for name in os.listdir(BE.RUN_ROOT):
        path = os.path.join(BE.RUN_ROOT, name)
        if name.startswith(('run-', 'check-')) and os.path.isdir(path):
            try:
                if os.path.getmtime(path) < limit: shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass


def assemble(prog, out_path, exe='original', compact=False, srcmap=None):
    """Builds DG.SCN (and MAPHEAD/.MAP files) in a fresh run directory. Returns (report, run dir).
    compact: bytecode --compact (no garbage tails of the original file, entry 0 one sector), as the story build does."""
    comp = prog.b
    if getattr(comp, 'mh_events', None):
        raise DwsError('`maphead { section(n) ... }` events can be checked but not applied yet: MAPHEAD.SCN is built from `maphead port`/`lossless`')
    BE.ensure_dis()
    os.makedirs(BE.RUN_ROOT, exist_ok=True)
    prune_runs()
    run = tempfile.mkdtemp(prefix='run-', dir=BE.RUN_ROOT)
    comp.run_dir = run; work = os.path.join(run, 'scn')
    if prog.lossless:
        for sid, (_, _, f) in prog.lossless.items():
            if comp.scripts[sid]['events']:
                raise DwsError(f'script {sid} is lossless and also has events', None)
            if sid >= BE.FIRST_NEW_SCRIPT: raise DwsError(f'script {sid}: lossless is only for scripts of the disc (0-221)', None)
    try:
        report = BE.apply(comp, work)
    except BE.BackendError as e:
        raise backend_error(e)
    for sid, (text, line, f) in prog.lossless.items():
        open(os.path.join(work, f'script_{sid:03d}.scn.txt'), 'w', encoding='utf-8').write(lossless_text(prog, text, f))
        report.append(f'script {sid}: lossless (verbatim assembly, text from keys)')
    for sid, (lines, f) in prog.port_texts.items():
        if sid == 'maphead':
            if comp.maphead: raise DwsError('`maphead port` cannot be combined with place/new scripts', None)
            mh = os.path.join(run, 'maphead_port.scn.txt')
            open(mh, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
            comp.maphead = os.path.join(run, 'MAPHEAD.SCN')
            r = BE.bytecode.asm(mh, comp.maphead, maphead_max=BE.MAPHEAD_LIMIT, pack_ascii=BE.PACK_ASCII)
            if r.returncode: raise DwsError('MAPHEAD: ' + (r.stderr.strip() or r.stdout.strip()), None)
            report.append('MAPHEAD: port form'); continue
        if comp.scripts[sid]['events']:
            raise DwsError(f'script {sid} is a port block and also has events', None)
        open(os.path.join(work, f'script_{sid:03d}.scn.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
        report.append(f'script {sid}: port form (one statement per instruction)')
    if prog.maphead_lossless is not None:
        if comp.maphead: raise DwsError('`maphead lossless` cannot be combined with place/new scripts', None)
        mh = os.path.join(run, 'maphead_lossless.scn.txt')
        open(mh, 'w', encoding='utf-8').write(lossless_text(prog, prog.maphead_lossless, 'maphead'))
        comp.maphead = os.path.join(run, 'MAPHEAD.SCN')
        r = BE.bytecode.asm(mh, comp.maphead, maphead_max=BE.MAPHEAD_LIMIT, pack_ascii=BE.PACK_ASCII)
        if r.returncode: raise DwsError('MAPHEAD: ' + (r.stderr.strip() or r.stdout.strip()), None)
        report.append('MAPHEAD: lossless')
    if exe != 'original' and BE.GROUND_PICKUP_MAX:
        from .pickups import rewrite
        try:
            report.append(rewrite(work, comp.maphead or BE.MAPHEAD_SCN, BE.GROUND_PICKUP_MAX))
        except ValueError as e:
            raise DwsError(str(e), None) from e
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    opts = ({'font': 'mods', 'font_glyphs': BE.FONT['glyphs']} if BE.FONT['extra'] else {'font': 'original'})
    opts.update(font_name=BE.FONT['name'], compact=compact, srcmap=srcmap, pack_ascii=BE.PACK_ASCII,
                # a disc built with --relayout (disc() for these executables; build-full.sh sets DWS_RELAYOUT=1): DG.SCN may grow
                grow=exe in ('mods', 'species', 'story-state') or BE.RELAYOUT)
    r = BE.bytecode.asm(work, out_path, opts)
    if r.returncode:                    # (its warnings are about other scripts than the one that failed: the error alone)
        lines = [l for l in (r.stderr.strip() or r.stdout.strip()).split('\n') if l.strip() and not l.startswith('warning:')]
        msg = '\n'.join(l[len('error: '):] if l.startswith('error: ') else l for l in lines)
        raise DwsError(asm_where(msg, work)[-1500:], None)
    report.append(r.stdout.strip()[-1500:])
    if BE.FONT['stripped'] and not any(' are drawn plain' in n for n in getattr(prog, 'notes', [])):     # (said at the .py line)
        report.append('note: drawn plain: %s (%s has no glyphs for them%s)' % (' '.join(sorted(BE.FONT['stripped'])), BE.FONT['of'],
                      '; --exe mods keeps them' if not BE.FONT['extra'] else ''))
    return report, run


def asm_where(msg, work):
    """An error of the assembler at a line of a generated script (`script_178.scn.txt:48: ...`) -> the story file that line
    was compiled from and its section (`house.py, script 178 section 5: ...`), read from the `; --- dws (FILE)` marks the
    back end writes around each event; the generated file is named after it, for whoever wants to look."""
    big = re.match(r'(script_(\d+)\.scn\.txt): (?:the script takes (0x[0-9a-f]+) bytes; offsets are u16|(\d+) bytes; an entry cannot)', msg)
    if big: return script_too_big(int(big.group(2)), int(big.group(3), 16) if big.group(3) else int(big.group(4)), work)
    m = re.match(r'(script_(\d+)\.scn\.txt):(\d+): (.*)', msg, re.S)
    if not m: return 'bytecode: ' + msg
    path = os.path.join(work, m.group(1))
    try: lines = open(path, encoding='utf-8').read().split('\n')
    except OSError: return 'bytecode: ' + msg
    src = sec = None
    for l in reversed(lines[:int(m.group(3))]):
        if src is None and l.strip().startswith('; --- end dws'): src = ''
        mm = re.match(r'\s*; --- dws \((.+)\)\s*$', l)
        if mm and src is None: src = mm.group(1)
        mm = re.match(r'sec(\d+):', l)
        if mm: sec = mm.group(1); break
    where = f'script {int(m.group(2))}' + (f' section {sec}' if sec else '')
    if src:
        from .py.lower import LINEMAP, LOWERED
        lm = LINEMAP.get(os.path.abspath(os.path.join(LOWERED, src)))
        where = (f'{lm[2]}, ' if lm else f'{src}, ') + where
    return f'{where}: {m.group(4)}  (the generated assembly: {os.path.relpath(path, ROOT)}:{m.group(3)})'


def script_too_big(sid, size, work):
    """A script past MAP_SCRIPT_BUFFER (16 384 bytes: the engine loads a screen's script there, and past 65 535 the assembler's
    offsets do not even fit), said in the writer's terms: which screen, how big, the limit, who adds to it, the way out."""
    from dws import bytecode
    from .py import naming as N
    from .py.lower import LINEMAP, LOWERED
    path = os.path.join(work, f'script_{sid:03d}.scn.txt'); files = []
    try:
        for l in open(path, encoding='utf-8'):
            mm = re.match(r'\s*; --- dws \((.+)\)\s*$', l)
            if mm:
                lm = LINEMAP.get(os.path.abspath(os.path.join(LOWERED, mm.group(1))))
                f = lm[2] if lm else mm.group(1)
                if f not in files: files.append(f)
    except OSError: pass
    try:
        _, by = N.disc_screens(); names = N.screen_members()
        screens = [names.get(x, str(x)) for x in by.get(sid, [])]
    except Exception: screens = []
    own = ''
    try:                                    # the script before the mods: the story build's base (or the disc's), assembled
        base = os.path.join(BE.DIS_CACHE, f'script_{sid:03d}.scn.txt')
        n = len(bytecode.assemble_script(open(base, encoding='utf-8').read(), os.path.basename(base), {'quiet': True})[0])
        own = f'; the game\'s own is about {n // 1024} KB of it'
    except Exception: pass
    what = f'script {sid}' + (f' ({", ".join(screens[:3])})' if screens else '')
    return (f'{what} is {size} bytes and a script holds {bytecode.MAP_SCRIPT_MAX} (MAP_SCRIPT_BUFFER: the engine loads a screen\'s '
            f'script there){own}' + (f'; added to it by {", ".join(files)}' if files else '') +
            '\n  hint: shorten the lines (a long talk is the usual cause), or give the scene a screen of its own (new_screen(N, map=...): '
            'a new script)')


def exe_ground_pickup_max(exe_dir):
    """Stable pickup capacity of a manual build's target; old targets have none."""
    header = os.path.abspath(os.path.join(exe_dir, '..', '..', '..', '..', 'include', 'dw', 'item.h'))
    if not os.path.isfile(header): return 0
    m = re.search(r'^#define\s+MOD_GROUND_PICKUP_MAX\s+(\d+)', open(header).read(), re.M)
    return int(m.group(1)) if m else 0


def exe_maphead_max(exe_dir):
    """MAPHEAD_SCRIPT_BUFFER of a built mod executable: MAPHEAD_SCRIPT_MAX of its worktree's include/dw/memmap.h (patch 0091), else the
    GCC tree's older 0x6800 (whole sectors of the original 25 000)."""
    h = os.path.join(exe_dir, '..', '..', '..', '..', 'include', 'dw', 'memmap.h')
    m = re.search(r'^#define\s+MAPHEAD_SCRIPT_MAX\s+(0x[0-9A-Fa-f]+|\d+)', open(h).read(), re.M) if os.path.exists(h) else None
    return int(m.group(1), 0) if m else 0x6800


def disc(prog, name, dg, exe='original'):
    comp = prog.b
    if comp.grown and exe == 'original':
        raise DwsError(', '.join(f'{r} grows from {so} to {sn} sectors' for r, (_, sn, so) in comp.grown.items())
                       + ': the original executable would read it short; build with --exe mods (--relayout)')
    files = ['--file', f'SCN/DG.SCN={dg}']
    if comp.maphead: files += ['--file', f'SCN/MAPHEAD.SCN={comp.maphead}']
    for rel, path in comp.maps.items(): files += ['--file', f'{rel}={path}']
    new_species = sorted({d for _, _, d, *_ in comp.placements if d >= 180})
    if new_species and exe != 'species':
        raise DwsError(f'Digimon {new_species} exist only with --exe species (DIGI.DAT)')
    if exe in ('mods', 'species', 'story-state'):
        exe_dir = BE.exe_dir(exe); rel = os.path.relpath(exe_dir, ROOT)
        if not os.path.exists(os.path.join(exe_dir, 'SLUS_010.32')):
            raise DwsError(f'{rel}/SLUS_010.32 is missing: build that branch first (docs/mods/font.md, docs/mods/species.md)')
        has, _ = BE.fontgen.exe_glyphs(exe_dir)
        if has is not None and has < BE.FONT['glyphs']:          # (compiled with --font-glyphs for a newer executable)
            raise DwsError(f'the text was compiled for {BE.FONT["glyphs"]} extra glyphs and {rel} has {has}: its executable '
                           f'would draw {" ".join(BE.EXTRA_ORDER[has:BE.FONT["glyphs"]])} as other glyphs; rebuild it (docs/mods/font.md)')
        files += ['--from', exe_dir, '--relayout']
        cap = exe_maphead_max(exe_dir)
        if comp.maphead and os.path.getsize(comp.maphead) > cap:
            raise DwsError(f'MAPHEAD.SCN is {os.path.getsize(comp.maphead)} bytes; the executable of {rel} holds {cap} '
                           '(MAPHEAD_SCRIPT_MAX: patch 0091 of mods/patches, which story-state builds on)')
        if exe == 'species': files += ['--add', 'DIGI.DAT=' + BE._species.build(quiet=True)]
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/build-disc.py'), name] + files, check=True)
