#!/usr/bin/env python3
"""Two story scenes on original 2 MB RAM, from a disposable corpus card.

  xvfb-run -a python3 tools/dev/playtest/engine_room_shore.py DISC --exe EXE --card CARD --mode engine|shore

engine: with Canyon.CHASING (flag 717) the tamer walks to the tunnel tiles of the Engine Room; the band must stop him
        (the lookout's new line, the tamer walked back to x 400, z -1000, then the fight). The fight is won (enemy HP
        held at 1), the Motor is broken, Shellmon's join box is photographed through the white fade; then, settled,
        the tunnel must pass freely to the Rift (screen 301).
shore:  the Drowned Shore (309): the big Whamon at the water's edge, talked to from the beach; "Let's go back" must
        end on the Secret Beach Cave (142) with control.
Every picture is a pause: two identical screenshots.
"""
from pathlib import Path
import argparse
import json
import struct
import sys
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.langpatch import elf_symbols


class Run:
    def __init__(self, a):
        self.a = a; self.out = Path(a.out).resolve(); self.out.mkdir(parents=True, exist_ok=True)
        e = self.e = Emu(a.disc, a.exe, a.port, str(self.out / 'emu'))
        for name, (addr, _, _) in elf_symbols(a.exe + '.elf').items(): e.table.setdefault(name, addr)
        e.env['EMU_ARGS'] = '-interpreter -debugger'
        self.log = []

    def note(self, **k):
        print(json.dumps(k), flush=True); self.log.append(k)

    def flag(self, n, v=None):
        e = self.e; off = f'SCRIPT_STATE+{245 + n // 8}'; b = e.peek(off, 'B')
        if v is None: return bool(b & (1 << (n % 8)))
        e.poke(off, bytes([(b | (1 << (n % 8))) if v else (b & ~(1 << (n % 8)))]))

    def shot(self, label):
        e = self.e
        e.api('/api/v1/execution-flow?function=pause'); time.sleep(.3)
        x = e.api('/api/v1/screen/still'); time.sleep(.2); y = e.api('/api/v1/screen/still')
        e.api('/api/v1/execution-flow?function=start')
        assert x == y, 'pause screenshots differ: ' + label
        (self.out / (label + '.png')).write_bytes(x)

    def place(self, x, z):
        e = self.e
        e.api('/api/v1/execution-flow?function=pause')
        e.poke('TAMER_POSITION_DATA+0x78', struct.pack('<3i', x, 0, z))
        e.poke('TAMER_ENTITY+0x10', struct.pack('<3i', x << 15, 0, z << 15))
        e.api('/api/v1/execution-flow?function=start'); time.sleep(.8)

    def pos(self):
        r = self.e.ram()
        return struct.unpack_from('<3i', r, self.e.A('TAMER_POSITION_DATA+0x78') & 0x1fffff)

    def state(self):
        e = self.e; r = e.ram()
        return dict(screen=e.peek('CURRENT_SCREEN', 'h', r), op=e.peek('ACTIVE_INSTRUCTION', 'B', r),
                    paused=e.peek('IS_SCRIPT_PAUSED', 'i', r), tamer=e.peek('TAMER_STATE', 'B', r),
                    gs=e.peek('GAME_STATE', 'H', r), pos=self.pos())

    def control(self):
        s = self.state(); return s['paused'] == 1 and s['tamer'] == 0

    def boot(self):
        e = self.e
        field_card(self.a.card, str(self.out / 'test.mcd'))
        e.start(str(self.out / 'test.mcd')); r = e.continue_game(); assert r == 0, f'Continue failed: {r}'
        e.wait(5); assert e.in_control(), 'no field control'
        self.note(ram_bytes=len(e.ram()))
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0')

    def hold(self, button, frames):
        self.e.press(button, frames)

    def battle_fixture(self):
        e = self.e; a = e.A
        data = Path(self.a.exe).with_name('BTL_REL.BIN').read_bytes()
        words = struct.unpack_from('<8I', data, a('BTL_isBattleFinished') - a('btl_START'))
        guard = ' and '.join(f'u32({a("BTL_isBattleFinished") + 4 * i})=={w}' for i, w in enumerate(words))
        e.run('lua', f"""
local m=PCSX.getMemPtr();local function u8(a)return tonumber(m[a-0x80000000])end
local function u16(a)return u8(a)+256*u8(a+1)end
local function u32(a)return u16(a)+65536*u16(a+2)end
local bp
bp=PCSX.addBreakpoint({a('BTL_isBattleFinished')},'Exec',4,'fixture',function()
 if not ({guard}) then return end
 local c=u32({a('COMBAT_DATA_PTR')});if c<0x80000000 then return end
 for i=1,u16({a('ENEMY_COUNT')}) do
  local slot=u8(c+1644+i);local ent=u32({a('ENTITY_TABLE')}+4*slot)
  if ent>=0x80000000 and u16(ent+76)>1 then m[ent-0x80000000+76]=1;m[ent-0x80000000+77]=0 end
 end
end)
return 'battle fixture ready'""")


