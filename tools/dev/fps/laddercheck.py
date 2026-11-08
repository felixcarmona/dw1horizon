"""Frame-rate ladder measurements in PCSX-Redux, guest time (vblank listener).

  laddercheck.py prepare  --disc D.cue --exe EXE --port P --out DIR [--ram 8] [--cpu interpreter]
      boots the disc with the corpus card, continues the save and saves scene states under DIR/states
  laddercheck.py capture  --disc D.cue --exe EXE --port P --out DIR [--ram 8] [--cpu interpreter]
                      [--refreshes 1800] [--policies 0,1,2,3] [--keep60 60] SCENE...
      loads each scene state and records every presented frame per policy; JSON per capture in DIR
  laddercheck.py summary DIR...      markdown table of the captures

Policies (MOD_FPS_POLICY): 0 ladder, 1 lock 60, 2 lock steady 30, 3 lock 20 (= 0.0.7 AUTO at 100 % CPU), 4 CPU probe.
"""
import argparse, hashlib, json, math, os, struct, sys, time, urllib.parse
from collections import Counter
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
BIOS = str(WT / '.tools/emu/pcsx-redux-zip/squashfs-root/usr/share/pcsx-redux/resources/openbios.bin')
sys.path[:0] = [str(WT), str(WT / 'tools')]
os.chdir(WT)
from tools.dev.saves.releases import Emu  # noqa: E402
from tools.langpatch import elf_symbols  # noqa: E402
from tools.dev.playtest.airdramon_timeout import native_card  # noqa: E402
from tools.dev.playtest.damage_curve_battles import arm_call  # noqa: E402


class LocalEmu(Emu):
    def ram(self):
        return self.api('/api/v1/cpu/ram/raw')[:0x200000]


def make_emu(a):
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = LocalEmu(a.disc, a.exe, a.port, str(out))
    args = ['-bios', BIOS]
    if a.ram == 8: args.append('-8mb')
    if a.cpu == 'interpreter': args.append('-interpreter')
    e.env['EMU_ARGS'] = ' '.join(args)
    for n, (addr, _, _) in elf_symbols(e.exe + '.elf').items(): e.table.setdefault(n, addr)
    e.out = out
    return e


def lua(e, code):
    p = e.out / f'cmd-{e.port}.lua'; p.write_text(code)
    r = e.api('/api/v1/lua/eval?file=' + urllib.parse.quote(str(p))).decode()
    if r.startswith('error:'): raise RuntimeError(r)
    return r


def w8(e, name, v): e.poke(name, struct.pack('<b', v))
def w16(e, name, v): e.poke(name, struct.pack('<h', v))
def w32(e, name, v): e.poke(name, struct.pack('<i', v))


def seed_fight(e):
    for name in ('PARTNER_ENTITY', 'NPC_ENTITIES'):
        e.poke(name + '+0x38', struct.pack('<4h', 100, 999, 500, 500))
        e.poke(name + '+0x48', struct.pack('<4h', 30000, 30000, 30000, 30000))


def prepare(a):
    e = make_emu(a); st = e.out / 'states'; st.mkdir(exist_ok=True)
    (st / 'executable.sha256').write_text(hashlib.sha256(Path(e.exe).read_bytes()).hexdigest() + '\n')
    card = native_card('tools/dev/saves/corpus/20261027-d2796814.mcd', st / 'continue.mcd')
    e.start(card)
    try:
        print('continue:', e.continue_game(), flush=True)
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0', 'partner.para.condition=0',
             'partner.para.nextHungerHour=23', 'partner.para.sleepyHour=23')
        e.run('save', str(st / 'house.state')); e.run('shot', str(st / 'house.png'))
        print('house', e.peek('CURRENT_SCREEN', 'h'), flush=True)
        for label, screen in [('file-city', 168), ('gear-savanna', 69), ('freezeland', 88)]:
            if label in a.skip: continue
            ok = e.warp(screen) and e.in_control()
            print(label, screen, ok, e.peek('CURRENT_SCREEN', 'h'), flush=True)
            if ok:
                e.run('save', str(st / f'{label}.state')); e.run('shot', str(st / f'{label}.png'))
    finally:
        e.stop()
    for kind, screen in [('wild', 0), ('tournament', 208)]:
        if kind in a.skip: continue
        te = make_emu(a); te.env['EMU_ARGS'] += ' -interpreter -debugger'
        te.start(None)
        try:
            te.run('load', str(st / 'house.state')); te.run('resume'); time.sleep(1)
            assert te.warp(screen) and te.in_control(), kind + ' warp failed'
            if kind == 'tournament':
                te.gs('pstat', '3', '4'); arm_call(te, 'startTournament', [])
            else:
                # Enter the actual placed enemy's battle through the ordinary start path.
                for n, v in ((250, 1), (251, 2), (252, 255), (253, 255)):
                    te.gs('pstat', str(n), str(v))
                te.gs('trigger', '1', '0')
                arm_call(te, 'startBattle', [2])
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                r = te.ram()
                if te.peek('GAME_STATE', 'B', r) == (4 if kind == 'tournament' else 1) and te.peek('BATTLE_FRAME_COUNT', 'h', r) > 80:
                    te.run('pause'); seed_fight(te)
                    te.run('save', str(st / f'{kind}.state')); te.run('shot', str(st / f'{kind}.png'))
                    print(kind, 'READY', flush=True); break
                te.press('CONFIRM', 4); time.sleep(0.5)
            else: raise RuntimeError(kind + ' never entered battle')
        finally:
            te.stop()


