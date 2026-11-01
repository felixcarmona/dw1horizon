#!/usr/bin/env python3
"""Every branch of the extended story's decisions rejoins, on the original 2 MB.

The game runs the real handlers. Only the saved state before a scene is set by
flag, and battles are seeded at one HP as in birdramon_recruitment.py. Each case
restores one field checkpoint, so one failure does not hide the next.
"""
import argparse, json, re, socket, struct, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols
from tools.dev.playtest.birdramon_recruitment import field_card, install, call_section, bit

MOD = ROOT / 'story/mods/what-the-island-forgot'
FLAGS = json.loads((MOD / 'save.lock').read_text())['flags']
FLAGS.update({m[1]: int(m[2]) for m in re.finditer(r'alias flag (\w+) = (\d+);', (ROOT / 'story/base/names.dws').read_text())})
FLAGS.update(game_beaten=50, trigger355=355)
GEAR = 120


class Run:
    def __init__(self, e, out):
        self.e, self.out = e, out

    def flag(self, name):
        return bit(self.e, FLAGS.get(name, name) if isinstance(name, str) else name)

    def set(self, **flags):
        for name, value in flags.items():
            self.e.gs('trigger', str(FLAGS[name]), str(int(value)))

    def recruit(self, **species):
        for name, value in species.items():
            self.e.gs('trigger', str(200 + self.number(name)), str(int(value)))

    def number(self, name):
        stubs = (ROOT / 'typings/dw/__init__.pyi').read_text()
        return int(re.search(rf'^    {name} = (\d+)', stubs[stubs.index('class Species'):], re.M)[1])

    def recruited(self, name):
        return bit(self.e, 200 + self.number(name))

    def shot(self, name):
        self.e.run('shot', str(self.out / f'{name}.png'), check=False)

    def go(self, screen, entry=0, deadline=90):
        """Warp and close whatever the arrival says, until the tamer is free on that screen."""
        e = self.e
        e.api('/api/v1/execution-flow?function=pause')
        try:
            e.poke('TAMER_SUB_STATE', b'\0')
            e.poke('TARGET_MAP', struct.pack('<h', screen))
            e.poke('CURRENT_EXIT', bytes([entry]))
            e.poke('TAMER_STATE', bytes([5]))
        finally:
            e.api('/api/v1/execution-flow?function=start')
        self.settle(screen, deadline)

    def settle(self, screen=None, deadline=90):
        e = self.e
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            ram = e.ram()
            if (screen is None or e.peek('CURRENT_SCREEN', 'h', ram) == screen) and e.peek('TAMER_STATE', 'b', ram) == 0 \
                    and e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1:
                e.wait(.6)
                ram = e.ram()
                if e.peek('TAMER_STATE', 'b', ram) == 0 and e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1: return
            if e.peek('CURRENT_SCREEN', 'h', ram) == screen or screen is None: e.press('CONFIRM', 6)
            e.wait(.5)
        self.shot(f'stuck-{screen}')
        raise AssertionError(f'not free on screen {screen}: on {e.peek("CURRENT_SCREEN", "h")}')

    def advance(self, done, deadline=120, name=''):
        """Close boxes and take the top option until done() holds."""
        e = self.e
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            if done(): return
            if e.peek('GAME_STATE', 'H') != 1: e.press('CONFIRM', 6)
            e.wait(.4)
        self.shot('stuck-' + (name or 'advance'))
        raise AssertionError('never reached: ' + (name or 'advance'))

    def talk(self, slot, done, deadline=120, name=''):
        """Enter the NPC's real talk section: walking up to it is not what these cases prove."""
        e = self.e
        e.poke('TALKED_TO_ENTITY', bytes([5 + slot]))
        call_section(e, e.peek('CURRENT_SCRIPT_ID', 'H'), 5 + slot)
        e.wait(1.5)
        self.advance(done, deadline, name)

    def npc(self, slot):
        """The species standing in a slot, or None."""
        ram = self.e.ram()
        species = self.e.peek(f'NPC_ENTITIES+{slot * 104}', 'i', ram)
        return species if self.e.peek(f'NPC_ENTITIES+{slot * 104 + 52}', 'b', ram) else None    # Entity.isOnMap

    def items(self, *types):
        kinds = list(types) + [-1] * (30 - len(types))
        self.e.poke('INVENTORY', struct.pack('<30h', *kinds))
        self.e.poke('INVENTORY+60', bytes([1] * len(types) + [0] * (30 - len(types))))

    def has(self, item):
        return item in self.e.peek('INVENTORY', '30h')


