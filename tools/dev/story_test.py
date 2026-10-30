#!/usr/bin/env python3
"""Behavioural tests for the story scripts: run a scenario on a disc, trace what the script engine does,
and compare the trace of two discs (milestone M3 of docs/reference/story-engine.md, see docs/developing.md).

  story_test.py list                                   scenarios and their recorded digests
  story_test.py disc NAME [--dws | --mutate S:SEC:REL=HEX ...]
                                                    builds a disc besides the original: `dws` = DG.SCN and MAPHEAD recompiled by
                                                    dws from the decompiled sources; a mutant = the original with bytes patched
                                                    (negative control: the differential runner must flag it)
  story_test.py boot                                   creates the start state (continue from the memory card, ~2 min), once
  story_test.py run SCENARIO [--disc NAME] [-o FILE]   runs one scenario, prints the canonical trace summary
  story_test.py check [SCENARIO ...] [--discs orig,dws] [--reps 2] [--record]
                                                    runs every scenario on every disc, `reps` times each; reports determinism
                                                    (reps equal), equality between discs and against the stored digest
  story_test.py record SCENARIO ...                    runs on the original disc twice and stores the digest in the scenario file
  story_test.py diff A.trace B.trace [--timing]        compares two raw traces
  story_test.py offline                                the checks that need no emulator (selftest.sh)

Needs the emulator (EMU_PORT=NNNN story_test.py ..., one instance at a time). Always runs with `-interpreter -debugger`:
Lua breakpoints only fire there. Scenarios are JSON (lines starting with // are comments) in tools/dws/testing/scenarios/.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, bisect, hashlib, json, os, re, struct, subprocess, sys, time

ROOT = _DEV_ROOT
os.environ.setdefault('EMU_PORT', '38020')   # a port of its own: never the 38090 of interactive sessions
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import symbols as dwsyms; from dws import bytecode

WORK = os.path.join(ROOT, 'build/dwstest')
SCEN_DIR = os.path.join(ROOT, 'tools/dws/testing/scenarios')
LUA = os.path.join(ROOT, 'tools/dev/story_trace.lua')
ORIG_CUE = os.path.join(ROOT, 'Digimon World (USA).cue')
CARD = os.path.join(ROOT, 'build/states/file-city.mcd')
BOOT_STATE = os.path.join(WORK, 'boot.state')
DISCS = os.path.join(WORK, 'discs.json')
FPS = 60

# ---------------------------------------------------------------------------------------------------
# addresses

FUNCS = 'gameLoop callScriptSection playSound playMusic startBattle rand customRandom scriptInstructionFBtoFF ' \
        'scriptInstruction10to27 scriptInstruction28to3F scriptInstruction46to58 scriptInstruction5Ato5F scriptInstruction64to7E'.split()
VARS = 'SCRIPT_POINTER ACTIVE_SCRIPT MAPHEAD_SCRIPT_PTR ACTIVE_MAP_SCRIPT ACTIVE_INSTRUCTION TAMER_SUB_STATE TARGET_MAP ' \
       'CURRENT_EXIT TAMER_STATE NPC_ENTITIES TAMER_POSITION_DATA STORED_TAMER_POS TAMER_ENTITY IS_SCRIPT_PAUSED ' \
       'CURRENT_SCREEN MAPHEAD_SCRIPT_BUFFER SCRIPT_OFFSET_TABLE SCRIPT_STATE CURRENT_SCRIPT_ID MONEY'.split()
# regions diffed while tracing: name -> (symbol expression, length). Everything a script or the engine routines it calls can change
# and that does not change by itself every frame (the clock and the care timers are left out on purpose).
WATCH = [('script_saved', 'SCRIPT_STATE', 380, True), ('script_session', 'SCRIPT_STATE+380', 221, False), ('money', 'MONEY', 4), ('merit', 'MERIT', 2), ('screen', 'CURRENT_SCREEN', 1),
         ('script_id', 'CURRENT_SCRIPT_ID', 2), ('inventory', 'INVENTORY', 0x5B), ('partner_stats', 'PARTNER_ENTITY+0x38', 0x20),
         ('partner_moves', 'PARTNER_ENTITY+0x58', 16), ('battles', 'BATTLES_STARTED', 2)]
# script_saved = cards, triggers and the pstats 0-34 that the memory card keeps; script_session = the other pstats (45-93 variables of
# the story, 94-99 scratch, 100-255 the scripts' own registers): their changes are traced, but their value at a checkpoint is not part
# of the digest (a STORE_DATE during the untraced setup leaves a clock-dependent value there). The call stack after them is not watched.


WATCH = [(w + (True,))[:4] if len(w) == 3 else w for w in WATCH]


def phys(expr):
    return dwsyms.resolve(expr, 'orig') & 0x1FFFFF


def addresses():
    return {n: phys(n) for n in FUNCS + VARS}


# ---------------------------------------------------------------------------------------------------
# emulator

def emu_mod():
    from tools.dev import emulator as emu
    return emu


def emulator_disc():
    E = emu_mod(); st = E.state()
    return os.path.basename(st['disc']) if st and E.alive(st) else None


def start_emulator(cue, card=True):
    """Starts the emulator on `cue` (stopping a different one first). Interpreter + debugger, fresh or given memory card."""
    E = emu_mod(); st = E.state()
    if st and E.alive(st):
        if os.path.abspath(st['disc']) == os.path.abspath(cue): return
        E.stop()
    os.environ['EMU_ARGS'] = '-interpreter -debugger'
    if card:
        os.makedirs(E.HOME, exist_ok=True)
        import shutil; shutil.copy(CARD, os.path.join(E.HOME, 'memcard1.mcd'))
    E.start(cue, keep_cards=card)
    time.sleep(2)


def lua_file(code, name='x'):
    E = emu_mod(); os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, f'{name}-{E.PORT}.lua'); open(p, 'w').write(code)
    import urllib.parse
    return E.api('/api/v1/lua/eval?file=' + urllib.parse.quote(p), timeout=60).decode()


def pause(): emu_mod().api('/api/v1/execution-flow?function=pause')
def resume(): emu_mod().api('/api/v1/execution-flow?function=start')


def load_state(path):
    import urllib.parse
    r = emu_mod().api('/api/v1/lua/load?file=' + urllib.parse.quote(os.path.abspath(path)), timeout=120).decode()
    if not r.startswith('ok'): raise RuntimeError(r)


def peek(phys_addr, n):
    return emu_mod().api('/api/v1/cpu/ram/raw')[phys_addr:phys_addr + n]


def poke(phys_addr, data):
    emu_mod().api(f'/api/v1/cpu/ram/raw?offset={phys_addr}&size={len(data)}', data=bytes(data))


# ---------------------------------------------------------------------------------------------------
# discs

def load_discs():
    d = {'orig': {'cue': ORIG_CUE, 'dg': os.path.join(ROOT, 'extracted/SCN/DG.SCN'),
                  'maphead': os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')}}
    if os.path.exists(DISCS): d.update(json.load(open(DISCS)))
    return d


def save_disc(name, spec):
    d = json.load(open(DISCS)) if os.path.exists(DISCS) else {}
    d[name] = spec; os.makedirs(WORK, exist_ok=True); json.dump(d, open(DISCS, 'w'), indent=1)


def container_entries(b):
    offs = []; p = 0
    while True:
        o = struct.unpack_from('<I', b, p)[0]; offs.append(o); p += 4
        if len(offs) > 1 and o >= len(b): break
        if len(offs) > 600: break
    return offs


class Scripts:
    """The scripts of a disc (DG.SCN entries plus MAPHEAD as script 0), with the section table of each."""

    def __init__(self, dg, maphead):
        b = open(dg, 'rb').read(); offs = container_entries(b)
        self.raw = {i: b[offs[i]:offs[i + 1]] for i in range(1, len(offs) - 1)}
        self.raw[0] = open(maphead, 'rb').read()
        self._sec = {}

    def sections(self, sid):
        if sid not in self._sec:
            _, secs = bytecode.parse_header(self.raw[sid])
            self._sec[sid] = sorted((off, s) for s, off in secs)
        return self._sec[sid]

    def locate(self, sid, ip):
        """(section id, offset inside the section) of address ip in script sid."""
        secs = self.sections(sid); k = bisect.bisect_right([o for o, _ in secs], ip) - 1
        if k < 0: return None, ip
        # several section ids can share one address: the smallest id names it
        off = secs[k][0]; sid_ = min(s for o, s in secs if o == off)
        return sid_, ip - off


def build_dws_disc(name='dws'):
    """DG.SCN and MAPHEAD recompiled by dws from the decompiled sources, on a disc."""
    from dws import decomp, build as B, textx
    os.makedirs(WORK, exist_ok=True)
    bank = os.path.join(WORK, 'orig.en.json'); textx.write_bank(textx.extract(), bank)
    scripts, mh, _ = decomp.decompile_all(); srcs = []
    d = os.path.join(WORK, 'dws-src'); os.makedirs(d, exist_ok=True)
    for sid, src in scripts.items():
        p = os.path.join(d, f's{sid:03d}.dws'); open(p, 'w', encoding='utf-8').write(src); srcs.append(p)
    p = os.path.join(d, 'maphead.dws'); open(p, 'w', encoding='utf-8').write(mh); srcs.append(p)
    prog = B.compile_sources(srcs, text=[bank])
    dg = os.path.join(WORK, f'{name}-DG.SCN'); B.assemble(prog, dg)
    import shutil; mhp = os.path.join(WORK, f'{name}-MAPHEAD.SCN'); shutil.copy(prog.b.maphead, mhp)
    return dg, mhp


def build_disc(name, dg, maphead):
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/build-disc.py'), name, '--file', f'SCN/DG.SCN={dg}',
                    '--file', f'SCN/MAPHEAD.SCN={maphead}'], check=True, stdout=subprocess.DEVNULL)
    save_disc(name, {'cue': os.path.join(ROOT, f'build/{name}.cue'), 'dg': dg, 'maphead': maphead})
    print(f'disc {name}: build/{name}.cue')


def compact_disc(name):
    """The original scripts disassembled and assembled again with --compact: same code, but the entries of DG.SCN sit at other
    offsets (garbage tails dropped), so the offset table and the file differ. A relayout control for the runner."""
    d = os.path.join(WORK, f'{name}-dis'); os.makedirs(d, exist_ok=True)
    scn = os.path.join(ROOT, 'tools/dws/bytecode/__main__.py')
    subprocess.run([sys.executable, scn, 'dis', os.path.join(ROOT, 'extracted/SCN/DG.SCN'), d], check=True, stdout=subprocess.DEVNULL)
    dg = os.path.join(WORK, f'{name}-DG.SCN')
    subprocess.run([sys.executable, scn, 'asm', d, dg, '--compact'], check=True, stdout=subprocess.DEVNULL)
    return dg, os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')


def mutate(dg, maphead, edits, name):
    """Negative control: the original scripts with bytes patched. edit = 'script:section:rel=HEX' (section -1: absolute offset)."""
    sc = Scripts(dg, maphead); b = bytearray(open(dg, 'rb').read()); mh = bytearray(open(maphead, 'rb').read())
    offs = container_entries(bytes(b))
    for e in edits:
        loc, hx = e.split('='); s, sec, rel = [int(x, 0) for x in loc.split(':')]
        base = dict((sid, off) for off, sid in sc.sections(s))[sec] if sec >= 0 else 0
        data = bytes.fromhex(hx)
        if s == 0: mh[base + rel:base + rel + len(data)] = data
        else:
            o = offs[s] + base + rel; b[o:o + len(data)] = data
    d = os.path.join(WORK, f'{name}-DG.SCN'); m = os.path.join(WORK, f'{name}-MAPHEAD.SCN')
    open(d, 'wb').write(b); open(m, 'wb').write(mh)
    return d, m


# ---------------------------------------------------------------------------------------------------
# scenarios

def read_json(path):
    text = ''.join(l for l in open(path) if not l.lstrip().startswith('//'))
    return json.loads(text)


def scenarios(names=None):
    out = {}
    if not os.path.isdir(SCEN_DIR): return out
    for f in sorted(os.listdir(SCEN_DIR)):
        if f.endswith('.json'):
            s = read_json(os.path.join(SCEN_DIR, f)); s['_path'] = os.path.join(SCEN_DIR, f); out[s['name']] = s
    if names:
        miss = [n for n in names if n not in out]
        if miss: sys.exit('unknown scenario(s): ' + ' '.join(miss) + '; known: ' + ' '.join(out))
        out = {n: out[n] for n in names}
    return out


SIZES = {'ACTIVE_INSTRUCTION': 1, 'IS_SCRIPT_PAUSED': 4, 'TAMER_STATE': 1, 'CURRENT_SCREEN': 1, 'MONEY': 4, 'MAIN_STATE': 4,
         'TARGET_MAP': 1, 'CURRENT_SCRIPT_ID': 2, 'MERIT': 2, 'HOUR': 2, 'MINUTE': 2}
OPS_ = ('==', '!=', '>=', '<=', '<', '>')


def parse_cond(text):
    """'free and trigger 232 and screen==1 and pstat 7>=2 and MONEY>=500' -> list of {a,n,op,v[,mask]} for the Lua side."""
    out = []
    for part in re.split(r'\s+and\s+', text.strip()):
        part = part.strip(); m = None
        if part == 'free':       # control of the player: no script running, tamer idle
            out += [dict(a=phys('IS_SCRIPT_PAUSED'), n=4, op='==', v=1), dict(a=phys('TAMER_STATE'), n=1, op='==', v=0)]
        elif part == 'idle': out.append(dict(a=phys('IS_SCRIPT_PAUSED'), n=4, op='==', v=1))
        elif part == 'running': out.append(dict(a=phys('IS_SCRIPT_PAUSED'), n=4, op='==', v=0))
        elif (m := re.fullmatch(r'(!?)trigger\s+(\d+)', part)):
            n = int(m.group(2)); out.append(dict(a=phys('SCRIPT_STATE+245') + n // 8, n=1, op='!=' if not m.group(1) else '==', v=0, mask=1 << (n % 8)))
        elif (m := re.fullmatch(r'pstat\s+(\d+)\s*(==|!=|>=|<=|<|>)\s*(\S+)', part)):
            out.append(dict(a=phys('SCRIPT_STATE+345') + int(m.group(1)), n=1, op=m.group(2), v=int(m.group(3), 0)))
        elif (m := re.fullmatch(r'([A-Za-z_][\w+x]*)(?::(\d))?\s*(==|!=|>=|<=|<|>)\s*(\S+)', part.replace('screen', 'CURRENT_SCREEN') if part.startswith('screen') else part)):
            sym = m.group(1); size = int(m.group(2)) if m.group(2) else SIZES.get(sym, 1)
            out.append(dict(a=phys(sym), n=size, op=m.group(3), v=int(m.group(4), 0)))
        else: raise ValueError(f'condition not understood: {part!r}')
    return out


def parse_step(text):
    """The step language of scenarios (all counts are game frames):
       wait N | press BTN [N] | until COND [press BTN [N] [every G]] [max M] | talk until COND [max M]
       warp SCREEN [EXIT] | approach SLOT [DIST] | npc SID [DIST] | move X Z | tile V | exit E | door E SCREEN | doortile V SCREEN | camera [SPEED] | call SCRIPT SECTION [EVENT] | trigger N 0|1 | pstat N V
       poke SYMBOL HEX | trace on|off | mark NAME | end"""
    w = text.split()
    k = w[0]
    if k == 'wait': return dict(t='wait', n=int(w[1]))
    if k == 'press': return dict(t='press', b=w[1].upper(), n=int(w[2]) if len(w) > 2 else 3)
    soft = k in ('until?', 'talk?')
    if soft: k = k[:-1]; text = k + text[len(k) + 1:]; w = text.split()
    if k == 'talk' and len(w) > 3 and w[1] == 'after' and w[2] == 'battle':          # talk after battle N [max M]: read the boxes until the N-th battle of the run has started and is over
        mx = int(w[w.index('max') + 1]) if 'max' in w else 9000
        return dict(t='talk', c=[], nb=int(w[3]), max=mx, soft=soft)
    if k in ('until', 'talk'):
        body = text.split(None, 1)[1] if k == 'until' else text.split(None, 2)[2]
        if k == 'talk' and w[1] != 'until': raise ValueError(text)
        mx = 3000; m = re.search(r'\s+max\s+(\d+)\s*$', body)
        if m: mx = int(m.group(1)); body = body[:m.start()]
        s = dict(t=k, max=mx); m = re.search(r'\s+press\s+(\w+)(?:\s+(\d+))?(?:\s+every\s+(\d+))?\s*$', body)
        if m:
            s.update(b=m.group(1).upper(), n=int(m.group(2) or 3), gap=int(m.group(3) or 40)); body = body[:m.start()]
        s['c'] = parse_cond(body); s['soft'] = soft; return s
    if k == 'warp': return dict(t='warp', screen=int(w[1]), exit=int(w[2]) if len(w) > 2 else 0)
    if k == 'warpif':          # warpif SCREEN [EXIT] skip K: warp back to SCREEN if the tamer is not there; if he is, skip the K steps that follow (they wait for the warp)
        return dict(t='warpif', screen=int(w[1]), exit=int(w[2]) if len(w) > 2 and w[2] != 'skip' else 0, skip=int(w[w.index('skip') + 1]) if 'skip' in w else 0)
    sk = int(w[w.index('skip') + 1]) if 'skip' in w and k in ('npc?', 'tile?', 'approach?') else 0          # `npc? SID skip K`: not there -> the K steps after it are skipped too
    if sk: w = w[:w.index('skip')]
    if k in ('npc', 'npc?'):         # npc SID [DIST]: walk up to the NPC whose script id is SID (the section its talk calls), wherever its slot is
        return dict(t='approach', sid=int(w[1]), slot=0, dist=int(w[2]) if len(w) > 2 else 180, optional=k.endswith('?'), et=phys('ENTITY_TABLE'), skip=sk)
    if k in ('approach', 'approach?'): return dict(t='approach', slot=int(w[1]), dist=int(w[2]) if len(w) > 2 else 180, optional=k.endswith('?'), skip=sk)
    if k == 'move': return dict(t='move', x=int(w[1]), z=int(w[2]))
    if k in ('tile', 'tile?', 'exit', 'exit?'):     # tile V: onto the tiles whose trigger value is V; exit E = tile 110+E (the door, walked through)
        v = int(w[1]) + (110 if k.startswith('exit') else 0)
        return dict(t='tile', v=v, a=phys('MAP_COLLISION_DATA'), optional=k.endswith('?'), skip=sk)
    if k == 'call': return dict(t='call', script=int(w[1]), section=int(w[2]), event=int(w[3]) if len(w) > 3 else 1)
    if k in ('door', 'doortile'):          # door E SCREEN [max M]: through exit E until SCREEN is loaded and the tamer free; put back on the exit when a wild battle interrupts the walk
        mx = int(w[w.index('max') + 1]) if 'max' in w else 4000          # doortile V SCREEN [max M]: the same through the tile of section V (51-79) that warps to SCREEN
        return dict(t='door', v=(110 if k == 'door' else 0) + int(w[1]), screen=int(w[2]), a=phys('MAP_COLLISION_DATA'), max=mx)
    if k == 'camera':        # camera [SPEED]: the view is moved to the tamer (createCameraMovement, as the training code does), SPEED frames (default 10)
        return dict(t='camera', fn=phys('createCameraMovement'), target=phys('TAMER_POSITION_DATA') + 0x78, speed=int(w[1]) if len(w) > 1 else 10)
    if k == 'trigger':
        n = int(w[1]); a = phys('SCRIPT_STATE+245') + n // 8
        return dict(t='bitset', a=a, bit=1 << (n % 8), on=int(w[2]) != 0)
    if k == 'pstat': return dict(t='poke', a=phys('SCRIPT_STATE+345') + int(w[1]), hex='%02x' % (int(w[2], 0) & 0xFF))
    if k == 'poke': return dict(t='poke', a=phys(w[1]), hex=w[2])
    if k == 'clock':        # clock H M: hour, minute and the frame counter of the minute (the game clock: 20 frames per minute)
        h, m = int(w[1]), int(w[2])
        return dict(t='multi', steps=[dict(t='poke', a=phys('HOUR'), hex=struct.pack('<h', h).hex()),
                                      dict(t='poke', a=phys('MINUTE'), hex=struct.pack('<h', m).hex()),
                                      dict(t='poke', a=phys('CURRENT_FRAME'), hex=struct.pack('<H', h * 1200 + m * 20).hex()),
                                      dict(t='poke', a=phys('SUBFRAME_COUNT'), hex='0000')])
    if k == 'trace': return dict(t='trace', on=w[1] == 'on')
    if k == 'mark': return dict(t='mark', name=w[1])
    if k == 'end': return dict(t='end')
    raise ValueError(f'step not understood: {text!r}')


def lua_value(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, list): return '{' + ','.join(lua_value(x) for x in v) + '}'
    if isinstance(v, dict): return '{' + ','.join(f'[{json.dumps(k)}]={lua_value(x)}' for k, x in v.items()) + '}'
    raise TypeError(v)


def apply_setup(setup, scripts_of_disc):
    """State written while the emulator is paused, before the scenario starts."""
    A = addresses()
    for k, v in (setup.get('set') or {}).items():
        from tools.dev import game_state as gamestate
        gamestate.apply(_nest(k, v))
    for n, v in (setup.get('triggers') or {}).items():
        n = int(n); a = phys('SCRIPT_STATE+245') + n // 8; b = peek(a, 1)[0]
        poke(a, bytes([(b | (1 << n % 8)) if v else (b & ~(1 << n % 8) & 0xFF)]))
    for n, v in (setup.get('pstats') or {}).items():
        poke(phys('SCRIPT_STATE+345') + int(n), bytes([int(v) & 0xFF]))
    inv = setup.get('items')            # [[item, amount], ...] replaces the inventory
    if inv is not None:
        base = phys('INVENTORY'); types = bytes([i for i, _ in inv]) + b'\xff' * (30 - len(inv))
        amounts = bytes([a for _, a in inv]) + b'\0' * (30 - len(inv))
        poke(base, types); poke(base + 30, amounts); poke(base + 90, bytes([len(inv)]))
    if setup.get('hour') is not None or setup.get('minute') is not None:
        h, m = setup.get('hour', 9), setup.get('minute', 0)
        for sym, v, f in (('HOUR', h, '<h'), ('MINUTE', m, '<h'), ('CURRENT_FRAME', h * 1200 + m * 20, '<H'), ('SUBFRAME_COUNT', 0, '<H')):
            poke(phys(sym), struct.pack(f, v))
    if setup.get('rng') is not None:    # pins customRandom (the BIOS rand() seed is part of the saved state)
        poke(phys('CUSTOM_RNG_VAL1'), struct.pack('<I', setup['rng'][0])); poke(phys('CUSTOM_RNG_VAL2'), struct.pack('<I', setup['rng'][1]))


def _nest(key, v):
    d = {}; cur = d; parts = key.split('.')
    for p in parts[:-1]: cur = cur.setdefault(p, {})
    cur[parts[-1]] = v; return d


def sync_scripts(disc):
    """The state keeps MAPHEAD and the offset table of the disc it was made on; put in RAM those of the disc under test and
    forget the cached screen script, so that it is read again from the mounted disc."""
    A = addresses()
    mh = open(disc['maphead'], 'rb').read(); poke(A['MAPHEAD_SCRIPT_BUFFER'], mh)
    dg = open(disc['dg'], 'rb').read(); offs = container_entries(dg); hdr = dg[:offs[0]]
    poke(A['SCRIPT_OFFSET_TABLE'], hdr[:0x2000])
    poke(A['ACTIVE_MAP_SCRIPT'], b'\xff\xff')


def run_spec(scen, A):
    steps = []
    for s in scen.get('pre', []): steps.append(parse_step(s))
    su = scen.get('setup') or {}
    clk = scen.get('clock') or ([su.get('hour', 9), su.get('minute', 0)] if 'hour' in su or 'minute' in su else [9, 12])
    steps.append(parse_step('clock %d %d' % tuple(clk)))    # the clock moves 1 minute per 20 frames: pin it
    steps.append(dict(t='trace', on=True))
    for s in scen['run']: steps.append(parse_step(s))
    steps = [x for st in steps for x in (st['steps'] if st['t'] == 'multi' else [st])]
    steps += [dict(t='mark', name='final'), dict(t='end')]    # a battle freezes the run earlier (end_on_battle)
    return steps


def run_scenario(scen, disc, out_trace, rep=0):
    """One run of a scenario on the (already started) emulator whose disc is `disc`. Returns the raw trace text."""
    A = addresses(); out_trace = os.path.abspath(out_trace)
    pause(); load_state(os.path.join(WORK, scen.get('start', 'boot') + '.state'))
    sync_scripts(disc); apply_setup(scen.get('setup') or {}, disc)
    watch = [dict(name=n, addr=phys(e), len=ln, digest=dg) for n, e, ln, dg in WATCH]
    S = dict(out=out_trace, A=A, steps=run_spec(scen, A), watch=watch, trace=False, max_frames=scen.get('max_frames', 6000),
             stop_on_battle=bool(scen.get('end_on_battle')))
    if os.path.exists(out_trace): os.remove(out_trace)
    r = lua_file(f'dofile("{LUA}")\nreturn DT.start({lua_value(S)})', 'start')
    if r != 'started': raise RuntimeError('lua: ' + r)
    resume(); t0 = time.time(); limit = S['max_frames'] / FPS * 2.5 + 60
    while True:
        time.sleep(0.5)
        st = lua_file('return tostring(DT.done) .. " " .. tostring(DT.pending_finish)', 'poll').split()
        if st[0] == 'true': break
        if st[1] != 'nil':
            lua_file(f'DT.finish("{st[1]}")', 'fin'); break
        if time.time() - t0 > limit:
            lua_file('DT.finish("host timeout")', 'fin'); time.sleep(1); break
    pause()
    text = open(out_trace).read()
    if re.search(r'^E \d+ battle', text, re.M):
        # frozen inside startBattle with the CD busy: loading a state on top of that hangs, so the next run gets a fresh emulator
        emu_mod().stop()
    return text


# ---------------------------------------------------------------------------------------------------
# trace -> canonical events

INS_CACHE = {}


def label_positions(b, p):
    """Byte offsets (in b) of the u16 label operands of the instruction at p."""
    op = b[p]; pos = []
    if op == 0x10:
        pos = [p + 2 + 2 * k for k in range(b[p + 1])]
    elif op in (0x18, 0x93):
        n = bytecode.u16(b, p + 2); pos = [p + 4 + 2 * k for k in range(n)]
    elif op == 0x19:
        q = p + 2
        while True:
            cop = b[q]; q += 2
            if cop == 0x19: break
            if (cop & 0x38) in (0x10, 0x18): pos.append(q)
            q += bytecode.IF_ARGLEN(cop)
    elif op in bytecode.OPS:
        n = 1
        for f in bytecode.OPS[op][1].split():
            if f == 'l': pos.append(p + n)
            n += bytecode.FSIZE[f]
    return pos


def mnemonic(op):
    if op in bytecode.OPS: return bytecode.OPS[op][0]
    return {0x10: 'SET_SELECTION', 0x18: 'SWITCH', 0x19: 'IF', 0x1A: 'SHOW_TEXTBOX', 0x6B: 'DATA', 0x93: 'SWITCH_W'}.get(op, f'OP_{op:02x}')


def parse_trace(text, scripts):
    """Raw trace -> list of events: dict(kind, key, frame, rand, extra). `key` is the canonical text (layout independent:
    sections and offsets inside sections, operands as a hash with the label fields cleared and the targets named by
    section+offset)."""
    ev = []
    for line in text.splitlines():
        w = line.split(' ')
        k = w[0]
        if k == 'I':
            f, sid, ip, op, rnd, hx = int(w[1]), int(w[2]), int(w[3]), int(w[4], 16), int(w[5]), w[6]
            b = bytearray.fromhex(hx)
            try:
                n, tg = bytecode.instr_length(bytes(b), 0)
            except Exception:
                n = None
            if n is None: n = min(len(b), 4); tg = []
            sec, rel = scripts.locate(sid, ip)
            ops = bytes(b[:n]); targets = []
            for pos in label_positions(ops, 0):
                t = bytecode.u16(ops, pos); ts, tr = scripts.locate(sid, t); targets.append(f'{ts}+{tr}')
                b[pos:pos + 2] = b'\0\0'
            h = hashlib.sha1(bytes(b[:n])).hexdigest()[:8]
            key = f'I {sid}:{sec}+{rel} {mnemonic(op)} #{h}' + (' ->' + ','.join(targets) if targets else '')
            ev.append(dict(kind='I', key=key, frame=f, rand=rnd, raw=ops, sid=sid, sec=sec, rel=rel, op=op))
        elif k == 'W':
            ev.append(dict(kind='W', key=f'W {w[2]}+{w[3]} {w[4]}>{w[5]}', frame=int(w[1])))
        elif k in 'SM':
            ev.append(dict(kind=k, key=f'{k} {w[2]} {w[3]}', frame=int(w[1])))
        elif k == 'B':
            ev.append(dict(kind='B', key=f'B {w[2]}', frame=int(w[1])))
        elif k == 'K':
            ev.append(dict(kind='K', key=f'K {w[2]}', frame=int(w[1])))
        elif k == 'D':
            ev.append(dict(kind='D', key=f'D {w[1]} {hashlib.sha1(bytes.fromhex(w[2])).hexdigest()[:12]}', frame=None, hex=w[2]))
        elif k == 'E':
            ev.append(dict(kind='E', key=f'E {w[2] if len(w) > 2 else ""}'.strip(), frame=int(w[1])))
        elif k == 'Y':          # the battle handler's notes (story_trace.lua: enemy HP set to 0, the frame it ended on)
            ev.append(dict(kind='Y', key=line, frame=int(w[1])))
        elif k == 'X':
            ev.append(dict(kind='X', key=line, frame=None))
    return ev


def canon(events, rand=True):
    """The lines the digest is made of: no frame numbers. With rand=True each instruction carries the number of rand()
    calls made since the first instruction (the count of draws is an L2 observable). Sounds and music before the first
    instruction are the ambient ones of the start state (the partner walking) and are left out, and so is the rand count
    before it: that is what makes the digest the same for two different boot states (docs/developing.md)."""
    out = []; first = None
    for e in events:
        if e['kind'] == 'E': continue
        s = e['key']
        if e['kind'] == 'I':
            if first is None: first = e['rand']
            if rand: s += f' r={e["rand"] - first}'
        elif e['kind'] in 'SM' and first is None: continue
        out.append(s)
    return out


def digest(events, rand=True):
    return hashlib.sha1('\n'.join(canon(events, rand)).encode()).hexdigest()


def first_diff(a, b, scripts=None, context=3):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]: break
    else:
        if len(a) == len(b): return None
        i = n
    lo = max(0, i - context)
    lines = [f'first difference at event {i} (of {len(a)} / {len(b)})']
    for j in range(lo, i): lines.append(f'      {a[j]}')
    lines.append(f'  A:  {a[i] if i < len(a) else "(end)"}')
    lines.append(f'  B:  {b[i] if i < len(b) else "(end)"}')
    return '\n'.join(lines)


def timing(ea, eb):
    """Frame differences between two traces with equal canonical events."""
    fa = [e['frame'] for e in ea if e.get('frame') is not None and e['kind'] != 'E']
    fb = [e['frame'] for e in eb if e.get('frame') is not None and e['kind'] != 'E']
    if len(fa) != len(fb): return None
    d = [y - x for x, y in zip(fa, fb)]
    return dict(max=max((abs(x) for x in d), default=0), first=next((i for i, x in enumerate(d) if x), None), n=len(d))


def describe(events, scripts, limit=60):
    """Readable listing of a trace (the disassembly of each executed instruction)."""
    out = []; shown = 0
    for e in events:
        if e['kind'] == 'I':
            b = e['raw']
            try:
                lines, _ = bytecode.dis_instr(b, 0, len(b), _Labels())
                txt = lines[0]
            except Exception:
                txt = mnemonic(e['op'])
            if len(lines) > 1: txt = lines[0] + ' ' + ' / '.join(x.strip() for x in lines[1:])
            out.append(f'{e["frame"]:>5}  {e["sid"]}:{e["sec"]}+{e["rel"]:<4} {txt[:110]}')
        else:
            out.append(f'{e["frame"] if e.get("frame") is not None else "":>5}  {e["key"][:80]}')
    return out


class _Labels(dict):
    def __missing__(self, k): return f'L{k:x}'


# ---------------------------------------------------------------------------------------------------
# commands

def ensure_boot():
    if not os.path.exists(BOOT_STATE): sys.exit('no start state: run `story_test.py boot` first (about 2 minutes)')


def cmd_boot(a):
    E = emu_mod(); os.makedirs(WORK, exist_ok=True)
    target = os.path.join(WORK, a.name + '.state')
    st = E.state()
    if st and E.alive(st): E.stop()
    start_emulator(ORIG_CUE, card=True)
    seq = os.path.join(ROOT, 'tools/dev/sequences/continue.seq')
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), 'seq', seq], check=True, stdout=subprocess.DEVNULL)
    # wait for control in Jijimon's house
    for _ in range(60):
        ram = E.api('/api/v1/cpu/ram/raw'); A = addresses()
        if ram[A['CURRENT_SCREEN']] == 218 and ram[A['TAMER_STATE']] == 0 and struct.unpack_from('<i', ram, A['IS_SCRIPT_PAUSED'])[0] == 1: break
        time.sleep(2)
    else: sys.exit('the game did not reach control in screen 218')
    time.sleep(3); pause(); sync = lua_file(f'return "ok"', 'x')
    import urllib.parse
    print(E.api('/api/v1/lua/save?file=' + urllib.parse.quote(target), timeout=120).decode())
    E.stop()


def prepare_emulator(disc_name):
    ensure_boot(); disc = load_discs()[disc_name]
    start_emulator(disc['cue']); return disc


def ensure_emulator(disc):
    start_emulator(disc['cue'])


def fmt_scen_result(name, disc, ev, trace_path):
    n = sum(1 for e in ev if e['kind'] == 'I'); w = sum(1 for e in ev if e['kind'] == 'W')
    end = next((e['key'] for e in ev if e['kind'] == 'E'), '?')
    return f'{name} on {disc}: {n} instructions, {w} state changes, ends: {end}'


def cmd_run(a):
    scen = scenarios([a.scenario])[a.scenario]; disc = prepare_emulator(a.disc)
    if a.start: scen['start'] = a.start
    os.makedirs(WORK, exist_ok=True); out = a.o or os.path.join(WORK, f'{a.scenario}.{a.disc}.trace')
    text = run_scenario(scen, load_discs()[a.disc], out)
    sc = Scripts(load_discs()[a.disc]['dg'], load_discs()[a.disc]['maphead']); ev = parse_trace(text, sc)
    print(fmt_scen_result(a.scenario, a.disc, ev, out)); print('digest', digest(ev)); print('trace', out)
    if a.show: print('\n'.join(describe(ev, sc)))
    if a.shot: open(a.shot, 'wb').write(emu_mod().api('/api/v1/screen/still')); print('shot', a.shot)
    if not a.keep: emu_mod().stop()


def cmd_check(a):
    scs = scenarios(a.scenarios); discs = a.discs.split(','); alld = load_discs()
    for d in discs:
        if d not in alld: sys.exit(f'unknown disc {d} (story_test.py disc ...)')
    res = {}                   # (scenario, disc) -> [events per rep]
    os.makedirs(WORK, exist_ok=True)
    for d in discs:
        prepare_emulator(d); sc = Scripts(alld[d]['dg'], alld[d]['maphead'])
        for name, scen in scs.items():
            for r in range(a.reps if d == discs[0] else a.reps_other):
                out = os.path.join(WORK, f'{name}.{d}.{r}.trace')
                ensure_emulator(alld[d])
                text = run_scenario(scen, alld[d], out, r)
                ev = parse_trace(text, sc); res.setdefault((name, d), []).append(ev)
                print(f'  {fmt_scen_result(name, d, ev, out)}', flush=True)
        emu_mod().stop()
    bad = 0; caught = {}; mutants = a.mutants.split(',') if a.mutants else []
    print('\nresults')
    for name, scen in scs.items():
        for d in discs:
            reps = res[(name, d)]
            full = [canon(e) + [f'@{x["frame"]}' for x in e if x.get('frame') is not None] for e in reps]
            det = all(f == full[0] for f in full)
            det_ev = all(canon(e) == canon(reps[0]) for e in reps)
            tag = 'identical (events and frames)' if det else ('events identical, frames differ' if det_ev else 'DIFFERENT between repetitions')
            print(f'  {name:28} {d:8} ' + (f'repeat x{len(reps)}: {tag}' if len(reps) > 1 else '1 run'))
            if not det_ev: bad += 1; print(first_diff(canon(reps[0]), canon(reps[1])) if len(reps) > 1 else '')
        base = discs[0]; eb = res[(name, base)][0]
        for d in discs[1:]:
            ed = res[(name, d)][0]; df = first_diff(canon(eb), canon(ed))
            if d in mutants:       # negative control: a difference is the expected result
                caught[d] = caught.get(d, 0) + (df is not None)
                print(f'  {name:28} {base} vs {d} (mutant): ' + ('difference seen at ' + df.splitlines()[0].split(' at ')[-1] if df else 'same trace (the mutation is not on this path)'))
                continue
            if df is None:
                t = timing(eb, ed)
                print(f'  {name:28} {base} vs {d}: SAME trace ({len(eb)} events)' + (f'; frame drift max {t["max"]}' if t else ''))
            else:
                from dws.testing import sweep as SW            # the sweep's normalized trace: code positions, JUMP_TO and IF (pure tests) dropped, every effect kept
                ra, rd = SW.relaxed_events(eb), SW.relaxed_events(ed)
                fx = lambda ev: [e for e in ev if e['kind'] != 'I']           # the effects (writes, sounds, music, boxes, screens) with their frames
                t = timing(fx(eb), fx(ed))
                if ra == rd and t is not None:
                    print(f'  {name:28} {base} vs {d}: SAME behaviour (relaxed: {len(ra)} events, the code moved; frame drift max {t["max"]})')
                else:
                    bad += 1; print(f'  {name:28} {base} vs {d}: DIFFERENT\n' + df)
        if a.record and base == 'orig' and len(res[(name, base)]) > 1 and canon(res[(name, base)][0]) == canon(res[(name, base)][1]):
            store_digest(scen, digest(eb), sum(1 for e in eb if e['kind'] == 'I')); scen['expect'] = {'digest': digest(eb)}
            print(f'  {name:28} digest recorded {digest(eb)[:12]}')
        exp = scen.get('expect', {}).get('digest')
        if exp and base == 'orig' and not a.record:
            ok = digest(eb) == exp; print(f'  {name:28} recorded digest: ' + ('matches' if ok else 'DIFFERS')); bad += (not ok)
    for d in mutants:
        print(f'mutant {d}: caught in {caught.get(d, 0)} of {len(scs)} scenarios'); bad += caught.get(d, 0) == 0
    sys.exit(1 if bad else 0)


def store_digest(scen, d, n):
    txt = open(scen['_path']).read()
    exp = f'"expect": {{"digest": "{d}", "instructions": {n}}}'
    if '"expect"' in txt: txt = re.sub(r'"expect":\s*\{[^}]*\}', exp, txt)
    else: txt = re.sub(r'\n\}\s*$', f',\n  {exp}\n}}\n', txt.rstrip() + '\n')
    open(scen['_path'], 'w').write(txt)


def cmd_record(a):
    scs = scenarios(a.scenarios); disc = prepare_emulator('orig'); sc = Scripts(disc['dg'], disc['maphead'])
    for name, scen in scs.items():
        evs = []
        for r in range(2):
            out = os.path.join(WORK, f'{name}.orig.{r}.trace'); ensure_emulator(disc); evs.append(parse_trace(run_scenario(scen, disc, out, r), sc))
        if canon(evs[0]) != canon(evs[1]):
            print(f'{name}: NOT deterministic, digest not recorded\n' + str(first_diff(canon(evs[0]), canon(evs[1])))); continue
        d = digest(evs[0]); store_digest(scen, d, sum(1 for e in evs[0] if e['kind'] == 'I')); print(f'{name}: recorded {d} ({len(canon(evs[0]))} events)')
    emu_mod().stop()


def cmd_diff(a):
    d = load_discs()['orig']; sc = Scripts(d['dg'], d['maphead'])
    ea = parse_trace(open(a.a).read(), sc); eb = parse_trace(open(a.b).read(), sc)
    df = first_diff(canon(ea), canon(eb))
    print('traces identical' if df is None else df)
    if df is None and a.timing: print('timing', timing(ea, eb))
    sys.exit(0 if df is None else 1)


def cmd_list(a):
    for n, s in scenarios().items():
        e = s.get('expect', {})
        print(f'{n:28} {e.get("digest", "-")[:12]:12} {s.get("doc", "")[:70]}')


def cmd_disc(a):
    os.makedirs(WORK, exist_ok=True); o = load_discs()['orig']
    if a.dws: dg, mh = build_dws_disc(a.name)
    elif a.compact: dg, mh = compact_disc(a.name)
    elif a.mutate: dg, mh = mutate(o['dg'], o['maphead'], a.mutate, a.name)
    else: sys.exit('--dws or --mutate')
    build_disc(a.name, dg, mh)


def cmd_offline(a):
    from tools.dev.story_test_offline import run
    run()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list').set_defaults(f=cmd_list)
    p = sub.add_parser('disc'); p.add_argument('name'); p.add_argument('--dws', action='store_true')
    p.add_argument('--compact', action='store_true'); p.add_argument('--mutate', action='append'); p.set_defaults(f=cmd_disc)
    p = sub.add_parser('boot'); p.add_argument('--name', default='boot', help='state name (build/dwstest/NAME.state)'); p.set_defaults(f=cmd_boot)
    p = sub.add_parser('run'); p.add_argument('scenario'); p.add_argument('--disc', default='orig'); p.add_argument('-o')
    p.add_argument('--show', action='store_true'); p.add_argument('--keep', action='store_true', help='leave the emulator running (paused)')
    p.add_argument('--shot'); p.add_argument('--start', help='start state name (default boot)'); p.set_defaults(f=cmd_run)
    p = sub.add_parser('check'); p.add_argument('scenarios', nargs='*'); p.add_argument('--discs', default='orig,dws')
    p.add_argument('--reps', type=int, default=2, help='repetitions on the first disc (determinism)')
    p.add_argument('--reps-other', type=int, default=1, help='repetitions on the other discs')
    p.add_argument('--mutants', help='discs that must differ (negative controls), comma separated')
    p.add_argument('--record', action='store_true', help='store the digest of the first disc in the scenario files'); p.set_defaults(f=cmd_check)
    p = sub.add_parser('record'); p.add_argument('scenarios', nargs='+'); p.set_defaults(f=cmd_record)
    p = sub.add_parser('diff'); p.add_argument('a'); p.add_argument('b'); p.add_argument('--timing', action='store_true'); p.set_defaults(f=cmd_diff)
    sub.add_parser('offline').set_defaults(f=cmd_offline)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
