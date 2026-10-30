"""The readable layer of the story tree (milestone 6): runs the beautifier (lift.py) over the disc, writes the
`story/base` layout with readable events, and measures what it achieved (build/story-analysis/beautifier-coverage.csv).

    python3 tools/dws.py decompile --readable 2              # one script, to stdout
    python3 tools/dws.py decompile-all --readable [-o DIR] [--scripts 2,3,178]
    python3 tools/dws.py readable-coverage                    # the CSV and the numbers

Every section in the output is proven (lift.py); `write` proves the written *files* again by compiling them whole and
comparing each event with the disc's section (flowcmp)."""
import csv, os, re, sys, tempfile
from . import decomp, layout, lift, textx, build as B, flowcmp
from .diag import DwsError

ROOT = B.ROOT
HEAD = ('Readable form of {sid}, made by `dws decompile --readable`. Every event below was compiled and proven equivalent to the\n'
        '// original section (control-flow bisimulation, tools/dws/flowcmp.py); sections that cannot be an event stay in the port form.\n'
        '// Text is by key (text/us/dialogue.json), never the game\'s own words.')


def disc_texts():
    d, m = textx.disassemble()
    scripts = {}
    for f in sorted(os.listdir(d)):
        mm = re.match(r'script_(\d+)\.scn\.txt$', f)
        if mm: scripts[int(mm.group(1))] = (os.path.join(d, f), open(os.path.join(d, f), encoding='utf-8').read())
    return scripts, open(os.path.join(m, 'maphead.scn.txt'), encoding='utf-8').read()


def make_names(mh_text):
    names = lift.Names(); names.load_npcs(mh_text); return names


def prepare_tmp(names):
    """A scratch directory for the proofs, with the file of story/names.toml's aliases that the checked sources import."""
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='lift-', dir=os.path.join(ROOT, 'build'))
    if names.extra_vars or names.extra_flags:
        names.dws_path = os.path.join(tmp, 'names.dws'); write_names_dws(names.dws_path, names)
    return tmp


SCRIPT_LIMIT = 0x4000            # MAP_SCRIPT_BUFFER of the original executable (bytecode.MAP_SCRIPT_MAX)
MAPHEAD_LIMIT = 25000           # MAPHEAD_SCRIPT_BUFFER of the original executable


def lift_disc(only=None, levels=(3, 2, 1, 0), maphead=True, progress=None):
    """-> ({script id: [Lifted]}, [Lifted] of MAPHEAD, names). `only`: script ids to do (None = all)."""
    scripts, mh = disc_texts(); names = make_names(mh)
    tmp = prepare_tmp(names)
    out = {}
    for sid, (path, text) in scripts.items():
        if only is not None and sid not in only: continue
        out[sid] = lift.lift_script_text(text, 'script', sid, path, names, tmp, levels, limit=SCRIPT_LIMIT)
        if progress: progress(sid)
    mhl = lift.lift_script_text(mh, 'maphead', None, 'maphead', names, tmp, levels, limit=MAPHEAD_LIMIT) if maphead and only is None else []
    return out, mhl, names


# ------------------------------------------------------------------------------------------------ source text
def event_header(lf, names):
    n = lf.sec.sid
    if lf.kind == 'maphead': return f'section({n}) replace', None
    if 5 <= n <= 12:
        nm = names.npc_name(lf.sid, n); return f'on talk({nm}) replace', n
    if n == 254: return 'on enter replace', None
    if 51 <= n <= 79: return f'on step({n - 51}) replace', None
    if 80 <= n <= 109: return f'on use({n - 80}) replace', None
    if 1 <= n <= 254 or (lf.sid == 0 and (255 <= n <= 1999 or n == 0)): return f'section({n}) replace', None
    return None, None