def close_paper(r):
    for _ in range(12):
        if r.e.peek('IS_SCRIPT_PAUSED', 'i') == 1 and r.e.peek('TAMER_STATE', 'b') == 0: return
        r.e.press('CANCEL', 6); r.e.wait(.6)
    raise AssertionError('the newspaper did not close')


def skullgreymon(r):
    r.set(root2=True, myotismon_joined_city=True, myotismon_freed=True, memory_news=True)
    r.recruit(Myotismon=True, SkullGreymon=False)
    r.e.gs('pstat', '1', '40')
    # The newspaper in the window before it comes back: Myotismon stays.
    r.recruit(Shellmon=True)
    r.go(180)
    call_section(r.e, 163, 82)
    r.e.wait(2)
    for _ in range(10):           # every page: "Next" is the top option
        r.e.press('CONFIRM', 6); r.e.wait(.6)
    close_paper(r)
    paper = dict(myotismon=r.recruited('Myotismon'), missing=r.flag('myotismon_missing'))
    assert paper == dict(myotismon=True, missing=False), paper
    r.e.gs('pstat', '1', '10')    # house 218
    r.go(218)
    first = dict(news=r.flag('memory_news'), skull=r.recruited('SkullGreymon'))
    assert first == dict(news=False, skull=False), first
    r.go(168); r.e.gs('pstat', '1', '10'); r.go(218)
    assert r.recruited('SkullGreymon')
    r.shot('skullgreymon-home')
    prosperity = r.e.peek('SCRIPT_STATE+346', 'B')
    r.e.gs('pstat', '1', '40')
    r.go(180); call_section(r.e, 163, 82)
    r.advance(lambda: r.flag('skullgreymon_debut_news_read'), name='debut news')
    close_paper(r)
    assert r.recruited('Myotismon')
    # The second house (205) does the same: SkullGreymon, with the news told first.
    r.set(memory_news=True); r.recruit(SkullGreymon=False); r.e.gs('pstat', '1', '60')
    r.go(205); assert not r.flag('memory_news') and not r.recruited('SkullGreymon')
    r.go(168); r.e.gs('pstat', '1', '60'); r.go(205)
    assert r.recruited('SkullGreymon')
    return dict(paper=paper, prosperity_after_join=prosperity)


def lab_corridor(r):
    r.set(root2=True); r.recruit(SkullGreymon=False)
    r.go(68); gone = r.npc(1)
    r.recruit(SkullGreymon=True)
    r.go(68); back = r.npc(1)
    assert back is not None and gone is None, (gone, back)
    # "Keep him" can be taken back at the mansion.
    r.set(root2=False, myotismon_joined_city=True)
    r.go(55)
    assert r.npc(0) is not None
    r.talk(0, lambda: r.flag('root2'), name='close the circle')
    r.settle(55)
    assert r.recruited('SkullGreymon')
    return dict(patrol_gone=gone, patrol_back=back)


def angemon(r):
    r.set(root3=True, memory_news=False); r.recruit(Angemon=False)
    r.e.gs('pstat', '1', '10')
    r.go(311); keeper = r.npc(0)
    assert keeper is not None
    r.e.gs('pstat', '1', '10')
    r.go(218)
    assert r.recruited('Angemon')
    r.shot('angemon-home')
    r.go(311)
    assert r.npc(0) != keeper, 'Angemon has left the wall'
    # "Come to the city" is asked again.
    r.set(root3=False, vault_kept=True); r.recruit(Angemon=True)
    r.go(97); call_section(r.e, 93, 52)
    r.advance(lambda: r.e.peek('CURRENT_SCREEN', 'h') == 310, name='down to the wall')
    r.settle(310)
    assert not r.flag('vault_kept') and r.npc(0) is not None
    return dict(keeper=keeper)


def monzaemon(r):
    r.set(toy_tale_heard=False, gear_for_andromon=True, gear_offered=True, m3_archive=False, island_history_read=True,
          factorial_town_reopened=True, factory_asked=True, factory_kept_shut=False)
    r.recruit(WaruMonzaemon=True, Monzaemon=False, Andromon=True)
    r.items(GEAR); r.e.gs('pstat', '9', '0')
    r.go(146)
    assert r.has(GEAR)
    r.settle(146)
    r.talk(0, lambda: r.e.peek('IS_SCRIPT_PAUSED', 'i') == 1, name='toys wait')   # "bring it back after"
    assert r.has(GEAR) and not r.flag('toy_tale_heard')
    r.go(157)
    r.talk(0, lambda: r.flag('m3_archive'), name='archive')
    r.settle(157)
    assert r.has(GEAR), 'the gear stays with the tamer'
    assert r.e.peek('SCRIPT_STATE+354', 'B') == 2, 'M3 counts two'
    r.go(146)
    r.talk(0, lambda: r.flag('toy_tale_heard') or r.recruited('Monzaemon'), deadline=240, name='toys song')
    r.shot('monzaemon-song')
    r.advance(lambda: r.recruited('Monzaemon'), deadline=240, name='monzaemon joins')
    assert not r.has(GEAR)
    return dict(joined=True)


