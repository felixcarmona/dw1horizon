"""Coverage of the language over the original game: how many instructions, sections and idioms DWS can
express without `asm()`, before (milestone 1: what the retired quest language had) and after (milestone 1b: the registry,
labels, subroutines, port form).

    python3 tools/dws.py coverage            writes build/story-analysis/dws-coverage.csv and
                                             dws-missing-constructs.csv

"Before" is the set of opcodes that had a typed statement (registry.BEFORE) and the IF clause kinds the
old conditions wrote; control flow counts as expressible only in a section whose jumps nest properly
(an `if/else/while` shape): a section with crossing jumps, shared tails or jumps into another section
needed `goto`, which did not exist. "After" is the real thing: the decompiler's lift of every instruction
(`decomp.lift`), so it is exactly what the round trip proves."""
import collections, csv, os, re, sys, tempfile
from dws import bytecode
from . import registry as R, decomp, textx

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(ROOT, 'build', 'story-analysis')
FLOW_BEFORE = {'IF', 'JUMP_TO', 'END_SECTION'}
ENGINE_ARGS = set(range(243, 256))
WALK_START = {'ENTITY_WALK_TO', 'ENTITY_WALK_TO_WITH_CAMERA', 'ENTITY_WALK_TO_ENTITY', 'ENTITY_WALK_TO_ENTITY_WITH_CAMERA',
              'ENTITY_MOVE_TO', 'ENTITY_MOVE_TO_WITH_CAMERA', 'ENTITY_MOVE_TO_ENTITY', 'ENTITY_MOVE_TO_AXIS',
              'ENTITY_MOVE_TO_AXIS_WITH_CAMERA', 'MOVE_CAMERA_TO', 'MOVE_CAMERA_TO_ENTITY', 'MOVE_OBJECT_TO', 'ROTATE_3D_OBJECT'}


def clause_kind(c):
    t = c.split()
    if t and t[0] in ('and', 'or'): t = t[1:]
    neg = bool(t and t[0] == 'not')
    if neg: t = t[1:]
    k = t[0]
    if k == 'trigger': return 'not trigger' if neg else 'trigger'
    if re.fullmatch(r'p\d+', k): return 'pstat'
    if re.fullmatch(r'w\d+', k): return 'wide register'
    return {'item16': 'item', 'card16': 'card', 'move16': 'move'}.get(k, k)


def structured(items):
    """Per section chunk: do all jumps stay inside it and nest (no crossing intervals)?
    Returns {chunk entry label: (ok, reason)}."""
    pos = {}; seq = []                     # instruction index of each label, list of instructions
    for it in items:
        if it[0] == 'label': pos[it[1]] = len(seq)
        else: seq.append(it[1])
    return pos, seq


def chunks(secs, items):
    """Instruction index ranges of the section chunks, in address order."""
    pos, seq = structured(items)
    starts = sorted({pos[l] for _, l, _ in secs if l in pos})
    ranges = []
    for i, s in enumerate(starts):
        ranges.append((s, starts[i + 1] if i + 1 < len(starts) else len(seq)))
    return pos, seq, ranges


def chunk_ok(pos, seq, lo, hi):
    """Jumps of seq[lo:hi]: all targets inside the chunk and properly nested."""
    ivs = []
    for i in range(lo, hi):
        ins = seq[i]; n = ins.name; tg = []
        if n == 'JUMP_TO': tg = [(ins.args[0], True)]
        elif n == 'IF': tg = [(a[5:], False) for a in ins.args if a.startswith(('else ', 'then '))]
        elif n == 'SET_SELECTION': tg = [(a, False) for a in ins.args]
        elif n in ('SWITCH', 'SWITCH_W'): return False, 'switch'
        elif n in ('JUMP_AND_LINK',): continue
        for lab, uncond in tg:
            t = pos.get(lab)
            if t is None or not (lo <= t <= hi): return False, 'jump out of the section'
            a, b = (i + 1 if uncond else i), t
            if b < i and not uncond: return False, 'backward IF'
            ivs.append((min(a, b), max(a, b)))
    ivs.sort()
    for x in range(len(ivs)):
        for y in range(x + 1, len(ivs)):
            a, b = ivs[x]; c, d = ivs[y]
            if c >= b: break
            if c > a and c < b < d: return False, 'crossing jumps (shared tail)'
    return True, ''