def script_source(sid, lifted, names, base=None, names_file=None, entries=None):
    """The .dws text of one script (events of the sections that could be lifted) and the list of sections left out.
    entries: the disc's section table [(id, label)] in header order: written as the script's `sections` list (the build makes
    the script from its sources alone); a repeated id (a dead copy of a section) is `id as LABEL`, its code a shared block."""
    events = []; left = []; seen = set(); imports = set(); npcs = set(); extra = set(); shared = []
    for lf in lifted:
        if lf.level is None: left.append((lf.sec.label, lf.reason)); continue
        if getattr(lf.sec, 'piece', False):
            imports.update(lf.imports); npcs.update(lf.npcs); extra |= lf.extra
            shared.append(lf); continue
        hdr, talk = event_header(lf, names)
        if hdr is None: left.append((lf.sec.label, 'section id outside 1-254')); continue
        if lf.sec.sid in seen:                  # a dead copy (getScriptSection takes the first entry): kept, as a shared block
            imports.update(lf.imports); npcs.update(lf.npcs); extra |= lf.extra; lf.sec.of = f'a dead copy of section {lf.sec.sid}'
            shared.append(lf); continue
        seen.add(lf.sec.sid); imports.update(lf.imports); npcs.update(lf.npcs); extra |= lf.extra
        if talk: npcs.add(talk)
        events.append((lf, hdr))
    lines = [f'// {HEAD.format(sid="MAPHEAD.SCN" if sid is None else f"script {sid} of DG.SCN")}']
    for p in sorted(imports):
        rel = os.path.relpath(p, base or os.getcwd())
        lines.append(f'import "{rel}";')
    if extra and names_file:
        rel = os.path.relpath(names_file, base or os.getcwd())
        lines.append(f'import "{rel}";')
    elif extra: lines += names_decls(names, extra)           # a lone file: the aliases it uses, written in place
    maphead = sid is None
    lines.append('maphead {' if maphead else f'script {sid} {{')
    for n in sorted(npcs): lines.append(f'    npc {names.npc_name(sid, n)} = {n};')
    if npcs: lines.append('')
    if entries:
        first = set(); ents = []
        for n, lab in entries:
            ents.append(str(n) if n not in first else f'{n} as {lab}'); first.add(n)
        lines += ['    // the section table, in the order of the original header', '    sections ' + ', '.join(ents) + ';', '']
    for k, (lf, hdr) in enumerate(events):
        lines.append(f'    {hdr} {{    // section {lf.sec.sid}' + ('' if lf.status == 'readable' else f' ({lf.status})'))
        lines += ['    ' + shared_names(l, lf.sec) for l in lf.body]
        lines.append('    }')
        lines.append('')
    for lf in shared:
        lines.append(f'    shared {lf.sec.label} {{    // ' + (lf.sec.of if lf.sec.of.startswith('a dead') else f'code of {lf.sec.of} that other code jumps to') +
                     ('' if lf.status == 'readable' else f' ({lf.status})'))
        lines += ['    ' + shared_names(l, lf.sec) for l in lf.body]
        lines.append('    }')
        lines.append('')
    if left:
        lines.append('    // left in the port form (`dws decompile ' + ('maphead' if maphead else str(sid)) + '`):')
        for lab, why in left: lines.append(f'    //   {lab}: {why}')
    else:
        while lines and lines[-1] == '': lines.pop()
    lines.append('}')
    from .fmt import format_source
    return format_source('\n'.join(lines) + '\n'), left


ORIGINAL = re.compile(r'\boriginal\((\w+)\)')


def shared_names(line, sec):
    """`original(L)` (the lifter's proof form: a leaf named after the disc's label) -> the name the source gives that code:
    a shared block or label of the script, or a section entry `secN`."""
    canon = getattr(sec, 'canon', None) or {}
    return ORIGINAL.sub(lambda m: canon.get(m.group(1), m.group(1)), line) if 'original(' in line else line


def header_entries(text):
    """[(section id, label)] of a script's header (its `.section` lines), in order."""
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r'^\.section\s+(\d+)\s+(\S+)', text, re.M)]


def names_decls(names, used):
    groups = {}
    for kind, table in (('flag', names.extra_flags), ('var', names.extra_vars)):
        for n, nm in sorted(table.items()):
            if nm in used:
                g, _, leaf = nm.rpartition('.'); groups.setdefault(g, []).append(f'alias {kind} {leaf} = {n};')
    out = []
    for g, decls in sorted(groups.items()):
        out += ([f'group {g} {{'] + ['    ' + d for d in decls] + ['}']) if g else decls
    return out


def write_names_dws(path, names):
    """The aliases of story/names.toml (the pstats and triggers named so far) as one importable file."""
    out = ['// Generated from story/names.toml. Names for state the game already uses (nothing is allocated).']
    groups = {}
    for kind, table in (('flag', names.extra_flags), ('var', names.extra_vars)):
        for n, nm in sorted(table.items()):
            g, _, leaf = nm.rpartition('.')
            groups.setdefault(g, []).append(f'alias {kind} {leaf} = {n};')
    for g, decls in sorted(groups.items()):
        if g: out += [f'pub group {g} {{'] + ['    pub ' + d for d in decls] + ['}']
        else: out += ['pub ' + d for d in decls]
    open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')


