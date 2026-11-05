#!/usr/bin/env python3
"""Play one Mojyamon exchange, its same-day refusal and next-day success on 2 MB."""
import argparse
import json
from pathlib import Path
import socket
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.birdramon_recruitment import field_card, bit
from tools.dev.playtest.ogre_tunnel import call
from tools.langpatch import elf_symbols


def counts(e):
    ram = e.ram(); at = e.A('INVENTORY') - 0x80000000
    types = struct.unpack_from('<30h', ram, at)
    return {i: ram[at + 60 + n] for n, i in enumerate(types) if i >= 0}


def trace(e, name):
    return int(e.run('lua', f'return MT.{name}').strip())


def talk(e):
    old = trace(e, 'lists')
    call(e, 'callScriptSection', [129, 7, 1])
    for _ in range(20):
        e.wait(.5)
        if trace(e, 'lists') > old:
            e.wait(1)
            return
        e.press('CONFIRM', 6)
    raise AssertionError('trade list did not open')


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
        e.start(field_card(a.card, out / 'native.mcd'))
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
MT={{lists=0,amounts=0,trades=0,refused=0,bp={{}}}}
local function hook(a,f) MT.bp[#MT.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'mojyamon-proof',f) end
hook({e.A('createMojyaTradeMenu')},function() MT.lists=MT.lists+1 end)
hook({e.A('openAmountBox')},function() if tonumber(PCSX.getRegisters().GPR.n.a0)==1 then MT.amounts=MT.amounts+1 end end)
hook({e.A('setMojyaItemTradedTrigger')},function() MT.trades=MT.trades+1 end)
hook({e.A('showMapHeadTextbox')},function() local r=PCSX.getRegisters().GPR.n
 if tonumber(r.a0)==12 and tonumber(r.a3)==1238 then MT.refused=MT.refused+1 end end)
''')
        talk(e)
        e.run('shot', str(out / '01-trade-list.png'))
        e.press('CONFIRM', 6); e.wait(2)
        assert trace(e, 'amounts') == 1
        assert e.peek('MAX_SHOP_AMOUNT', 'B') == 1
        e.press('RIGHT', 6); e.wait(.5)
        assert e.peek('SHOP_AMOUNT', 'B') == 1
        e.run('shot', str(out / '02-one-per-day.png'))
        e.press('CONFIRM', 6); e.wait(2)
        assert trace(e, 'trades') == 1 and bit(e, 789)
        after = counts(e)
        assert after.get(69, 0) == before.get(69, 0)-1
        assert after.get(45, 0) == before.get(45, 0)+1
        assert e.in_control()
        results['first_trade'] = dict(input_before=before.get(69), input_after=after.get(69), reward_after=after.get(45), daily_bit=bit(e,789))
        talk(e); e.press('CONFIRM', 6); e.wait(2)
        assert trace(e, 'refused') == 1 and trace(e, 'amounts') == 1 and trace(e, 'trades') == 1
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
        talk(e); e.press('CONFIRM', 6); e.wait(2)
        assert trace(e, 'amounts') == 2
        e.press('CONFIRM', 6); e.wait(2)
        assert trace(e, 'trades') == 2 and bit(e,789)
        final = counts(e)
        assert final.get(69,0) == after.get(69,0)-1
        assert final.get(45,0) == after.get(45,0)+1
        e.run('shot', str(out / '04-next-day-allowed.png'))
        results['next_day_allowed'] = True
        results['final_inventory'] = final
        results['trace'] = {n:trace(e,n) for n in ('lists','amounts','trades','refused')}
        print(json.dumps(results, indent=2), flush=True)
        (out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    finally:
        e.stop()


if __name__ == '__main__':
    main()
