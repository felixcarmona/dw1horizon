#!/usr/bin/env python3
"""Play daily/permanent Mojyamon limits and North Star evolution on 2 MB."""
import argparse
import json
from pathlib import Path
import socket
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.birdramon_recruitment import field_card, bit
from tools.dev.playtest.ogre_tunnel import call, place
from tools.langpatch import elf_symbols


def counts(e):
    ram = e.ram(); at = e.A('INVENTORY') - 0x80000000
    types = struct.unpack_from('<30h', ram, at)
    return {i: ram[at + 60 + n] for n, i in enumerate(types) if i >= 0}


def trace(e, name):
    return int(e.run('lua', f'return MT.{name}').strip())


def talk(e, script=129, section=7):
    old = trace(e, 'lists')
    call(e, 'callScriptSection', [script, section, 1])
    for _ in range(20):
        e.wait(.5)
        if trace(e, 'lists') > old:
            e.wait(1)
            return
        e.press('CONFIRM', 6)
    raise AssertionError('trade list did not open')



def select_offer(e):
    # A short wall-time tap can miss a logic tick under interpreter load.
    events = ('amounts', 'refused', 'onceRefused')
    before = sum(trace(e, n) for n in events)
    for _ in range(6):
        e.press('CONFIRM', 12); e.wait(1)
        if sum(trace(e, n) for n in events) > before:
            return
    raise AssertionError('trade selection did not receive Confirm')


