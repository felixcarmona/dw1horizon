#!/usr/bin/env python3
"""A wild fight on Great Canyon Top Area (screen 43) whose drop is placed with the enemy inside the cliff.

Reported in play: a dropped item lay on tile 78,46, inside the right cliff, where the tamer can never get within one
tile of it. Battle moves skip the map collision, so the defeated enemy can stand there when spawnDroppedItems runs.

Boots the native-Agumon corpus card in original-2-MB PCSX-Redux, warps to 43 and fights wild slot --slot for real.
Fixture writes: a strong partner, the enemy species' drop chance at 100 and, with --wall, a breakpoint at the entry of
spawnDroppedItems that moves the defeated enemy to 2811,370 (the reported spot) before the drop is placed. After the
fight the drop's tile and sprite are read, the screen's collision is read from RAM and tools/maps/reach.py walks it
from where the tamer stands: how many points of that walk pick the item up (tamer.c: his tile within one of the
item's). Then the tamer is placed on the best of those points and the pickup must start (TAMER_STATE 7).
Without --wall the drop must stay on the enemy's own tile and sprite position (a drop on open ground is unchanged).

  python3 tools/dev/playtest/drop_reach.py build/x.cue --exe build/x/exe/SLUS_010.32 --out build/drop-wall --wall
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/maps')]
from tools.dev.playtest.battle_return import free, sample
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols
import reach

WALL = (2811, 370)            # the reported item, tile 78,46
PARA_SIZE, DROP_CHANCE = 52, 34   # DigimonPara (params.h)


def drops(e, ram):
    out = []
    for i in range(11):
        sx, sy, sz, _, kind, tx, ty = e.peek(f'DROPPED_ITEMS+{16 * i}', '4hi2h', ram)
        if kind != -1:
            out.append(dict(slot=i, type=kind, tile=[tx, ty], sprite=[sx, sz]))
    return out


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(str(args.disc.resolve()), str(args.exe.resolve()), args.port, str(out / 'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    result = dict(wall=args.wall, slot=args.slot)
    try:
        e.start(str(card_fixture(out, 168, [0, 0, 0], 3, False, 1, 0)))
        assert e.continue_game() == 0, 'Continue failed'
        assert e.in_control()
        e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0',
             'partner.para.condition=0', 'partner.para.age=1', 'partner.para.evoTimer=0',
             'partner.para.remainingLifetime=1000', 'partner.stats.hp=9999',
             'partner.stats.mp=9999', 'partner.stats.currentHP=9999',
             'partner.stats.currentMP=9999', 'partner.stats.off=999',
             'partner.stats.def=999', 'partner.stats.speed=999', 'partner.stats.brain=999')
        assert e.warp(43), 'screen 43 did not load'
        before = drops(e, e.ram())
        ram = e.ram()
        result['npcs'] = {i: e.peek(f'NPC_ENTITIES+{i * 0x68}', '2I', ram) for i in range(8)}
        kind, posdata = result['npcs'][args.slot]
        assert 0x80000000 < posdata < 0x80800000, f'no NPC in slot {args.slot}: {result["npcs"]}'
        assert 0 <= kind < 180, kind
        e.poke(f'DIGIMON_DATA+{kind * PARA_SIZE + DROP_CHANCE}', bytes([100]))
        result['enemy_type'] = kind
        lua = f'''
if DROPBP then DROPBP:remove() end
DROP={{hits=0}}
DROPBP=PCSX.addBreakpoint({e.A('spawnDroppedItems')},'Exec',4,'drop-reach',function()
  local m=PCSX.getMemPtr()
  local a0=bit.band(tonumber(PCSX.getRegisters().GPR.n.a0),0x1fffff)
  local pos=0
  for i=3,0,-1 do pos=pos*256+tonumber(m[a0+4+i]) end
  local loc=bit.band(pos,0x1fffff)+0x78
  local function rd(o) local v=0 for i=3,0,-1 do v=v*256+tonumber(m[o+i]) end if v>=2^31 then v=v-2^32 end return v end
  local function wr(o,v) if v<0 then v=v+2^32 end for i=0,3 do m[o+i]=v%256 v=math.floor(v/256) end end
  DROP.hits=DROP.hits+1
  DROP.x=rd(loc) DROP.z=rd(loc+8)
  if {str(args.wall).lower()} then wr(loc,{WALL[0]}) wr(loc+8,{WALL[1]}) end
end)
'''
        e.run('lua', lua)
        e.run('pause')
        try:
            e.gs('approach', str(args.slot), '150')
        finally:
            e.run('resume')
        started = False
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            row = sample(e)
            started |= row['GAME_STATE'] != 0
            if started and free(row):
                break
            e.press('CONFIRM', 8)
            e.wait(.25)
        else:
            raise AssertionError('the fight did not return to free field control')
        hit = e.run('lua', 'return DROP.hits..","..tostring(DROP.x)..","..tostring(DROP.z)').strip().split(',')
        result['spawn_calls'] = int(hit[0])
        assert result['spawn_calls'] >= 1, 'no drop was placed (spawnDroppedItems never ran)'
        result['enemy_at_drop'] = [int(hit[1]), int(hit[2])]
        ram = e.ram()
        new = [d for d in drops(e, ram) if d not in before]
        assert new, 'no new dropped item'
        item = new[0]
        result['drop'] = item
        tamer = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
        result['tamer'] = tamer
        m = type('RamMap', (), {})()
        m.collision = list(e.raw('MAP_COLLISION_DATA', 10000, ram))
        m.warps = []
        walk = reach.reach(m, starts=[(tamer[0], tamer[2])])
        on, near = reach.pickup_room(m, item['tile'], walk)
        result['pickup_points'] = dict(on_tile=on, window=near, walk=len(walk))
        origin = reach.model_tile(*(WALL if args.wall else result['enemy_at_drop']))
        result['enemy_tile'] = list(origin)
        if not args.wall:
            assert item['tile'] == list(origin) and item['sprite'] == result['enemy_at_drop'], item
        # Stand on the walked point nearest the item that picks it up; the pickup must start.
        spots = [(x, z) for x, z in walk if max(abs(a - b) for a, b in zip(reach.model_tile(x, z), item['tile'])) <= 1]
        if spots:
            sx, sz = min(spots, key=lambda p: (p[0] - item['sprite'][0]) ** 2 + (p[1] - item['sprite'][1]) ** 2)
            result['pickup_from'] = [sx, sz]
            e.run('pause')
            try:
                e.gs('move', str(sx), str(sz))
            finally:
                e.run('resume')
            for _ in range(20):
                state = e.peek('TAMER_STATE', 'B')
                if state == 7:
                    break
                e.wait(.25)
            result['pickup_state'] = state
            e.run('shot', str(out / 'pickup.png'))
        # Half a tile of standing room at least: the reported drop had 9 points (a sliver the player never finds).
        result['ok'] = near >= 50 and result.get('pickup_state') == 7
        assert result['ok'], 'the tamer cannot comfortably pick the drop up'
    except BaseException as error:
        result['error'] = str(error)
        try:
            e.run('shot', str(out / 'failure.png'))
        except Exception:
            pass
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        e.stop()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('disc', type=Path)
    p.add_argument('--exe', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--wall', action='store_true', help='the enemy stands at the reported cliff spot when its drop is placed')
    p.add_argument('--slot', type=int, default=0)
    p.add_argument('--port', type=int, default=39591)
    p.add_argument('--timeout', type=float, default=300)
    run(p.parse_args())


if __name__ == '__main__':
    main()
