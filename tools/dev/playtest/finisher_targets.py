#!/usr/bin/env python3
"""Record finisher HP changes on original 2 MB RAM using species_proof's battle.

EMU_PORT and DW_SYMS must select this disc's emulator and executable.
Usage: .venv/bin/python -m tools.dev.playtest.finisher_targets DISC DIGI OUT ID ...
       [--trials 2] [--baseline] [--card CARD] [--sounds]
Baseline requires a caster hit; fixed runs require enemy damage and no self damage.
With --sounds (slower: the emulator runs as an interpreter with its debugger, the only mode where Lua
breakpoints fire) every battle sound the effect plays (bank 8: STD_playEFESound's playSound and
playSound2) is logged as [sound id, video frame at 60 Hz from the recording's start] in the result's "sounds".
"""
import argparse
import functools
import json
from pathlib import Path
import subprocess
import threading
import time

from tools.dev.playtest import species_proof as P

PARTNER_HP = 'PARTNER_ENTITY.digimonEntity.stats.current.currentHP'
CYCLES_PER_FRAME = 33868800 / 60


def log_sounds(emu):
    """Starts logging the battle sounds (bank 8) with the CPU cycle they start at."""
    hooks = ' '.join(
        f"FT_SND.bp[#FT_SND.bp+1]=PCSX.addBreakpoint({emu.A(name)},'Exec',4,'finisher-sound',function() "
        "local r=PCSX.getRegisters() if r.GPR.n.a0==8 then "
        "FT_SND.log[#FT_SND.log+1]=tostring(r.GPR.n.a1)..':'..tostring(PCSX.getCPUCycles()) end end)"
        for name in ('playSound', 'playSound2'))
    emu.run('lua', "if FT_SND then for _,b in ipairs(FT_SND.bp) do b:remove() end end "
                   f"FT_SND={{bp={{}},log={{}}}} {hooks} return PCSX.getCPUCycles()")


def logged_sounds(emu, start):
    """[[id, frame]] of the sounds logged since log_sounds, frames counted from `start` (CPU cycles); stops logging."""
    out = emu.run('lua', "local s=table.concat(FT_SND.log,',') for _,b in ipairs(FT_SND.bp) do b:remove() end "
                         "FT_SND.bp={} return s").strip()
    pairs = [x.split(':') for x in out.split(',') if ':' in x]
    return [[int(i), round((int(c.rstrip('ULul')) - start) / CYCLES_PER_FRAME)] for i, c in pairs]