def gear_old_save(r):
    r.set(gear_for_andromon=True, gear_offered=True, m3_archive=True, toy_tale_heard=False, island_history_read=True,
          factorial_town_reopened=True, factory_asked=True, factory_kept_shut=False)
    r.recruit(WaruMonzaemon=True, Andromon=True)
    r.items(*([1] * 30))              # a full bag: Andromon keeps it for the next visit
    r.go(157); r.talk(0, lambda: r.e.peek('IS_SCRIPT_PAUSED', 'i') == 1, name='full bag')
    r.settle(157)
    full = r.has(GEAR)
    r.items()
    r.talk(0, lambda: r.has(GEAR), name='gear back')
    r.settle(157)
    # Given to the Toys first: Hagurumon lets Andromon read it.
    r.items(); r.set(gear_for_andromon=False, m3_archive=False, toy_tale_heard=True); r.e.gs('pstat', '9', '0')
    r.talk(0, lambda: r.flag('m3_archive'), name='read after the toys')
    r.settle(157)
    assert r.e.peek('SCRIPT_STATE+354', 'B') == 2 and not r.has(GEAR)
    return dict(full_bag_gave_it=full)


def post(r):
    r.set(post_kept=True, post_guided=False, m11_field=False, bone_field_visited=False)
    r.recruit(Tyrannomon=True)
    r.go(82)
    assert not r.flag('post_kept'), 'the offer comes back on entering'
    assert r.npc(3) is not None
    r.talk(3, lambda: r.flag('post_guided'), name='guide me')
    r.settle(82, 120)
    r.shot('post-guided')
    r.go(81); gone81 = r.npc(2)
    r.go(82); gone82 = r.npc(3)
    assert gone81 is None and gone82 is None, (gone81, gone82)
    r.go(306); assert r.npc(0) is not None
    r.talk(0, lambda: r.flag('m11_field'), name='M11')
    r.settle(306)
    r.go(82); back82 = r.npc(3)
    r.go(81); back81 = r.npc(2)
    assert back82 is not None and back81 is not None, (back82, back81)
    r.go(306); keeper = r.npc(0)
    return dict(back82=back82, back81=back81, field_master_gone=keeper)


def factory(r):
    r.set(factory_kept_shut=True, factory_asked=True, factorial_town_reopened=True, island_history_read=True,
          factory_guards_passed=True)
    r.recruit(Andromon=False)
    r.go(155); gone = r.npc(0)
    r.shot('factory-shut')
    r.go(157)
    assert not r.flag('factory_asked')
    r.talk(0, lambda: not r.flag('factory_kept_shut'), name='restart')
    r.settle(157)
    r.go(155); back = r.npc(0)
    r.shot('factory-back')
    assert gone is None and back is not None, (gone, back)     # the balanced slot's species may differ from the script's name
    return dict(back=back)


def motor(r):
    r.set(ogre_fortress_cleared=True, root1=False, m5_notebook=False, Canyon_b0=False, Canyon_b1=True)
    r.go(48); call_section(r.e, 48, 51)
    r.advance(lambda: r.e.peek('CURRENT_SCREEN', 'h') == 302, name='lift down, chase given up')
    r.settle(302)
    assert r.flag('Canyon_b0') and not r.flag('Canyon_b1'), 'the band is back in the Engine Room'
    r.go(300); band = r.npc(0)
    assert band is not None
    r.set(m5_notebook=True, Canyon_b0=False, Canyon_b1=True)
    r.go(48); call_section(r.e, 48, 51)
    r.advance(lambda: r.e.peek('CURRENT_SCREEN', 'h') == 302, name='lift down, Motor left')
    r.settle(302)
    e = r.e
    e.api('/api/v1/execution-flow?function=pause')
    e.poke('TAMER_SUB_STATE', b'\0'); e.poke('TARGET_MAP', struct.pack('<h', 300)); e.poke('CURRENT_EXIT', b'\0'); e.poke('TAMER_STATE', bytes([5]))
    e.api('/api/v1/execution-flow?function=start')
    r.advance(lambda: r.flag('root1'), name='the Motor again')
    r.shot('motor-again')
    r.settle(300)
    return dict(band=band, root1=True)