# ------------------------------------------------------------------------------------------------ proof of the written files
def check_file(path, lifted, kind='script', sid=None):
    """Compiles a written file whole and compares each of its events with the original section. -> number of events proven."""
    prog = B.compile_sources(path if isinstance(path, list) else [path])
    where = 'MAPHEAD' if isinstance(path, list) else path
    events = getattr(prog.b, 'mh_events', []) if kind == 'maphead' else prog.b.scripts[sid]['events']
    shared = getattr(prog.b, 'mh_shared', []) if kind == 'maphead' else prog.b.scripts[sid].get('shared', [])
    by = {}; pieces = {}
    for lf in lifted:
        if lf.level is None: continue
        if getattr(lf.sec, 'piece', False) or lf.sec.sid in by: pieces[lf.sec.label] = lf      # a shared block, or a dead copy
        else: by[lf.sec.sid] = lf
    n = 0
    for sec, rep, code, ents, p in events:
        lf = by[sec]
        got = prog.b.gen_event(sec, rep, code, ents, p)
        if not flowcmp.compare(canonical(lf.sec.lines, lf.sec), from_source(got))['equal']:
            raise DwsError(f'{where}: section {sec} is not equivalent to the original', None)
        n += 1
    for name, code, p in shared:
        lf = pieces.get(name)
        if lf is None: raise DwsError(f'{where}: shared {name} is not code of the original', None)
        if not flowcmp.compare(canonical(lf.sec.lines, lf.sec), from_source(code))['equal']:
            raise DwsError(f'{where}: shared {name} is not equivalent to the original', None)
        n += 1
    return n


LABEL_DEF = re.compile(r'^([A-Za-z_]\w*):')
WORD = re.compile(r'\b[A-Za-z_]\w*\b')


def canonical(lines, sec):
    """The original's asm lines with every label named as the source names that code (`sec.canon`): two labels of one
    address are one name, so the original and the compiled source meet on the same leaves."""
    canon = getattr(sec, 'canon', None) or {}
    if not canon: return lines
    out = []
    for l in lines:
        m = LABEL_DEF.match(l)
        if m: out.append(canon.get(m.group(1), m.group(1)) + ':' + l[m.end():]); continue
        if l.startswith('    ') and not flowcmp.ROW.match(l):
            code, sep, com = l.partition(';')
            head = re.match(r'^(\s+[A-Z][A-Z0-9_]*)(.*)$', code)
            if head: l = head.group(1) + WORD.sub(lambda w: canon.get(w.group(0), w.group(0)), head.group(2)) + sep + com
        out.append(l)
    return out


def from_source(lines):
    """Compiled source: the shared code's labels `sh_NAME` are the original's names."""
    return [re.sub(r'\bsh_(\w+)', r'\1', l) if not flowcmp.ROW.match(l) else l for l in lines]