def engine(r):
    e = r.e; a = r.a
    r.flag(717, True); r.flag(718, False)
    assert e.warp(300), 'screen 300 did not load'; e.wait(2)
    r.battle_fixture()
    # The tunnel tiles are row tz 47 (z 300..400), tx 72..75 (x 2200..2600).
    r.place(2400, 150); r.shot('01-before-tunnel'); r.note(step='before', **r.state())
    seen_gate = False; shots = 0; walked_back = None; t0 = time.monotonic(); decided = False
    r.hold('UP', 120)
    while time.monotonic() - t0 < 420:
        s = r.state()
        if s['op'] == 0x1a and not seen_gate and s['screen'] == 300:
            seen_gate = True; r.note(step='gate fired', **s); time.sleep(1.0); r.shot('02-gate-line')
        if s['screen'] == 301 and not decided:
            raise AssertionError('the tunnel passed without the band: ' + str(s))
        if s['op'] == 0x10 and not decided:      # the Motor question
            time.sleep(.8); r.shot('04-motor-question'); r.note(step='motor question', **s)
            e.press('CONFIRM', 6); decided = True; t1 = time.monotonic()
            while time.monotonic() - t1 < 40:    # photograph the join, through the white fade
                r.shot(f'05-break-{shots:02d}'); shots += 1
                if r.flag(718) and r.control(): break
                time.sleep(.4)
            break
        if seen_gate and walked_back is None and s['op'] == 0x1a:
            pass
        e.press('CONFIRM', 6); time.sleep(.5)
    assert decided, 'never reached the Motor question'
    r.note(step='after break', canyon_settled=r.flag(718), chasing=r.flag(717), root1=r.flag(719),
           shellmon=r.flag(235), shots=shots, **r.state())
    assert r.flag(718) and r.flag(719) and r.flag(235), 'Break did not settle'
    for _ in range(30):
        if r.control(): break
        e.press('CONFIRM', 6); time.sleep(.5)
    assert r.control(), 'no control after Break'
    r.shot('06-after-break')
    # Settled: the tunnel passes freely.
    r.place(2400, 150); r.hold('UP', 150); time.sleep(4)
    s = r.state(); r.note(step='tunnel after settle', **s)
    for _ in range(40):
        if r.state()['screen'] == 301 and r.control(): break
        time.sleep(.5)
    s = r.state(); assert s['screen'] == 301 and r.control(), 'settled tunnel did not pass: ' + str(s)
    r.shot('07-rift')


def shore(r):
    e = r.e
    assert e.warp(309), 'screen 309 did not load'
    t0 = time.monotonic()
    while not r.control() and time.monotonic() - t0 < 60:
        e.press('CONFIRM', 6); time.sleep(.6)
    assert r.control(), 'no control on the shore'
    r.note(step='shore', **r.state()); r.shot('11-shore-arrival')
    for _ in range(20):
        if r.control(): break
        time.sleep(.5)
    r.place(300, -450); r.hold('RIGHT', 150); time.sleep(1)
    p = r.pos(); r.note(step='walked to the water box', pos=p); r.shot('12-at-whamon')
    e.press('CONFIRM', 6); time.sleep(1.5)
    s = r.state(); r.note(step='talk', **s)
    t0 = time.monotonic()
    while s['op'] != 0x10 and time.monotonic() - t0 < 20:
        e.press('CONFIRM', 6); time.sleep(.6); s = r.state()
    assert s['op'] == 0x10, 'Whamon did not ask: ' + str(s)
    time.sleep(.8); r.shot('13-ride-question')
    e.press('CONFIRM', 6)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 90:
        s = r.state()
        if s['screen'] == 142 and r.control(): break
        e.press('CONFIRM', 6); time.sleep(.6)
    s = r.state(); assert s['screen'] == 142 and r.control(), 'ride back failed: ' + str(s)
    r.note(step='ridden back', **s); r.shot('14-back-in-cave')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--mode', choices=('engine', 'shore'), required=True)
    ap.add_argument('--out', default='build/engine-shore'); ap.add_argument('--port', type=int, default=44210)
    a = ap.parse_args(); r = Run(a)
    try:
        r.boot(); (engine if a.mode == 'engine' else shore)(r)
        r.note(result='PASS ' + a.mode)
    except BaseException as error:
        r.note(result='FAIL', error=str(error)); r.e.run('shot', str(r.out / 'failure.png'), check=False); raise
    finally:
        (r.out / (a.mode + '-result.json')).write_text(json.dumps(r.log, indent=1) + '\n'); r.e.stop()


if __name__ == '__main__':
    main()
