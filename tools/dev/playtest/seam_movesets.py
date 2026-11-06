#!/usr/bin/env python3
"""Measure real 2 MB Seam/story battles with an explicit Agumon fixture.

Run separately against baseline and changed discs; checkpoints never cross
executables. Enemy stats, move weights, RNG, hits and results are not injected.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu as BaseEmu
from tools.dev.playtest.birdramon_recruitment import field_card, free_heap
from tools.dev.playtest.damage_curve_battles import arm_call, trace, hits
from tools.langpatch import elf_symbols

CASES = {'iceleomon': (323, 0, 10, 300, 100), 'icedevimon': (323, 2, 23, 200, 0),
         'sorcermon': (323, 1, 10, 300, 100), 'devimon': (247, 5, 10, 300, 100)}


class Emu(BaseEmu):
    def ram(self):
        # Only retry this read-only snapshot, never a game action or outcome.
        for attempt in range(3):
            try:
                return super().ram()
            except subprocess.CalledProcessError as error:
                if attempt == 2:
                    raise RuntimeError(f'RAM snapshot failed: {error.stderr.decode(errors="replace")}') from error
                time.sleep(.25)


def fixture(e, slot, partner_type=3, technique=3, dx=300, dz=100):
    e.run('pause')
    try:
        # One legal equipped/learned move, NORMAL, Your Call; no items,
        # finishers or forced attack commands. Resolve the actual loaded slots.
        ram = e.ram()
        para = e.A('DIGIMON_DATA') - 0x80000000 + partner_type * 52
        moves = list(ram[para + 35:para + 51])
        animation = 46 + moves.index(technique)
        e.poke('PARTNER_ENTITY+0x38', struct.pack('<4h', 800, 500, 350, 700))
        e.poke('PARTNER_ENTITY+0x40', bytes([100, 0, 0, 0, animation, 255, 255, 255]))
        e.poke('PARTNER_ENTITY+0x48', struct.pack('<4h', 9999, 9999, 9999, 9999))
        e.poke('PARTNER_ENTITY+0x58', (1 << technique).to_bytes(16, 'little'))
        e.poke('MOD_OPT_DIFFICULTY', struct.pack('<i', 0))
        e.poke('PARTNER_PARA', bytes(4))
        ram = e.ram()
        npc = e.peek('NPC_ENTITIES+' + str(slot * 0x68 + 4), 'I', ram)
        x, y, z = struct.unpack_from('<3i', ram, npc - 0x80000000 + 0x78)
        if y:
            # Mt. Infinity's actor starts above the floor before its descent
            # scene. A direct battle fixture uses the scene's landed position.
            y = 0
            e.run('poke', hex(npc + 0x7c), bytes(4).hex())
            e.run('poke', hex(e.A('NPC_ENTITIES') + slot * 0x68 + 0x14), bytes(4).hex())
        x += dx
        z += dz
        pos = e.peek('PARTNER_ENTITY+4', 'I', ram)
        e.run('poke', hex(pos + 0x78), struct.pack('<3i', x, y, z).hex())
        e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', x << 15, y << 15, z << 15))
        # loadBattleData calls tickPartnerWaypoints before rendering the new
        # position. A stale offscreen flag would relocate this staged partner.
        e.poke('PARTNER_ENTITY+0x35', b'\x01')
        # Arm while paused: a field frame here would make the partner run back
        # toward the tamer before the direct battle starts.
        arm_call(e, 'startBattle', [slot + 2])
    finally:
        e.run('resume')
    return dict(partner=[x, y, z], enemy=[x-dx, y, z-dz])


def pan(e, slot):
    # A timed pan streams and clamps the background, unlike a large one-frame
    # walk delta. The staged fighters must be visible during a direct start.
    e.poke('CAMERA_REACHED_TARGET', b'\xff')
    arm_call(e, 'tickCameraMoveToEntity', [5 + slot, 20])
    for _ in range(40):
        e.wait(.25)
        if e.peek('CAMERA_REACHED_TARGET', 'b') == 1:
            break
    assert e.peek('CAMERA_REACHED_TARGET', 'b') == 1, 'camera pan did not finish'


def observe_moves(e, exe):
    addr = e.A('BTL_setupMoveExecution')
    data = Path(exe).with_name('BTL_REL.BIN').read_bytes()
    words = struct.unpack_from('<4I', data, addr - e.A('btl_START'))
    guard = ' and '.join(f'u32({addr + i * 4})=={w}' for i, w in enumerate(words))
    e.run('lua', f'''
SM={{moves={{}}}}
local mem=PCSX.getMemPtr()
local function u8(a)return tonumber(mem[a-0x80000000])end
local function u16(a)return u8(a)+256*u8(a+1)end
local function u32(a)return u16(a)+65536*u16(a+2)end
SM.bp=PCSX.addBreakpoint({addr},'Exec',4,'moveset-start',function()
 if not ({guard}) then return end
 local r=PCSX.getRegisters().GPR.n
 -- Called after the animation starts, after loading/global-lock waits.
 SM.moves[#SM.moves+1]={{u32(r.a0),u16({e.A('BATTLE_FRAME_COUNT')}),r.a0=={e.A('PARTNER_ENTITY')} and 1 or 0}}
end)
return 'observing' ''')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc')
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--card', default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    ap.add_argument('--port', type=int, default=44367)
    ap.add_argument('--cases', help='comma-separated cases; defaults to the three Seam foes, or IceLeomon/IceDevimon/Devimon with --neutral')
    ap.add_argument('--neutral', action='store_true', help='Leomon with Megaton Punch; same stats, a physical comparison')
    ap.add_argument('--resume', action='store_true', help='reuse this output folder\'s field checkpoint with an identical executable')
    ap.add_argument('--seconds', type=int, default=360)
    args = ap.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(args.out / 'emu'))
    for name, (address, _, _) in elf_symbols(args.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = json.loads((args.out / 'results.json').read_text()) if args.resume and (args.out / 'results.json').exists() else []
    partner_type, technique = (48, 46) if args.neutral else (3, 3)
    cases = args.cases or ('iceleomon,icedevimon,devimon' if args.neutral else 'iceleomon,icedevimon,sorcermon')
    results = [r for r in results if r['case'] not in cases.split(',')]
    try:
        card = field_card(args.card, str(args.out / 'test.mcd'), partner_type=partner_type)
        e.start(card)
        checkpoint = str(args.out / 'field.state')
        stamp = args.out / 'field-exe.sha256'
        identity = hashlib.sha256(Path(args.exe).read_bytes()).hexdigest()
        if args.resume:
            assert stamp.read_text().strip() == identity, 'checkpoint executable differs'
            e.run('load', checkpoint)
        else:
            assert e.continue_game() == 0
        assert e.peek('PARTNER_ENTITY', 'I') == partner_type, 'checkpoint partner differs'
        e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0')
        arm_call(e, 'modProbeRam', [])
        e.wait(1)
        assert '2' in e.run('lua', 'return DCall.phase'), 'RAM probe did not return'
        assert e.peek('MOD_COLD_CACHE_TYPE', 'i') == -1, 'expanded RAM detected'
        if not args.resume:
            e.run('save', checkpoint)
            stamp.write_text(identity + '\n')
        assert len(e.ram()) == 0x200000
        for case in cases.split(','):
            screen, slot, hour, dx, dz = CASES[case]
            e.run('load', checkpoint)
            e.gs('set', f'hour={hour}', 'minute=0')
            if case == 'devimon':
                e.gs('trigger', '321', '0')
                e.gs('trigger', '727', '0')
            assert e.warp(screen), (case, 'warp failed')
            e.wait(2)
            pan(e, slot)
            ram = e.ram()
            entity = e.A('NPC_ENTITIES') + slot * 0x68
            offset = entity - 0x80000000
            enemy = dict(species=struct.unpack_from('<I', ram, offset)[0],
                         stats=list(struct.unpack_from('<4h', ram, offset + 0x38)),
                         weights=list(ram[offset + 0x40:offset + 0x44]),
                         moves=list(ram[offset + 0x44:offset + 0x48]),
                         hp=struct.unpack_from('<h', ram, offset + 0x4c)[0],
                         mp=struct.unpack_from('<h', ram, offset + 0x4e)[0])
            print(json.dumps(dict(case=case, phase='ready', enemy=enemy)), flush=True)
            trace(e, args.exe, 'field', args.out)
            observe_moves(e, args.exe)
            for n, v in ((250, 1), (251, slot + 2), (252, 255), (253, 255)):
                e.gs('pstat', str(n), str(v))
            e.gs('trigger', '1', '0')
            initial_positions = fixture(e, slot, partner_type, technique, dx, dz)
            start = time.monotonic()
            seen = False
            samples = []
            heap = None
            entered_positions = None
            while time.monotonic() - start < args.seconds:
                ram = e.ram()
                gs = e.peek('GAME_STATE', 'H', ram)
                frame = e.peek('BATTLE_FRAME_COUNT', 'h', ram)
                samples.append(dict(wall=round(time.monotonic() - start, 2), state=gs, tick=frame,
                                    hp=e.peek('PARTNER_ENTITY+0x4c', 'h', ram)))
                if gs in (1, 4) and not seen:
                    seen = True
                    heap = free_heap(e, ram)
                    pp = e.peek('PARTNER_ENTITY+4', 'I', ram) - 0x80000000
                    ep = e.peek('NPC_ENTITIES+' + str(slot*0x68+4), 'I', ram) - 0x80000000
                    entered_positions = dict(partner=list(struct.unpack_from('<3i',ram,pp+0x78)),
                                             enemy=list(struct.unpack_from('<3i',ram,ep+0x78)))
                    delta = [a-b for a,b in zip(entered_positions['partner'], initial_positions['partner'])]
                    assert sum(d*d for d in delta) < 400**2, 'partner relocated during battle entry'
                if seen and gs == 0:
                    break
                if frame > 1200 and not hits(e):
                    e.run('shot', str(args.out / (case + '-no-damage.png')))
                    raise RuntimeError(f'{case}: no damage in 60 battle seconds; reject this fixture')
                if seen and len(samples) == 20:
                    e.run('shot', str(args.out / (case + '.png')))
                # Advance result/dialog boxes after combat ticks stop. Leave
                # the live command menu alone so the partner uses Your Call.
                if len(samples) >= 3 and len({s['tick'] for s in samples[-3:]}) == 1:
                    e.press('CONFIRM', 12)
                time.sleep(.4)
            recorded = hits(e)
            raw = e.run('lua', "local o={} for _,x in ipairs(SM.moves) do o[#o+1]=table.concat(x,',') end return table.concat(o,';')")
            import re
            starts = [list(map(int, x.split(','))) for x in re.findall(r'([0-9]+,[0-9]+,[01])', raw)]
            ticks = [x[1] for x in starts if x[2]]
            result = dict(case=case, enemy=enemy, partnerSpecies=partner_type, partnerTechnique=technique,
                          partnerOffset=[dx, dz],
                          initialPositions=initial_positions, enteredPositions=entered_positions,
                          ramBytes=len(e.ram()), ramProbeExpanded=False, heap=heap,
                          finished=seen and samples[-1]['state'] == 0,
                          partnerKnockedOut=min(s['hp'] for s in samples) <= 0,
                          battleSeconds=max(s['tick'] for s in samples) / 20,
                          hpLost=9999 - min(s['hp'] for s in samples),
                          partnerStarts=len(ticks), maxPartnerStartGapSeconds=max([b-a for a,b in zip(ticks,ticks[1:])] or [0])/20,
                          partnerHits=sum(bool(h[6]) and h[1] == enemy['species'] for h in recorded),
                          partnerSelfHits=sum(bool(h[6]) and h[1] == partner_type for h in recorded),
                          enemyHits=sum(not h[6] for h in recorded),
                          enemyHitMoves=dict(Counter(str(h[2]) for h in recorded if not h[6])),
                          damageTrace=recorded, starts=starts, samples=samples,
                          executableSha256=hashlib.sha256(Path(args.exe).read_bytes()).hexdigest())
            assert seen and recorded and len({s['tick'] for s in samples}) > 3, (case, 'battle failed to run')
            results.append(result)
            (args.out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
            print(json.dumps({k:v for k,v in result.items() if k not in ('samples','damageTrace','starts')}), flush=True)
            e.run('lua', "SM.bp:remove() for _,bp in ipairs(DC.bps) do pcall(function()bp:remove()end) end return 'removed'")
    except BaseException:
        e.run('shot', str(args.out / 'failure.png'), check=False)
        raise
    finally:
        e.stop()


if __name__ == '__main__':
    main()