def bind_memory():
    """Use the same DWARF field resolver with batched HTTP RAM access."""
    from tools.dev import emulator as E, memory_inspector as M
    variables, types = M.build_index()
    resolve = functools.lru_cache(None)(lambda expression: M.resolve_expr(expression, variables, types))

    def read(*names):
        M._ram = E.api('/api/v1/cpu/ram/raw')
        if len(M._ram) != 0x200000: raise RuntimeError('Original 2 MB RAM required')
        values = {}
        for name in names:
            address, kind = resolve(name)
            values[name] = M.scalar(kind, address)
        return values

    def write(*assignments):
        E.api('/api/v1/execution-flow?function=pause')
        try:
            for assignment in assignments:
                name, value = assignment.split('=', 1)
                address, kind = resolve(name)
                data = M.encode(kind, value)
                E.api(f'/api/v1/cpu/ram/raw?offset={address & 0x1fffff}&size={len(data)}', data=data)
        finally:
            E.api('/api/v1/execution-flow?function=start')
    P.mem, P.mset = read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cue')
    parser.add_argument('digi')
    parser.add_argument('out', type=Path)
    parser.add_argument('ids', nargs='+', type=int)
    parser.add_argument('--trials', type=int, default=2)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--attach', action='store_true', help='use the already running disc on EMU_PORT')
    parser.add_argument('--card', default='build/states/file-city.mcd')
    parser.add_argument('--sounds', action='store_true', help='log the battle sounds the effect plays')
    args = parser.parse_args()
    if args.sounds:
        plain = P.emulator
        def debugging(cue):
            emu = plain(cue)
            emu.env['EMU_ARGS'] = '-interpreter -debugger'
            return emu
        P.emulator = debugging
    if not all(P.emulator(args.cue).has(name) for name in ('MOD_BOOT_LANGUAGE', 'labCount', 'labChoices')):
        parser.error('DW_SYMS needs the disc executable, its .elf and .elf.map with local symbols')
    args.out.mkdir(parents=True, exist_ok=True)
    _, _, records = P.species.read_archive(args.digi)
    results = []
    current = {}

    def watch(slot, seconds, launch):
        initial = P.mem(PARTNER_HP, *P.ENEMY_HP)
        samples, enemy_damage, self_damage = [], 0, 0
        start = int(P.EMU.run('lua', 'return PCSX.getCPUCycles()').strip().rstrip('ULul'))
        if args.sounds: log_sounds(P.EMU)
        with open(folder / 'recorder.log', 'w') as log:
            recorder = subprocess.Popen(P.E + ['record', str(folder / 'finisher.mp4'), '18'],
                                        stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + seconds
        errors = []
        def trigger():
            try: launch()
            except BaseException as error: errors.append(error)
        launcher = threading.Thread(target=trigger)
        launcher.start()
        try:
            while time.monotonic() < deadline:
                values = P.mem(P.ANIM, P.FRAME, 'GAME_STATE', 'NO_AI_FLAG',
                               'EFE_TARGET_ENTITY_INDEX', PARTNER_HP, *P.ENEMY_HP)
                values['GAME_STATE'] = P.game_state(values)
                samples.append(values)
                self_damage = max(0, initial[PARTNER_HP] - values[PARTNER_HP])
                enemy_damage = max(0, *(initial[k] - values[k] for k in P.ENEMY_HP))
                if self_damage or enemy_damage:
                    P.seq(f'shot {folder}/hit.png')
                    break
                time.sleep(0.05)
        finally:
            try:
                recorder.wait(timeout=300)   # 18 emulated seconds, whatever the host load
            except subprocess.TimeoutExpired:
                recorder.terminate()
                recorder.wait(timeout=5)
        if recorder.returncode:
            raise RuntimeError(f'Video capture failed; see {folder}/recorder.log')
        launcher.join(timeout=30)
        if launcher.is_alive(): raise RuntimeError('Finisher input did not complete')
        if errors: raise errors[0]
        final = P.mem(P.ANIM, P.FRAME, 'GAME_STATE', 'NO_AI_FLAG',
                      'EFE_TARGET_ENTITY_INDEX', PARTNER_HP, *P.ENEMY_HP)
        final['GAME_STATE'] = P.game_state(final)
        samples.append(final)
        self_damage = max(self_damage, initial[PARTNER_HP] - final[PARTNER_HP])
        enemy_damage = max(enemy_damage, *(initial[k] - final[k] for k in P.ENEMY_HP))
        P.seq(f'shot {folder}/settled.png')
        current.update(self_damage=self_damage, enemy_damage=enemy_damage, hp_before=initial, samples=samples)
        if args.sounds: current['sounds'] = logged_sounds(P.EMU, start)
        return samples, enemy_damage

    def freeze_opponents():
        # Let existing effects finish during preparation, then keep ordinary
        # enemy attacks from being mistaken for the finisher's caster damage.
        P.mset(*[f'COMBAT_DATA.fighter[{i}].cooldown=30000' for i in range(1, 4)],
               *[f'NPC_ENTITIES[{i}].digimonEntity.stats.current.currentMP=0' for i in range(P.NPC_SLOTS)])

    try:
        if args.attach:
            P.EMU = P.emulator(args.cue)
        elif not P.boot(args.cue, args.card):
            raise RuntimeError('Could not continue into the world')
        bind_memory()
        for species in args.ids:
            if len(P.EMU.ram()) != 0x200000:
                raise RuntimeError('Original 2 MB RAM required')
            P.lab_evolve(species, str(args.out))
            if P.partner_type() != species:
                raise RuntimeError(f'Evolution to {species} failed')
            for trial in range(args.trials):
                folder = args.out / f'{species}-{trial + 1}'
                folder.mkdir(exist_ok=True)
                current = dict(species=species, trial=trial + 1, ram_bytes=0x200000, enemy_ai_isolated=True)
                # Equip only the finisher so normal attacks cannot end the fight
                # during the helper's preparation window. Keep its real slot.
                moves = [move if 58 <= move <= 112 else 255 for move in records[species]['para']['moves']]
                P.battle(species, moves, str(folder), current, prepare=freeze_opponents,
                         launch_and_watch=watch, warmup=6)
                current['ok'] = (current.get('in_battle', False) and current.get('frames_advance', False) and
                                 current.get('finisher_played', False) and current.get('game_state_after') == 0 and
                                 (args.baseline or (current.get('enemy_damage', 0) > 0 and
                                                   current.get('self_damage', 0) == 0)))
                results.append(current)
                (args.out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                print(json.dumps({k: v for k, v in current.items() if k != 'samples'}), flush=True)
    finally:
        P.run(P.E + ['stop'])
        (args.out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
    summary = dict(trials=len(results), self_hit_reproduced=any(row.get('self_damage', 0) > 0 for row in results))
    summary['ok'] = bool(results) and all(row['ok'] for row in results) and (
        not args.baseline or summary['self_hit_reproduced'])
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