def write(out_root, lifted, mhl, names, stats=None, check=True, root_readme=True):
    """Writes the readable layout (same folders as `decompile-all`): zones/<zone>/s<ID>-<screens>/script.dws + README.md.
    root_readme=False leaves out_root/README.md alone (story/base, whose README is committed: tools/dws/basebuild.py)."""
    scripts, mh = disc_texts()
    os.makedirs(os.path.join(out_root, 'zones'), exist_ok=True)
    for rp, txt in (('README.md', '# base (readable)\n\nThe original game as readable DWS (`dws decompile-all --readable`). Generated; every event is proven '
                                  'equivalent to the disc (`docs/mods/dws.md`, "The beautifier"). Not committed.\n'),
                    (os.path.join('zones', 'README.md'), '# zones\n\nOne folder per zone (the first screen that loads the script); inside, one folder per script.\n')):
        if rp == 'README.md' and not root_readme: continue
        open(os.path.join(out_root, rp), 'w').write(txt)
    nm_path = os.path.join(out_root, 'names.dws')
    if names.extra_vars or names.extra_flags: write_names_dws(nm_path, names)
    zones = {}; index = {}; proven = 0
    for sid, lst in sorted(lifted.items()):
        text = scripts[sid][1]; scr = layout.screens_of(text)
        zone = 'unused' if sid == 0 else (layout.slug(scr[0][1]) if scr else 'libraries')
        sname = f's{sid:03d}' + ('-' + '-'.join(str(a) for a, _ in scr[:3]) if scr else '')
        sdir = os.path.join(out_root, 'zones', zone, sname); os.makedirs(sdir, exist_ok=True)
        src, left = script_source(sid, lst, names, base=sdir, names_file=nm_path, entries=header_entries(text))
        path = os.path.join(sdir, 'script.dws'); open(path, 'w', encoding='utf-8').write(src)
        if check and any(l.level is not None for l in lst): proven += check_file(path, lst, 'script', sid)
        rd = [f'# Script {sid} (readable)', '', f'Screens that load it: {", ".join(f"{a} {b}" for a, b in scr) or "none (a library script)"}.', '',
              '| section | status | lines | instructions |', '|---|---|---|---|']
        for lf in lst:
            rd.append(f'| {lf.sec.label} | {lf.status}{" (" + lf.reason + ")" if lf.reason else ""} | {len(lf.body)} | {len(lf.sec.ins)} |')
        open(os.path.join(sdir, 'README.md'), 'w', encoding='utf-8').write('\n'.join(rd) + '\n')
        index[sid] = path; zones.setdefault(zone, []).append((sname, scr))
    for zone, lst in zones.items():
        rd = [f'# Zone: {zone.replace("-", " ")}', '', 'Scripts of this zone (one folder each):', '']
        for sname, scr in lst: rd.append(f'- `{sname}`: ' + (', '.join(f'{a} {b}' for a, b in scr[:6]) if scr else 'library'))
        open(os.path.join(out_root, 'zones', zone, 'README.md'), 'w', encoding='utf-8').write('\n'.join(rd) + '\n')
    if mhl:
        mdir = os.path.join(out_root, 'maphead'); os.makedirs(mdir, exist_ok=True)
        paths = []
        for lf in mhl:
            if lf.level is None or lf.sec.sid is None: continue
            n = lf.sec.sid
            fn = (f'screen{n:03d}' if n <= 254 else f'global-{n:04d}') + '.dws'
            src, _ = script_source(None, [lf], names, base=mdir, names_file=nm_path)
            path = os.path.join(mdir, fn); open(path, 'w', encoding='utf-8').write(src); paths.append(path)
        pieces = [lf for lf in mhl if lf.level is not None and getattr(lf.sec, 'piece', False)]
        # MAPHEAD's section table and its shared code (one namespace for all its files): maphead/maphead.dws
        src, _ = script_source(None, pieces, names, base=mdir, names_file=nm_path, entries=header_entries(mh))
        path = os.path.join(mdir, 'maphead.dws'); open(path, 'w', encoding='utf-8').write(src); paths.append(path)
        if check: proven += check_file(paths, mhl, 'maphead')
        rd = ['# MAPHEAD (readable)', '', 'One file per section: `screenNNN.dws` (screen setup) and `global-NNNN.dws` (entry points of the C code).', '',
              '| section | status | lines | instructions |', '|---|---|---|---|']
        for lf in mhl: rd.append(f'| {lf.sec.label} | {lf.status}{" (" + lf.reason + ")" if lf.reason else ""} | {len(lf.body)} | {len(lf.sec.ins)} |')
        open(os.path.join(mdir, 'README.md'), 'w', encoding='utf-8').write('\n'.join(rd) + '\n')
    if stats is not None: stats['proven_events'] = proven
    return index


# ------------------------------------------------------------------------------------------------ coverage
SUGAR = [('say', r'\bsay\('), ('choice', r'\bchoice\b'), ('if', r'\bif \('), ('while', r'\bwhile \('), ('loop', r'\bloop \{'),
         ('battle', r'\bbattle\('), ('walk_away', r'\bwalk_away\('), ('join_city', r'\bjoin_city'), ('recruit', r'\brecruit\('),
         ('named', r'\bengine\.')]


def literal_lines(lf):
    """Lines of the literal (port) form of the section: one statement per instruction plus its labels."""
    return len(lf.sec.ins) + len({i for x in lf.sec.ins for t in lift.targets(x, lf.sec.labels) for i in [lf.sec.labels.get(t, t)]})