def reset_ladder(e, keep60):
    if not e.has('MOD_FPS_POLICY'):
        w32(e, 'MOD_PERF_RESET', 1)
        return
    w8(e, 'MOD_CAD_LEVEL', 2)
    if e.has('modCadCount'):  # the first build: separate statics
        w8(e, 'modCadCount', 0); w8(e, 'modCadPos', 0); w8(e, 'modCadCtx', -1)
        w8(e, 'modCadPrev', -1); w8(e, 'modCadUp', 0); w16(e, 'modCadSince', 0)
        e.poke('modCadCtxLevel', bytes([2, 2])); e.poke('modCadCool', struct.pack('<2h', 32, 32))
    else:  # struct modCad: ring[32] u32, mapGen i32, since i16, cool[2] i16, count/pos/ctx/prev/up i8, ctxLevel[2] i8
        e.poke('modCad+132', struct.pack('<h2h', 0, 32, 32) + bytes([0, 0, 0xFF, 0xFF, 0, 2, 2]))
    w32(e, 'MOD_CAD_SWITCHES', 0); w8(e, 'MOD_CAD_KEEP60', keep60); w32(e, 'MOD_PERF_RESET', 1)


def capture(e, a, label, policy):
    e.api('/api/v1/execution-flow?function=pause', data=b'')
    state = label[:-5] if label.endswith('-walk') else label
    import urllib.request
    r = urllib.request.urlopen(f'http://127.0.0.1:{e.port}/api/v1/lua/load?file=' + urllib.parse.quote(str(e.out / 'states' / f'{state}.state')), timeout=90).read().decode()
    if not r.startswith('ok'): raise RuntimeError(r)
    # Redux applies a queued state when resumed. Never write policy into pre-restore RAM.
    e.run('resume'); time.sleep(0.2)
    e.api('/api/v1/execution-flow?function=pause', data=b'')
    screen_start = e.peek('CURRENT_SCREEN', 'h')
    reset_ladder(e, a.keep60)
    if e.has('MOD_FPS_POLICY'): w8(e, 'MOD_FPS_POLICY', policy)
    else: assert policy == 4, 'baseline executable only supports its original AUTO'
    if a.cpu == 'fast':
        lua(e, 'CORE_SCALE=0.5;return dofile(' + repr(str(WT / 'tools/dev/fps/redux_core_scale.lua')) + ')')
    walk = label.endswith('-walk')
    A = e.A
    level_expr = f"r8({A('MOD_CAD_LEVEL')})" if e.has('MOD_CAD_LEVEL') else f"r32({A('MOD_FPS_MODE_RUN')})"
    policy_expr = f"r8({A('MOD_FPS_POLICY')})" if e.has('MOD_FPS_POLICY') else '4'
    cost_expr = f"r32({A('MOD_CAD_LAST')})" if e.has('MOD_CAD_LAST') else '0'
    lua(e, f'''local m=PCSX.getMemPtr(); local ffi=require('ffi')
    local function r32(a) return tonumber(ffi.cast('uint32_t*',m+a-0x80000000)[0]) end
    local function r8(a) return tonumber(ffi.cast('int8_t*',m+a-0x80000000)[0]) end
    local function currentLevel()
      local p={policy_expr}
      if p==4 then return r32({A('MOD_FPS_MODE_RUN')}) end
      if p>0 then return 3-p end
      return {level_expr}
    end
    if STUDY and STUDY.vl then STUDY.vl:remove() end
    local pad=PCSX.SIO0.slots[1].pads[1]
    STUDY={{v=0,rows={{}},costs={{}},ticks0=r32({A('MOD_FPS_TICKS')}),renders=r32({A('MOD_FPS_RENDERS')}),bad=0,last=-1,dir=0}}
    STUDY.vl=PCSX.Events.createEventListener('GPU::Vsync',function()
      if STUDY.v>={a.refreshes} then return end
      STUDY.v=STUDY.v+1
      local renders=r32({A('MOD_FPS_RENDERS')})
      if renders~=STUDY.renders then
        if renders-STUDY.renders~=1 then STUDY.bad=STUDY.bad+1 end
        STUDY.rows[#STUDY.rows+1]=STUDY.v..','..currentLevel()..','..{policy_expr}
        STUDY.renders=renders
      end
      local last={cost_expr}
      if last~=STUDY.last then STUDY.costs[#STUDY.costs+1]=last; STUDY.last=last end
      if {1 if walk else 0}==1 and STUDY.v%150==1 then
        if STUDY.dir==1 then pad.clearOverride(PCSX.CONSTS.PAD.BUTTON.LEFT) else pad.clearOverride(PCSX.CONSTS.PAD.BUTTON.RIGHT) end
        STUDY.dir=1-STUDY.dir
        if STUDY.dir==1 then pad.setOverride(PCSX.CONSTS.PAD.BUTTON.LEFT) else pad.setOverride(PCSX.CONSTS.PAD.BUTTON.RIGHT) end
      end
      if STUDY.v>={a.refreshes} then
        pad.clearOverride(PCSX.CONSTS.PAD.BUTTON.LEFT); pad.clearOverride(PCSX.CONSTS.PAD.BUTTON.RIGHT)
        STUDY.ticks1=r32({A('MOD_FPS_TICKS')});STUDY.spins=r32({A('MOD_CPU_SPINS')})
        PCSX.pauseEmulator()
      end
    end)
    return 'armed' ''')
    e.api('/api/v1/execution-flow?function=start', data=b'')
    t0 = time.monotonic()
    while int(lua(e, 'return STUDY.v')) < a.refreshes:
        time.sleep(0.5)
        if time.monotonic() - t0 > 1200: raise RuntimeError('capture timeout')
    host = time.monotonic() - t0
    rows = [[int(x) for x in row.split(',')] for row in lua(e, "return table.concat(STUDY.rows,'\\n')").splitlines() if row]
    costs = [int(x) for x in lua(e, "return table.concat(STUDY.costs,',')").split(',') if x]
    bad = int(lua(e, 'return STUDY.bad')); lua(e, 'STUDY.vl:remove(); return 1')
    ram = e.ram()
    perf = {n: e.peek(n, 'i', ram) for n in ('MOD_PERF_TICK_SUM', 'MOD_PERF_TICK_MAX', 'MOD_PERF_RENDER_SUM', 'MOD_PERF_RENDER_MAX',
                                             'MOD_PERF_XRENDER_SUM', 'MOD_PERF_XRENDER_MAX', 'MOD_PERF_XPASSES', 'MOD_PERF_FRAMES',
                                             'MOD_PERF_LATE', 'MOD_CAD_SWITCHES', 'MOD_FPS_TICKS') if e.has(n)}
    frames = max(1, perf['MOD_PERF_FRAMES']); xp = max(1, perf['MOD_PERF_XPASSES'])

    def stats(rows):
        ds = [b[0] - a_[0] for a_, b in zip(rows, rows[1:])]
        if not ds: return {}
        slow = sorted(ds, reverse=True)[:max(1, math.ceil(len(ds) * .01))]
        return dict(swaps=len(rows), fps=round(60 * len(ds) / sum(ds), 2), low1=round(60 / (sum(slow) / len(slow)), 2),
                    intervals=dict(sorted(Counter(ds).items())))
    levels = [row[1] for row in rows]
    switches = sum(1 for x, y in zip(levels, levels[1:]) if x != y)
    first_switch = next((row[0] for row, prev in zip(rows[1:], rows) if row[1] != prev[1]), None)
    share = Counter(levels)
    c0 = [c & 0xFFF for c in costs]; cx = [(c >> 12) & 0xFFF for c in costs if (c >> 12) & 0xFFF]
    shown = [(c >> 24) & 3 for c in costs]
    res = dict(scene=label, policy=policy, keep60=a.keep60, ram=a.ram, cpu=a.cpu, executable_sha256=hashlib.sha256(Path(e.exe).read_bytes()).hexdigest(), refreshes=a.refreshes, host_s=round(host, 1),
               logic_hz=round(60 * int(lua(e, 'return STUDY.ticks1-STUDY.ticks0')) / a.refreshes, 3),
               cpu_spins=int(lua(e, 'return STUDY.spins')), bad_counter_deltas=bad, screen=e.peek('CURRENT_SCREEN', 'h', ram), game_state=e.peek('GAME_STATE', 'B', ram),
               whole=stats(rows), steady=stats([row for row in rows if row[0] >= 300]),
               level_switches=switches, first_switch_refresh=first_switch, final_level=levels[-1] if levels else None,
               switches_per_min=round(switches * 3600 / a.refreshes, 2),
               level_share={k: round(v / len(levels), 3) for k, v in share.items()} if levels else {},
               tick_avg=round(perf['MOD_PERF_TICK_SUM'] / frames, 1), tick_max=perf['MOD_PERF_TICK_MAX'],
               render_avg=round(perf['MOD_PERF_RENDER_SUM'] / frames, 1), render_max=perf['MOD_PERF_RENDER_MAX'],
               xrender_avg=round(perf['MOD_PERF_XRENDER_SUM'] / xp, 1), xrender_max=perf['MOD_PERF_XRENDER_MAX'],
               xpasses_per_tick=round(perf['MOD_PERF_XPASSES'] / frames, 2), late=perf['MOD_PERF_LATE'], ticks=perf['MOD_PERF_FRAMES'],
               cost0=dict(n=len(c0), avg=round(sum(c0) / max(1, len(c0)), 1), p50=sorted(c0)[len(c0) // 2] if c0 else 0,
                          p90=sorted(c0)[int(len(c0) * .9)] if c0 else 0, max=max(c0) if c0 else 0),
               costx=dict(n=len(cx), avg=round(sum(cx) / max(1, len(cx)), 1), max=max(cx) if cx else 0),
               shown_per_tick=round(sum(shown) / max(1, len(shown)), 2), raw=rows)
    expected_state = 4 if state == 'tournament' else 1 if state == 'wild' else 0
    assert res['game_state'] == expected_state, 'scene ended during capture'
    assert res['screen'] == screen_start, 'walking left the target screen'
    assert bad == 0, 'vblank listener missed a presented frame'
    name = f'{label}-p{policy}-k{a.keep60}-{a.ram}mb-{a.cpu}.json'
    (e.out / name).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'raw'}), flush=True)
    return res