def run(out=None, quiet=False):
    out = out or DEFAULT_OUT
    per_op = collections.defaultdict(lambda: {'total': 0, 'before': 0, 'after': 0})
    per_script = []
    clauses = collections.Counter(); clauses_before = collections.Counter()
    constructs = collections.Counter(); notes = {}
    routines = collections.Counter(); engine_writes = collections.Counter()
    jal_targets = collections.Counter(); back_jumps = 0; counter_loops = 0
    par_blocks = 0; sections_total = sections_goto = 0; goto_reasons = collections.Counter()
    with tempfile.TemporaryDirectory() as tmp:
        d, m = textx.disassemble(tmp)
        files = sorted(f for f in os.listdir(d) if re.match(r'script_\d+\.scn\.txt$', f))
        srcs = [(int(re.search(r'\d+', f).group()), os.path.join(d, f)) for f in files if int(re.search(r'\d+', f).group()) != 0] + \
               [('maphead', os.path.join(m, 'maphead.scn.txt'))]
        for sid, path in srcs:
            text = open(path, encoding='utf-8').read()
            secs, items, meta = bytecode.parse_script_text(text, str(sid))
            pos, seq, ranges = chunks(secs, items)
            ok_chunk = [chunk_ok(pos, seq, lo, hi) for lo, hi in ranges]
            idx_ok = {}
            for (lo, hi), (ok, why) in zip(ranges, ok_chunk):
                for i in range(lo, hi): idx_ok[i] = ok
                sections_total += 1
                if not ok: sections_goto += 1; goto_reasons[why] += 1
            n_before = n_after = 0; walks = 0; in_par = 0
            for i, ins in enumerate(seq):
                nm = ins.name; per_op[nm]['total'] += 1
                try:
                    decomp.lift(ins, ['k'] * max(1, len(ins.strings))); after = True
                except decomp.NotLiftable: after = False
                if nm in ('.byte', '.align'): after = False
                if nm == 'IF':
                    ks = [clause_kind(c) for c in ins.args if not c.startswith(('else ', 'then '))]
                    for k in ks: clauses[k] += 1; clauses_before[k] += k in R.BEFORE_CLAUSES
                    b = all(k in R.BEFORE_CLAUSES for k in ks) and idx_ok.get(i, False)
                elif nm in FLOW_BEFORE and nm != 'IF':
                    b = idx_ok.get(i, False) if nm == 'JUMP_TO' else True
                else:
                    b = nm in R.BEFORE
                per_op[nm]['before'] += b; per_op[nm]['after'] += after; n_before += b; n_after += after
                if nm == 'CALL_ROUTINE': routines[int(ins.args[0])] += 1
                if nm in ('SET_PSTAT', 'COPY_PSTAT', 'ADD_TO_PSTAT', 'STORE_RANDOM') and nm != 'COPY_PSTAT':
                    pn = int(ins.args[0][1:])
                    if pn in ENGINE_ARGS: engine_writes[pn] += 1
                if nm == 'JUMP_AND_LINK': jal_targets[ins.args[0]] += 1
                if nm == 'JUMP_TO' and pos.get(ins.args[0], 10 ** 9) <= i: back_jumps += 1
                if nm == 'SET_PSTAT' and ins.args[0] == 'p101': counter_loops += 1
                if nm in WALK_START:
                    walks += 1
                elif nm == 'WAIT_FOR_ENTITY':
                    if walks >= 2: par_blocks += 1
                    walks = 0
            per_script.append((sid, len(seq), n_before, n_after, sum(1 for (ok, _) in ok_chunk if not ok), len(ranges)))
    total = sum(v['total'] for v in per_op.values())
    tb = sum(v['before'] for v in per_op.values()); ta = sum(v['after'] for v in per_op.values())
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'dws-coverage.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['kind', 'name', 'instructions', 'expressible_before', 'expressible_after', 'pct_before', 'pct_after',
                    'sections_needing_goto', 'sections'])
        pct = lambda a, b: f'{100 * a / b:.1f}' if b else ''
        w.writerow(['total', 'all', total, tb, ta, pct(tb, total), pct(ta, total), sections_goto, sections_total])
        for nm, v in sorted(per_op.items(), key=lambda kv: -kv[1]['total']):
            w.writerow(['opcode', nm, v['total'], v['before'], v['after'], pct(v['before'], v['total']), pct(v['after'], v['total']), '', ''])
        for k in sorted(clauses, key=lambda k: -clauses[k]):
            w.writerow(['if-clause', k, clauses[k], clauses_before[k], clauses[k], pct(clauses_before[k], clauses[k]), '100.0', '', ''])
        for sid, n, b, a, g, c in per_script:
            w.writerow(['script', sid, n, b, a, pct(b, n), pct(a, n), g, c])
    missing = []
    for nm, v in per_op.items():
        if v['total'] > v['before'] and nm not in ('IF', 'JUMP_TO'):
            kind = 'opcode without a typed statement'
            missing.append((v['total'] - v['before'], f'{nm}', kind, 'registry command' if v['after'] == v['total'] else 'still missing'))
    if_lost = per_op['IF']['total'] - per_op['IF']['before']; j_lost = per_op['JUMP_TO']['total'] - per_op['JUMP_TO']['before']
    missing.append((if_lost + j_lost, 'goto/labels (IF and JUMP_TO in sections that are not if/while shaped)',
                    f'control flow: {sections_goto} of {sections_total} section chunks ({dict(goto_reasons)})', 'goto, labels, unless'))
    for k, cnt in clauses.items():
        if k not in R.BEFORE_CLAUSES: missing.append((cnt, f'IF clause "{k}"', 'condition not covered', 'has_card/knows/condition/wN'))
    missing.append((sum(jal_targets.values()), 'JUMP_AND_LINK functions', f'{len(jal_targets)} distinct targets', 'gosub, sub fn'))
    missing.append((back_jumps, 'loops / backward jumps', f'{counter_loops} p101 counter loops', 'loop, repeat, for, while, goto'))
    missing.append((per_op['SWITCH']['total'], 'SWITCH tables', 'jump tables', 'match / switch()'))
    missing.append((par_blocks, 'parallel actions (2+ walks/camera moves started, then waited)', 'par block', 'par { }'))
    missing.append((sum(routines.values()), 'CALL_ROUTINE n', f'{len(routines)} distinct routines, calls by number', 'routine("name")'))
    missing.append((sum(engine_writes.values()), 'hidden arguments in engine pstats (p243-p255)', 'writes before CALL_ROUTINE/START_BATTLE', 'lib/engine.dws aliases'))
    missing.append((per_op['DATA']['total'], 'DATA records (cup tables read by C)', 'not instructions', 'data() now; cup {} later'))
    missing.sort(key=lambda r: -r[0])
    with open(os.path.join(out, 'dws-missing-constructs.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['rank', 'occurrences', 'construct', 'detail', 'dws form now'])
        for i, (n, c, dtl, now) in enumerate(missing, 1): w.writerow([i, n, c, dtl, now])
    if not quiet:
        print(f'instructions: {total}; expressible without asm(): before {tb} ({pct(tb, total)} %), after {ta} ({pct(ta, total)} %)')
        print(f'section chunks needing goto (before): {sections_goto} of {sections_total}')
        print('ranked missing constructs (before):')
        for i, (n, c, dtl, now) in enumerate(missing[:20], 1): print(f'  {i:2d}. {n:6d}  {c}  [{dtl}]  -> {now}')
        print(f'wrote {os.path.relpath(os.path.join(out, "dws-coverage.csv"), ROOT)} and dws-missing-constructs.csv')
    return {'total': total, 'before': tb, 'after': ta, 'goto_sections': sections_goto, 'sections': sections_total}
