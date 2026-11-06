#!/usr/bin/env python3
"""Measure imported enemy attacks in ordinary 2 MB field battles.

Use a matching disc and executable in EMU_PORT / DW_SYMS. The fixture replaces
Native Forest's ModokiBetamon at model loading and entity initialization, so the
game loads the tested species' real model, skeleton, texture and technique EFE.
Each equipped set starts a fresh battle: changing a slot during combat would
leave the previous technique's effect loaded. No damage or accuracy is forced.

  python3 -m tools.dev.playtest.battle_hits DISC OUT --ids 321 --seconds 30
  python3 -m tools.dev.playtest.battle_hits DISC OUT --all --seconds 20

The default checks each species' first three map attacks. --slots selects one
animation slot per battle instead. Range-4 buffs and Counter are recorded but
do not require outgoing damage against the defending partner.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import emulator as E
from tools.dev.playtest import species_proof as P
from tools.dev.playtest.birdramon_recruitment import field_card
import species


class Battle:
    def __init__(self, emu):
        self.emu = emu
        self.table = emu.table
        self.enemy_slot = 0
        self.execution_flow = json.loads(E.api('/api/v1/execution-flow'))
        if self.execution_flow.get('8mb') is not False:
            raise RuntimeError('The emulator must have its 8 MB expansion disabled')

    def address(self, name):
        return self.table[name] if isinstance(name, str) else name

    def read(self, name, fmt='i', ram=None):
        ram = self.ram() if ram is None else ram
        return struct.unpack_from('<' + fmt, ram, self.address(name) & 0x1fffff)[0]

    def ram(self):
        ram = E.api('/api/v1/cpu/ram/raw')
        if len(ram) != 0x200000:
            raise RuntimeError('Original 2 MB RAM required')
        return ram

    def write(self, name, fmt, value):
        data = struct.pack('<' + fmt, value)
        E.api(f'/api/v1/cpu/ram/raw?offset={self.address(name) & 0x1fffff}&size={len(data)}', data)

    def flow(self, running):
        E.api('/api/v1/execution-flow?function=' + ('start' if running else 'pause'), b'')

    def position(self, entity, x, z, y=0):
        """Keep the displayed position and the animation's fixed-point origin together."""
        pointer = self.read(entity + 4, 'I')
        for i, value in enumerate((x, y, z)):
            self.write(pointer + 120 + 4 * i, 'i', value)
            self.write(entity + 16 + 4 * i, 'i', value << 15)

    def effects(self, index, source, ram):
        if index < 0:
            return []
        slot = self.read('EFE_DATA_PTR', 'I', ram) + index * 40
        contexts = self.read(slot + 16, 'I', ram)
        count = self.read(slot + 20, 'h', ram)
        if not (0x80000000 <= contexts < 0x80200000 and 0 <= count <= 128):
            raise RuntimeError('Invalid effect context table')
        result = []
        for i in range(count):
            context = contexts + i * 28
            if self.read(context + 16, 'I', ram) != source:
                continue
            instance = self.read(context + 8, 'I', ram)
            if not 0x80000000 <= instance < 0x801fff00:
                continue
            frame = self.read(instance, 'i', ram)
            if frame >= 0:
                result.append(dict(context=i, frame=frame,
                                   x=self.read(instance + 4, 'i', ram),
                                   y=self.read(instance + 8, 'i', ram),
                                   z=self.read(instance + 12, 'i', ram)))
        return result

    def wait(self, predicate, seconds=90):
        stop = time.monotonic() + seconds
        while time.monotonic() < stop:
            ram = self.ram()
            if predicate(ram):
                return ram
            time.sleep(.2)
        raise RuntimeError('Battle fixture timed out')

    def world(self, screen):
        return self.wait(lambda r: self.read('CURRENT_SCREEN', 'h', r) == screen and
                         self.read('TAMER_STATE', 'B', r) == 0 and
                         self.read('IS_SCRIPT_PAUSED', 'i', r) == 1 and
                         self.read('GAME_STATE', 'B', r) == 0)

    def combat_ready(self):
        def ready(r):
            combat = self.read('COMBAT_DATA_PTR', 'I', r)
            effects = self.read('EFE_DATA_PTR', 'I', r)
            return (self.read('GAME_STATE', 'B', r) == 1 and
                    0x80000000 <= combat < 0x801ff000 and
                    0x80000000 <= effects < 0x801ff000 and
                    self.read('BATTLE_FRAME_COUNT', 'h', r) > 0 and
                    self.read('MOD_BATTLE_LOADING', 'B', r) == 0)
        return self.wait(ready)

    def fixture(self, spec, slots):
        """Change test placement before the normal game allocates its model."""
        a = self.address
        moves = slots + [255] * (4 - len(slots))
        lua = f"""
if HIT then for _, b in ipairs(HIT.bp) do b:remove() end end
HIT={{bp={{}}, loaded=0, spawned=0}}
local m=PCSX.getMemPtr()
local function w8(a,v) m[bit.band(a,0x1fffff)]=v%256 end
local function w16(a,v) w8(a,v);w8(a+1,math.floor(v/256)) end
local function w32(a,v) w16(a,v);w16(a+2,math.floor(v/65536)) end
local function u32(a) local o=bit.band(a,0x1fffff);return tonumber(m[o])+256*tonumber(m[o+1])+65536*tonumber(m[o+2])+16777216*tonumber(m[o+3]) end
local function hook(a,f) HIT.bp[#HIT.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'battle-hits',f) end
hook({a('loadNPCModel')},function()
 local r=PCSX.getRegisters().GPR.n
 local original=tonumber(r.a0)
 -- scriptLoadModel has already recorded this ID for later unloading.
 -- Keep that bookkeeping consistent with the actual replacement model.
 for i=0,7 do
  local entry={a('LOADED_DIGIMON_MODELS')}+4*i
  if u32(entry)==original then w32(entry,original==83 and {spec['id']} or 4294967295);break end
 end
 if original==83 then r.a0={spec['id']};HIT.loaded=HIT.loaded+1
 else PCSX.getRegisters().pc=r.ra end
end)
hook({a('scriptSetDigimon')},function()
 local r=PCSX.getRegisters().GPR.n
 if r.a0~=83 or r.a1~=0 then r.v0=1;PCSX.getRegisters().pc=r.ra;return end
 r.a0={spec['id']}
 local slot=tonumber(r.a1)
 -- Only slot zero is replaced, whose type is the first table field.
 local entry={a('MAP_DIGIMON_TABLE')}
 w16(entry,{spec['id']})
 local entity={a('NPC_ENTITIES')}+slot*104
 local moves={{{','.join(map(str, moves))}}}
 for i=0,3 do w8(entity+68+i,moves[i+1]);w8(entity+64+i,moves[i+1]==255 and 0 or 100) end
 w16(entity+72,30000);w16(entity+76,30000)
 w16(entity+74,30000);w16(entity+78,30000)
 w16(entity+56,500);w16(entity+58,300);w16(entity+60,500);w16(entity+62,300)
 HIT.spawned=HIT.spawned+1
end)
return 'installed'
"""
        path = ROOT / 'build' / f'battle-hits-{os.environ["EMU_PORT"]}.lua'
        path.write_text(lua)
        result = E.api('/api/v1/lua/eval?file=' + urllib.parse.quote(str(path))).decode()
        if result != 'installed':
            raise RuntimeError(result)

    def talk_handler(self, screen, enemy):
        """Enter the real NPC handler at a field frame boundary.

        A position poke leaves the scrolling camera behind. The game's talk
        dispatcher ignores offscreen NPCs, so use its section and entity id
        directly, as the existing recruitment integration tests do.
        """
        self.write('TALKED_TO_ENTITY', 'B', self.enemy_slot + 2)
        section = self.read(enemy + 101, 'B')
        loop = self.address('gameLoop')
        code = f"""
if HIT_ROUTE and HIT_ROUTE.bp then HIT_ROUTE.bp:remove() end
HIT_ROUTE={{}}
HIT_ROUTE.bp=PCSX.addBreakpoint({loop},'Exec',4,'battle-hits-talk',function()
 local r=PCSX.getRegisters()
 if HIT_ROUTE.ra then r.GPR.n.ra=HIT_ROUTE.ra;HIT_ROUTE.bp:remove();return end
 HIT_ROUTE.ra=r.GPR.n.ra;r.GPR.n.a0={self.read('CURRENT_SCRIPT_ID', 'H')};r.GPR.n.a1={section};r.GPR.n.a2=1
 r.GPR.n.ra={loop};r.pc={self.address('callScriptSection')}
end)
return 'armed'
"""
        path = ROOT / 'build' / f'battle-hits-talk-{os.environ["EMU_PORT"]}.lua'
        path.write_text(code)
        result = E.api('/api/v1/lua/eval?file=' + urllib.parse.quote(str(path))).decode()
        if result != 'armed':
            raise RuntimeError(result)

    def start(self, spec, slots, screen=0, enemy_slot=0, partner_stat=400, partner_attack=None,
              clear_path=False):
        self.enemy_slot = enemy_slot
        E.api('/api/v1/lua/eval?code=' + urllib.parse.quote("if HIT then for _,b in ipairs(HIT.bp) do b:remove() end;HIT=nil end;return 'cleared'"))
        self.emu.gs('trigger', '1', '1')
        if self.read('CURRENT_SCREEN', 'h') != 1:
            self.emu.gs('warp', '1', '0')
        self.world(1)
        if screen == 0:
            self.fixture(spec, slots)
        self.flow(False)
        partner = self.address('PARTNER_ENTITY')
        self.write(partner + 68, 'I', 0xffffffff if partner_attack is None else 0xffffff00 | partner_attack)
        for offset in (72, 74, 76, 78):
            self.write(partner + offset, 'h', 30000)
        for offset in (56, 58, 60, 62):
            self.write(partner + offset, 'h', partner_stat)
        self.write('PARTNER_PARA', 'I', 0)
        self.flow(True)
        time.sleep(.5)
        for _ in range(16):
            if self.read('IS_SCRIPT_PAUSED', 'i') == 1 and self.read('TAMER_STATE', 'B') == 0:
                break
            E.press('CROSS', 4)
            time.sleep(.5)
        self.emu.gs('warp', str(screen), '0')
        self.world(screen)
        enemy = self.address('NPC_ENTITIES') + enemy_slot * 104
        self.wait(lambda r: self.read(enemy, 'i', r) == spec['id'] and
                  self.read(self.address('ENTITY_TABLE') + (enemy_slot + 2) * 4, 'I', r) == enemy)
        self.flow(False)
        self.write(enemy + 72, 'h', 30000)
        self.write(enemy + 76, 'h', 30000)
        self.flow(True)
        # Keep the loaded camera and put the fixture beside its entry point.
        # Teleporting the tamer across a scrolling map leaves actors offscreen.
        self.flow(False)
        ram = self.ram()
        tp = self.read(self.address('TAMER_ENTITY') + 4, 'I', ram)
        self.position(enemy, self.read(tp + 120, 'i', ram) + 450,
                      self.read(tp + 128, 'i', ram))
        self.flow(True)
        # A large partner can otherwise intercept the talk press with its care
        # interaction when the tamer is placed beside the test opponent.
        self.flow(False)
        r = self.ram()
        tp = self.read(self.address('TAMER_ENTITY') + 4, 'I', r)
        self.position(partner, self.read(tp + 120, 'i', r) - 350,
                      self.read(tp + 128, 'i', r))
        self.flow(True)
        self.write('BATTLE_FRAME_COUNT', 'h', 0)
        self.talk_handler(screen, enemy)
        for _ in range(30):
            E.press('CROSS', 4)
            time.sleep(.5)
            if self.read('GAME_STATE', 'B') == 1:
                self.combat_ready()
                if clear_path:
                    # The tamer is a physical obstacle during a dash. Move
                    # aside, retaining the game's ordinary collision checks.
                    self.flow(False)
                    tamer = self.address('TAMER_ENTITY')
                    point = self.read(tamer + 4, 'I')
                    self.position(tamer, self.read(point + 120, 'i') + 1300,
                                  self.read(point + 128, 'i') - 1000)
                    self.flow(True)
                return
        raise RuntimeError('Could not start the field battle')

    def watch(self, seconds, out, defend=True, stop_on_hit=False):
        partner = self.address('PARTNER_ENTITY')
        enemy = self.address('NPC_ENTITIES') + self.enemy_slot * 104
        combat = self.read('COMBAT_DATA_PTR', 'I')
        self.flow(False)
        ram = self.ram()
        if self.read('ENEMY_COUNT', 'h', ram) != 1:
            raise RuntimeError('The attack fixture requires exactly one opponent')
        ids = [self.read(combat + 1644 + i, 'B', ram) for i in range(4)]
        enemy_fighter = ids.index(self.enemy_slot + 2)
        # Defend without outgoing attacks; leave the enemy's real attack AI active.
        if defend:
            self.write(combat + 1616, 'B', 6)
        for i in range(1, self.read('ENEMY_COUNT', 'h', ram) + 1):
            if i != enemy_fighter:
                self.write(combat + i * 360 + 40, 'h', 30000)
        initial = self.read(partner + 76, 'h', ram)
        self.flow(True)
        rows = []
        stop = time.monotonic() + seconds
        while time.monotonic() < stop:
            ram = self.ram()
            pos = self.read(enemy + 4, 'I', ram)
            target_pos = self.read(partner + 4, 'I', ram)
            f = combat + enemy_fighter * 360
            effect = self.read(enemy + 82, 'b', ram)
            effects = self.read('EFE_DATA_PTR', 'I', ram)
            effect_id = self.read(effects + effect * 40, 'i', ram) if effect >= 0 else None
            rows.append(dict(frame=self.read('BATTLE_FRAME_COUNT', 'h', ram),
                             hp=self.read(partner + 76, 'h', ram),
                             enemy_hp=self.read(enemy + 76, 'h', ram),
                             anim=self.read(enemy + 46, 'B', ram),
                             anim_frame=self.read(enemy + 28, 'h', ram),
                             technique=self.read(enemy + 80, 'h', ram),
                             effect=effect, effect_id=effect_id,
                             effects=self.effects(effect, enemy, ram),
                             flags=self.read(f + 52, 'H', ram),
                             queued=self.read(f + 56, 'B', ram),
                             target=self.read(f + 55, 'B', ram),
                             x=self.read(pos + 120, 'i', ram), z=self.read(pos + 128, 'i', ram),
                             px=self.read(target_pos + 120, 'i', ram), pz=self.read(target_pos + 128, 'i', ram)))
            if stop_on_hit and rows[-1]['hp'] < initial and rows[-1]['frame'] - rows[0]['frame'] > 40:
                break
            time.sleep(.1)
        E.shot(str(out / 'battle.png'))
        return dict(ram_bytes=0x200000, damage=initial - min(r['hp'] for r in rows),
                    played=sorted({r['anim'] for r in rows if 46 <= r['anim'] < 64}),
                    elapsed_frames=rows[-1]['frame'] - rows[0]['frame'], samples=rows)



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cue')
    parser.add_argument('out', type=Path)
    parser.add_argument('--ids', type=int, nargs='+', default=[321])
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--technique', type=int, help='test this technique in its species-specific animation slot')
    parser.add_argument('--slots', help='comma-separated animation slots; each gets a separate battle')
    parser.add_argument('--until-hit', action='store_true', help='finish a damage audit as soon as a hit is observed; no video')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--card', default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    parser.add_argument('--attach', action='store_true')
    parser.add_argument('--video', action='store_true')
    parser.add_argument('--partner', type=int, default=3)
    parser.add_argument('--screen', type=int, default=0, help='use an existing placement outside the forest fixture')
    parser.add_argument('--enemy-slot', type=int, default=0)
    parser.add_argument('--partner-attack', type=int, help='equip a partner animation slot and allow attacks to exercise Counter')
    parser.add_argument('--clear-path', action='store_true', help='move the tamer out of the attack corridor')
    parser.add_argument('--partner-stat', type=int, default=400)
    args = parser.parse_args()
    if args.until_hit and args.video:
        parser.error('--until-hit cannot be combined with fixed-duration --video')
    args.out.mkdir(parents=True, exist_ok=True)
    specs = species.load_content()
    ids = args.ids
    if args.all:
        ids = [r['id'] for r in json.loads((ROOT / 'content/modeldelta/models.json').read_text())['models']]
    results = []
    try:
        if args.attach:
            emu = P.emulator(args.cue)
        else:
            card = field_card(args.card, args.out / 'fixture.mcd', partner_type=args.partner)
            emu = P.emulator(args.cue)
            emu.env['EMU_ARGS'] = '-interpreter -debugger'
            emu.start(str(card))
            if emu.continue_game() != 0:
                raise RuntimeError('Continue failed')
        battle = Battle(emu)
        emu.gs('trigger', '1', '1')
        emu.gs('warp', '1', '0')
        battle.world(1)
        field_state = (args.out / 'field.state').resolve()
        battle.flow(False)
        E.api('/api/v1/lua/save?file=' + urllib.parse.quote(str(field_state)))
        battle.flow(True)
        for sid in ids:
            spec = specs[sid]
            if args.technique is not None:
                moves = species.table_rows(spec)['para']['moves']
                if args.technique not in moves:
                    continue
                sets = [[46 + moves.index(args.technique)]]
            else:
                sets = [[int(s, 0)] for s in args.slots.split(',')] if args.slots else [[46, 47, 48]]
            for slots in sets:
                out = args.out / (str(sid) + '-' + '-'.join(map(str, slots)))
                out.mkdir(exist_ok=True)
                # Independent starting state prevents care events, rewards and
                # prior map scripts from contaminating the next species.
                battle.flow(False)
                E.api('/api/v1/lua/load?file=' + urllib.parse.quote(str(field_state)))
                battle.flow(True)
                battle.start(spec, slots, args.screen, args.enemy_slot, args.partner_stat, args.partner_attack,
                             args.clear_path)
                E.api('/api/v1/lua/save?file=' + urllib.parse.quote(str((out / 'battle.state').resolve())))
                recorder = None
                if args.video:
                    recorder = subprocess.Popen(P.E + ['record', str(out / 'battle.mp4'), str(args.seconds), '20'],
                                                stdout=(out / 'recorder.log').open('w'), stderr=subprocess.STDOUT)
                try:
                    row = dict(species=sid, name=spec['name'], slots=slots,
                               partner=args.partner, partner_stat=args.partner_stat,
                               partner_attack=args.partner_attack, clear_path=args.clear_path,
                               **battle.watch(args.seconds, out, defend=args.partner_attack is None, stop_on_hit=args.until_hit))
                finally:
                    if recorder is not None:
                        recorder.wait(timeout=args.seconds + 30)
                        if recorder.returncode:
                            raise RuntimeError('Video capture failed')
                moves = species.table_rows(spec)['para']['moves']
                wanted = [moves[slot - 46] for slot in slots]
                technique_data = {int(path.name.split('-', 1)[0]): json.loads(path.read_text())
                                  for path in (ROOT / 'content/techniques').glob('*.json')}
                outgoing = any((move == 45 and args.partner_attack is not None) or
                               (move != 45 and technique_data[move]['range'] != 4) for move in wanted)
                row['requires_outgoing_damage'] = outgoing
                row['ok'] = bool(row['played']) and row['elapsed_frames'] > 20 and (not outgoing or row['damage'] > 0)
                results.append(row)
                (args.out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                print(json.dumps({k:v for k,v in row.items() if k != 'samples'}), flush=True)
                # The next case restores its clean field snapshot; reward
                # animations and care timers are outside this damage audit.
                battle.flow(False)
    finally:
        error = sys.exc_info()[1]
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr, file=sys.stderr)
        if sys.exc_info()[0] is not None:
            try:
                E.shot(str(args.out / 'failure.png'))
                E.api('/api/v1/lua/save?file=' + urllib.parse.quote(str((args.out / 'failure.state').resolve())))
            except Exception:
                pass
        P.run(P.E + ['stop'])
    return 0 if results and all(row['ok'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