def accept_amount(e, expected):
    for _ in range(6):
        e.press('CONFIRM', 12); e.wait(1)
        if trace(e, 'trades') >= expected:
            return
    raise AssertionError(f'amount confirmation did not complete trade {expected}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=42167)
    p.add_argument('--out', type=Path, default=Path('build/mojyamon-proof'))
    p.add_argument('--card', type=Path, default=ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd')
    a = p.parse_args()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', a.port))
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(out / 'emu'))
    for name, (addr, _, _) in elf_symbols(a.exe + '.elf').items(): e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = {}
    raw = Path(a.exe).read_bytes()
    load = struct.unpack_from('<I', raw, 0x18)[0]
    shops = json.loads((ROOT / 'content/tables/shops.json').read_text())
    for symbol, key in (('MOJYAMON_ITEMS_GIVE', 'mojyamonGives'), ('MOJYAMON_ITEMS_GET', 'mojyamonTakes')):
        start = 0x800 + e.A(symbol) - load
        assert list(raw[start:start+12]) == shops[key], 'disc trade table differs from owned JSON'
    results['disc_tables_match_json'] = True
    try:
        e.start(field_card(a.card, out / 'native.mcd', partner_type=4))
        e.run('lua', f"MT_MOV=PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
        assert e.continue_game() == 0, 'Continue failed'
        assert e.in_control()
        results['ram_bytes'] = len(e.ram())
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0')
        for n in list(range(5, 15)) + [107, 108, 109] + list(range(789, 798)):
            e.gs('trigger', str(n), '0')
        e.poke('INVENTORY', struct.pack('<30h', 69, *([-1]*29)) + bytes([5]+[0]*29) + bytes(30) + bytes([10]))
        before = counts(e)
        assert before.get(69, 0) >= 5
        assert e.warp(134), 'Freezeland screen did not load'
        assert e.in_control()
        e.run('lua', f'''
MT={{lists=0,amounts=0,trades=0,refused=0,onceRefused=0,bp={{}}}}
local function hook(a,f) MT.bp[#MT.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'mojyamon-proof',f) end
hook({e.A('createMojyaTradeMenu')},function() MT.lists=MT.lists+1 end)
hook({e.A('openAmountBox')},function() if tonumber(PCSX.getRegisters().GPR.n.a0)==1 then MT.amounts=MT.amounts+1 end end)
hook({e.A('setMojyaItemTradedTrigger')},function() MT.trades=MT.trades+1 end)
hook({e.A('showMapHeadTextbox')},function() local r=PCSX.getRegisters().GPR.n
 if tonumber(r.a0)==12 and tonumber(r.a3)==1238 then MT.refused=MT.refused+1 end
 if tonumber(r.a0)==10 and tonumber(r.a3)==1238 then MT.onceRefused=MT.onceRefused+1 end end)
''')
        talk(e)
        e.run('shot', str(out / '01-trade-list.png'))
        select_offer(e)
        assert trace(e, 'amounts') == 1
        assert e.peek('MAX_SHOP_AMOUNT', 'B') == 1
        e.press('RIGHT', 6); e.wait(.5)
        assert e.peek('SHOP_AMOUNT', 'B') == 1
        e.run('shot', str(out / '02-one-per-day.png'))
        accept_amount(e, 1)
        assert trace(e, 'trades') == 1 and bit(e, 789)
        after = counts(e)
        assert after.get(69, 0) == before.get(69, 0)-1
        assert after.get(45, 0) == before.get(45, 0)+1
        assert e.in_control()
        results['first_trade'] = dict(input_before=before.get(69), input_after=after.get(69), reward_after=after.get(45), daily_bit=bit(e,789))
        talk(e); select_offer(e)
        assert trace(e, 'refused') == 1 and trace(e, 'amounts') == 1 and trace(e, 'trades') == 1, {n:trace(e,n) for n in ('lists','refused','amounts','trades')}
        assert counts(e) == after
        e.run('shot', str(out / '03-same-day-refused.png'))
        assert e.in_control()
        results['same_day_refused'] = True
        day = e.peek('DAY', 'h')
        call(e, 'advanceToTime', [9, 0])
        assert e.peek('DAY', 'h') == (day+1)%30
        results['day_before'] = day
        results['day_after'] = e.peek('DAY', 'h')
        assert not bit(e, 789) and bit(e,5)
        talk(e); select_offer(e)
        assert trace(e, 'amounts') == 2
        accept_amount(e, 2)
        assert trace(e, 'trades') == 2 and bit(e,789)
        final = counts(e)
        assert final.get(69,0) == after.get(69,0)-1
        assert final.get(45,0) == after.get(45,0)+1
        e.run('shot', str(out / '04-next-day-allowed.png'))
        results['next_day_allowed'] = True
        results['final_inventory'] = final
        assert e.in_control()
        call(e, 'giveItem', [0, 5])
        assert e.warp(133) and e.in_control()
        def north_star_offer():
            talk(e, 128, 6)
            for _ in range(2):
                e.press('DOWN', 6); e.wait(.5)
            select_offer(e)
        north_star_offer()
        assert trace(e, 'amounts') == 3
        assert e.peek('SHOP_ITEM_TYPE', 'B') == 0 and e.peek('MAX_SHOP_AMOUNT', 'B') == 1
        e.run('shot', str(out / '05-north-star-once-offer.png'))
        accept_amount(e, 3)
        assert trace(e, 'trades') == 3 and bit(e,13)
        once = counts(e)
        assert once.get(0)==4 and once.get(92)==1
        assert e.in_control()
        north_star_offer()
        assert trace(e, 'onceRefused') == 1 and trace(e,'amounts') == 3
        assert counts(e) == once and e.in_control()
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0')
        call(e, 'advanceToTime', [9, 0])
        assert bit(e,13) and not bit(e,797)
        north_star_offer()
        assert trace(e,'onceRefused') == 2 and trace(e,'amounts') == 3
        assert counts(e) == once
        e.run('shot', str(out / '06-north-star-next-day-refused.png'))
        assert e.in_control()
        results['north_star_once_per_save'] = True
        results['north_star_still_refused_after_day_reset'] = True
        # Move to File City's open floor before feeding.
        assert e.warp(1) and e.in_control()
        e.run('pause')
        try:
            place(e, 0, 0)
            partner_pos = e.peek('PARTNER_ENTITY+4', 'I')
            e.run('poke', hex(partner_pos + 0x78), struct.pack('<3i', -200, 0, -100).hex())
            e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', -200 << 15, 0, -100 << 15))
        finally:
            e.run('resume')
        e.wait(3)
        # Use the actual field feeding entry point. No evolution target/state is injected.
        assert e.peek('PARTNER_ENTITY','i') == 4, 'Betamon fixture is not a Rookie'
        assert raw[0x800 + e.A('EVOLUTION_ITEM_TARGET') - load + 92 - 71] == 238
        slot = e.peek('INVENTORY','30h').index(92)
        e.poke('INVENTORY_POINTER', bytes([slot]))
        e.run('lua', f"""
MT.evoTarget=0; MT.applied=0
local m=PCSX.getMemPtr()
local function u16(a) return tonumber(m[a-0x80000000])+256*tonumber(m[a-0x80000000+1]) end
MT.bp[#MT.bp+1]=PCSX.addBreakpoint({e.A('gameLoop')},'Exec',4,'north-star-target',function()
 if tonumber(m[{e.A('PARTNER_STATE')}-0x80000000])==13 and u16({e.A('EVOLUTION_TARGET')})==238 then MT.evoTarget=238 end
end)
MT.bp[#MT.bp+1]=PCSX.addBreakpoint({e.A('EVL_applyEvolution')},'Exec',4,'north-star-apply',function()
 if tonumber(m[{e.A('PARTNER_STATE')}-0x80000000])==13 and u16({e.A('EVOLUTION_TARGET')})==238 then MT.applied=MT.applied+1 end
end)
""")
        e.run('shot', str(out / '07-before-north-star.png'))
        call(e, 'startFeedingItem', [92])
        deadline = time.monotonic()+150
        while time.monotonic() < deadline:
            if e.peek('PARTNER_ENTITY','i') == 238 and e.peek('PARTNER_STATE','b') != 13:
                break
            e.wait(1)
            # Advance any end-of-evolution text; the game chooses and applies its target.
            if trace(e,'evoTarget') == 238:
                e.press('CONFIRM', 6)
        assert e.peek('PARTNER_ENTITY','i') == 238, 'North Star did not evolve to Dolphmon'
        assert trace(e,'evoTarget') == 238 and trace(e,'applied') >= 1
        assert counts(e).get(92,0)==0, 'North Star was not consumed'
        assert e.in_control()
        e.gs('set','gametime_running=0')
        e.run('shot', str(out / '08-dolphmon-after-north-star.png'))
        results['north_star_evolution'] = dict(from_species=4, target=238,
            observed_target=trace(e,'evoTarget'), evolution_applied=trace(e,'applied'), item_consumed=True)
        results['trace'] = {n:trace(e,n) for n in ('lists','amounts','trades','refused','onceRefused')}
        print(json.dumps(results, indent=2), flush=True)
        (out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    except BaseException as error:
        results['error'] = str(error)
        e.run('shot', str(out / 'failure.png'), check=False)
        print(json.dumps(results, indent=2), flush=True)
        (out / 'failure.json').write_text(json.dumps(results, indent=2)+'\n')
        raise
    finally:
        e.stop()


if __name__ == '__main__':
    main()