def devimon(r):
    r.set(root2=True, mt_infinity_devimon_beaten=True, devimon_fought=False, shortcut_taken=True)
    r.go(312)
    assert r.npc(0) == 130, r.npc(0)
    r.e.gs('set', 'partner.stats.off=900', 'partner.stats.def=900', 'partner.stats.speed=900',
           'partner.stats.currentHP=9000', 'partner.stats.currentMP=9000')
    install(r.e, 'won')
    r.talk(0, lambda: r.flag('devimon_fought'), deadline=240, name='Devimon')
    r.settle(312)
    r.go(312); gone = r.npc(0)
    assert gone is None
    r.recruit(Megadramon=False)
    r.go(254, deadline=120)
    assert r.npc(6) is not None, 'Megadramon stays on its terrace'
    return dict(devimon='fought', megadramon=r.npc(6))


def postgame(r):
    out = {}
    r.set(game_beaten=True, root1=True, root2=True, root3=True)
    r.recruit(Koromon=False, Devimon=True)
    for portal, screen, slot in ((3, 47, 3), (2, 66, 1)):
        r.e.gs('pstat', str(r.portal), str(portal))
        r.e.api('/api/v1/execution-flow?function=pause')
        r.e.poke('TAMER_SUB_STATE', b'\0'); r.e.poke('TARGET_MAP', struct.pack('<h', screen)); r.e.poke('CURRENT_EXIT', b'\0'); r.e.poke('TAMER_STATE', bytes([5]))
        r.e.api('/api/v1/execution-flow?function=start')
        r.e.wait(8)
        out[str(screen)] = r.npc(slot)
        assert out[str(screen)] is not None, screen
    return out


def old_saves(r):
    # 4.4: game beaten, nobody came, no rewards, Airdramon dead, no portal.
    r.set(game_beaten=True, airdramon_killed=True, trigger355=False, myotismon_joined_city=True, myotismon_missing=True)
    r.recruit(Devimon=False, MetalGreymonVirus=False, Airdramon=False, Myotismon=False, Koromon=False)
    r.e.gs('pstat', str(r.portal), '0'); r.e.gs('pstat', '1', '40')
    r.go(168)
    result = dict(devimon=r.recruited('Devimon'), metalgreymon=r.recruited('MetalGreymonVirus'), airdramon=r.recruited('Airdramon'),
                  myotismon=r.recruited('Myotismon'), missing=r.flag('myotismon_missing'), killed=r.flag('airdramon_killed'),
                  healed=r.flag('trigger355'), portal=r.e.peek(f'SCRIPT_STATE+{345 + r.portal}', 'B'),
                  prosperity=r.e.peek('SCRIPT_STATE+346', 'B'))
    r.shot('old-save-city')
    assert result['devimon'] and result['metalgreymon'] and result['airdramon'] and result['myotismon'], result
    assert not result['missing'] and not result['killed'] and result['healed'] and result['portal'] in (1, 2, 3), result
    return result


CASES = dict(skullgreymon=skullgreymon, lab_corridor=lab_corridor, angemon=angemon, monzaemon=monzaemon, gear_old_save=gear_old_save,
             post=post, factory=factory, motor=motor, devimon=devimon, postgame=postgame, old_saves=old_saves)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=45139)
    p.add_argument('--out', type=Path, default=Path('build/convergence-proof'))
    p.add_argument('--card', type=Path, default=ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd')
    p.add_argument('cases', nargs='*', choices=[*CASES, []])
    args = p.parse_args()
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', args.port))
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(args.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    r = Run(e, out)
    r.portal = int(re.search(r'alias \w+ back_dimension_portal = (\d+)', (ROOT / 'story/base/names.dws').read_text())[1])
    results = {}
    try:
        e.start(field_card(args.card, out / 'native.mcd'))
        e.run('lua', f"""BR_MOV=PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function()
 PCSX.getRegisters().GPR.n.a1=0
end)""")
        assert e.continue_game() == 0, 'Continue failed'
        e.wait(8); assert e.in_control()
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0', 'partner.para.condition=0',
             'partner.para.foodLevel=100', 'partner.para.remainingLifetime=1000', 'gametime_running=0')
        e.run('save', str(out / 'field.state'))
        for name in args.cases or CASES:
            e.run('load', str(out / 'field.state')); e.run('lua', 'PCSX.resumeEmulator()')
            start = time.monotonic()
            try:
                results[name] = dict(ok=True, **CASES[name](r))
                print('PASS', name, results[name], f'{time.monotonic() - start:.0f}s', flush=True)
            except Exception as error:
                results[name] = dict(ok=False, error=repr(error), trace=traceback.format_exc()[-600:])
                r.shot('failed-' + name)
                print('FAIL', name, repr(error), f'{time.monotonic() - start:.0f}s', flush=True)
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
    finally:
        e.stop()
    sys.exit(0 if all(v['ok'] for v in results.values()) else 1)


if __name__ == '__main__':
    main()