def rows(lifted, mhl, py=None):
    """py: {(script | 'maphead', section id | shared name): verdict of the Python view} (tools/dws/py/view.py)."""
    out = []
    for kind, sid, lst in [('DG', s, l) for s, l in sorted(lifted.items())] + [('MAPHEAD', None, mhl)]:
        seen = set()
        for lf in lst:
            t = '\n'.join(lf.body)
            r = {'kind': kind, 'script': '' if sid is None else sid, 'section': lf.sec.label, 'section_id': lf.sec.sid if lf.sec.sid is not None else '',
                 'status': lf.status, 'level': '' if lf.level is None else lf.level, 'instructions': len(lf.sec.ins),
                 'literal_lines': literal_lines(lf), 'readable_lines': len(lf.body) if lf.level is not None else '', 'gotos_left': lf.gotos if lf.level else '', 'same_instructions': ('yes' if lf.same_layout else 'no') if lf.level is not None else '',
                 'reason': lf.reason or ''}
            r['shared'] = 'block' if getattr(lf.sec, 'piece', False) else 'labels' if getattr(lf.sec, 'shared_at', None) else ''
            if py is not None:
                key = 'maphead' if sid is None else sid
                named = getattr(lf.sec, 'piece', False) or (lf.sec.sid in seen)          # a shared block or a dead copy: by its name
                r['py'] = '' if lf.level is None else py.get((key, lf.sec.label if named else lf.sec.sid), '')
            seen.add(lf.sec.sid)
            r['jumps_before'] = sum(1 for x in lf.sec.ins if x.name in ('JUMP_TO', 'IF', 'SET_SELECTION', 'SWITCH', 'SWITCH_W', 'JUMP_AND_LINK'))
            r['original_jumps'] = len(re.findall(r'\b(?:goto|gosub) original\(|\boriginal\(', t)) if lf.level is not None else ''
            r['gotos_after'] = len(re.findall(r'\bgoto\b|\bgosub\b|\bset_selection\(|\bswitch\(', re.sub(r'\b(?:goto|gosub) original\(\w+\)', '', t)))
            for name, rx in SUGAR: r[name] = len(re.findall(rx, t)) if lf.level is not None else ''
            out.append(r)
    return out


def summarize(rs):
    s = {}
    for kind in ('DG', 'MAPHEAD', 'all'):
        every = [r for r in rs if kind == 'all' or r['kind'] == kind]
        sel = [r for r in every if r['shared'] != 'block']            # sections (a shared block is code cut out of one)
        d = {st: sum(1 for r in sel if r['status'] == st) for st in ('readable', 'shared-exit', 'partial', 'literal', 'port-only')}
        lifted = [r for r in every if r['status'] in ('readable', 'shared-exit', 'partial', 'literal')]
        d['sections'] = len(sel); d['shared_blocks'] = len(every) - len(sel)
        d['shared_label_sections'] = sum(1 for r in sel if r['shared'] == 'labels')
        d['literal_lines'] = sum(r['literal_lines'] for r in lifted); d['readable_lines'] = sum(r['readable_lines'] for r in lifted)
        d['saved'] = d['literal_lines'] - d['readable_lines']
        d['same_instructions'] = sum(1 for r in lifted if r['same_instructions'] == 'yes')
        d['jumps_before'] = sum(r['jumps_before'] for r in lifted); d['gotos_after'] = sum(r['gotos_after'] for r in lifted)
        d['original_jumps'] = sum(r['original_jumps'] or 0 for r in lifted)
        d['with_original_jumps'] = sum(1 for r in lifted if r['original_jumps'])
        s[kind] = d
    return s


def write_csv(path, rs):
    cols = ['kind', 'script', 'section', 'section_id', 'status', 'level', 'instructions', 'literal_lines', 'readable_lines', 'gotos_left', 'same_instructions', 'reason', 'shared'] + \
        (['py'] if rs and 'py' in rs[0] else []) + ['jumps_before', 'gotos_after', 'original_jumps'] + [n for n, _ in SUGAR]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in rs: w.writerow(r)


def run_coverage(out=None, quiet=False):
    lifted, mhl, names = lift_disc()
    tmp = tempfile.mkdtemp(prefix='cov-', dir=os.path.join(ROOT, 'build'))
    try:                                        # the Python view's verdict of each section (the `py` column)
        write(tmp, lifted, mhl, names, check=False)
        from .py import view as PV
        py = PV.write_base(tmp, names)
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
    rs = rows(lifted, mhl, py); sm = summarize(rs)
    path = os.path.join(out or os.path.join(ROOT, 'build', 'story-analysis'), 'beautifier-coverage.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True); write_csv(path, rs)
    if not quiet:
        for k, d in sm.items():
            pyc = {v: sum(1 for r in rs if (k == 'all' or r['kind'] == k) and r.get('py') == v) for v in ('clean', 'raw', 'hatch', 'literal')}
            print(f'{k}: Python view {pyc}')
            print(f'{k}: {d["sections"]} sections: {d["readable"]} readable, {d["shared-exit"]} shared-exit, {d["partial"]} partial, {d["literal"]} literal, {d["port-only"]} port-only; '
                  f'{d["literal_lines"]} -> {d["readable_lines"]} lines ({d["saved"]} saved); control-flow jumps {d["jumps_before"]} -> gotos {d["gotos_after"]} (+ {d["original_jumps"]} `original(L)` jumps in {d["with_original_jumps"]} sections); '
                  f'{d["same_instructions"]} sections compile to the very same instruction stream')
        print(os.path.relpath(path, ROOT))
    return sm, rs