def do_capture(a):
    e = make_emu(a)
    assert (e.out / 'states/executable.sha256').read_text().strip() == hashlib.sha256(Path(e.exe).read_bytes()).hexdigest(), 'checkpoint executable differs'
    for label in a.scenes:
        for policy in a.policies:
            # One process per restored checkpoint: JIT patches cannot survive a cache reset safely.
            e.start(None)
            try:
                capture(e, a, label, policy)
            finally:
                e.stop()


def summary(dirs):
    rows = []
    for d in dirs:
        for p in sorted(Path(d).glob('*.json')):
            try: j = json.loads(p.read_text())
            except Exception: continue
            if 'whole' not in j: continue
            rows.append(j)
    names = {0: 'ladder', 1: 'forced 60', 2: 'steady 30', 3: '20 (0.0.7 AUTO)', 4: 'CPU probe'}
    print('| Scene | RAM/CPU | Policy | fps | 1% low | intervals (refreshes: count) | level switches | final level | tick/pass0/extra lines |')
    print('|---|---|---|---:|---:|---|---:|---|---|')
    for j in sorted(rows, key=lambda j: (j['scene'], j['ram'], j['cpu'], j['policy'], j['keep60'])):
        s = j['steady'] or j['whole']
        pol = names.get(j['policy'], j['policy']) + (f" (keep60={j['keep60']})" if j['policy'] == 0 and j['keep60'] != 60 else '')
        print(f"| {j['scene']} | {j['ram']} MB {j['cpu']} | {pol} | {s.get('fps')} | {s.get('low1')} | "
              f"{' '.join(f'{k}:{v}' for k, v in s.get('intervals', {}).items())} | {j['level_switches']} | {j['final_level']} | "
              f"{j['tick_avg']}/{j['render_avg']}/{j['xrender_avg']} |")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=['prepare', 'capture', 'summary'])
    p.add_argument('scenes', nargs='*')
    p.add_argument('--disc'); p.add_argument('--exe'); p.add_argument('--port', type=int, default=43400)
    p.add_argument('--out'); p.add_argument('--ram', type=int, choices=(2, 8), default=2); p.add_argument('--cpu', choices=('dynarec', 'interpreter', 'fast'), default='dynarec')
    p.add_argument('--refreshes', type=int, default=1800); p.add_argument('--policies', default='0,1,2,3')
    p.add_argument('--keep60', type=int, default=60); p.add_argument('--skip', default='')
    a = p.parse_args()
    a.policies = [int(x) for x in a.policies.split(',') if x]; a.skip = a.skip.split(',')
    if a.cmd == 'prepare': prepare(a)
    elif a.cmd == 'capture': do_capture(a)
    else: summary(a.scenes)


if __name__ == '__main__':
    main()
