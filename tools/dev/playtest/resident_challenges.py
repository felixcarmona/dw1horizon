#!/usr/bin/env python3
"""Resident challenges end to end (content/tables/resident-challenges.json, docs/mods/resident-challenges.md).

  xvfb-run -a python3 tools/dev/playtest/resident_challenges.py DISC --exe EXE --card CARD [--partner TYPE]

Original 2 MB RAM. With the game beaten (flag 50) and every challenger recruited, it lets the clock run over midnight
and requires: a challenger picked (its row in the saved var, its bit in the bag), absent from its city home and waiting
at its recruit site; its fight starts with every stat max(sheet x (100 + sheetPercent), partner x (100 + partnerPercent))
/ 100, no late-game step (NORMAL fromHp 0) and an empty bag, all put back after the battle; a lost fight leaves it at
its site with the won flag clear; a won fight pays the item and the bits, sets the won flag and it runs off. A second
midnight picks another resident, never the same, and adds its bit to the bag. Screenshots and result.json under --out.
"""
from pathlib import Path
import argparse
import json
import re
import struct
import sys
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols

MOD = ROOT / 'story/mods/what-the-island-forgot'
FROM_HP = 175                      # MOD_BT_NORMAL_FROM_HP in include/dw/mod_battle.h
WREGS = 668                        # ScriptState.wregs (include/dw/script.h): smth, cards, triggers, pstats, stack[8]
BAG_WREGS = 5                      # the bag's saved wide registers (tools/city_residents.py: CHALLENGE_MAX / 16 rounded up)


def species_sheets():
    return {s['id']: s for p in (ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}


class Run:
    def __init__(self, e, doc, out):
        self.e, self.doc, self.out = e, doc, out
        self.save = doc['save']; self.rows = doc['residents']; self.rule = doc['rule']
        self.log = {}
        self.fixture = None; self.fixture_row = 0

    def pstat(self, n):
        return int(re.search(r'= (\d+)', self.e.gs('pstat', str(n))).group(1))

    def flag(self, n):
        return int(re.search(r'= (\d+)', self.e.gs('trigger', str(n))).group(1))

    def recruit(self, species):
        if species < 112: self.e.gs('trigger', str(200 + species), '1'); return
        a = f'SPECIES_RECRUITED_BITS+{species >> 3}'
        self.e.poke(a, bytes([self.e.peek(a, 'B') | 1 << (species & 7)]))

    def shot(self, name):
        self.e.run('shot', str(self.out / f'{name}.png'), check=False)

    def state(self):
        e = self.e; ram = e.ram()
        return dict(row=self.pstat(self.save['challengerVar']),
                    bag=self.bag(ram),
                    won=self.flag(self.save['wonFlag']), tried=self.flag(self.save['triedFlag']),
                    money=e.peek('MONEY', 'I', ram), fromHp=e.peek(f'MOD_BATTLE+{2 * FROM_HP}', 'h', ram),
                    items=self.items(ram), screen=e.peek('CURRENT_SCREEN', 'h', ram))

    def bag(self, ram=None):
        """The bag as one int, bit i = row i + 1: the saved wide registers from bagWreg (ScriptState.wregs, +668)."""
        regs = self.e.peek(f"SCRIPT_STATE+{WREGS + 2 * self.save['bagWreg']}", f'{BAG_WREGS}H', ram or self.e.ram())
        return sum(w << 16 * i for i, w in enumerate(regs))

    def set_bag(self, bits):
        self.e.poke(f"SCRIPT_STATE+{WREGS + 2 * self.save['bagWreg']}",
                    struct.pack(f'<{BAG_WREGS}H', *(bits >> 16 * i & 0xffff for i in range(BAG_WREGS))))

    def items(self, ram):
        types = self.e.peek('INVENTORY', '30h', ram); amounts = self.e.peek('INVENTORY+60', '30B', ram)
        return {t: a for t, a in zip(types, amounts) if t >= 0 and a}

    def npc_slot(self, species, ram=None):
        """(slot, entity address) of a present NPC of `species`. The NPC_ENTITIES records (0x68 bytes, type first) keep
        the last screen's types; presence is ENTITY_TABLE[2 + slot] pointing at the record (tools/dev/playtest/
        devimon_departure.py): leave() clears it."""
        ram = ram or self.e.ram(); base = self.e.A('NPC_ENTITIES')
        for slot in range(8):
            rec = base + slot * 0x68
            if struct.unpack_from('<i', ram, rec - 0x80000000)[0] != species: continue
            if self.e.peek(f'ENTITY_TABLE+{4 * (2 + slot)}', 'I', ram) == rec: return slot, rec
        return None, None

    def midnight(self, label):
        """23:59 with the clock running, until the day changes."""
        e = self.e
        e.gs('set', 'hour=23', 'minute=59', 'gametime_running=1')
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            e.wait(3)
            if int(e.gs('show', 'hour').split()[-1]) == 0: break
        else:
            raise AssertionError(f'{label}: the clock did not reach midnight')
        e.wait(2); e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0')
        st = self.state(); self.log[label] = st; print(label, st, flush=True)
        return st

    def home_screen(self, row):
        if not row['home']: return None
        src = (MOD / row['home']).read_text()
        m = re.search(r'new_screen\((\d+)', src)
        if m: return int(m.group(1))
        base = re.search(r'from dw\.base\.(\w+) import', src).group(1)     # a screen of the game: its stub says which
        return int(re.search(r'screen (\d+)', (ROOT / f'typings/dw/base/{base}.pyi').read_text()).group(1))

    def home_species(self, row):
        """The type the resident has at home: its own, or for an NPC of the game's screen the stub's (Gabumon139...)."""
        src = (MOD / row['home']).read_text()
        m = re.search(r'from dw\.base\.(\w+) import ([\w, ]+)', src)
        if not m: return row['species']
        stub = (ROOT / f'typings/dw/base/{m.group(1)}.pyi').read_text()
        for name in (n.strip() for n in m.group(2).split(',')):
            k = re.search(rf'^{name}: NPC +# slot \d+, (\w+)', stub, re.M)
            if k and re.match(r'[A-Za-z]+', k.group(1)).group(0) == row['name']:
                return int(re.search(rf'^    {k.group(1)} = (\d+)', (ROOT / 'typings/dw/__init__.pyi').read_text(), re.M).group(1))
        raise AssertionError(f"{row['name']}: no NPC of it imported in {row['home']}")

    def go(self, screen, label):
        """Warp to `screen` with control. An arrival can start a wild battle (Ancient Speedy Region): then back to the
        fixture (self.fixture, with the challenger var as it was) and in by the next entry."""
        e = self.e
        for entry in range(3):
            if e.warp(screen, entry):
                e.wait(3)
                if e.in_control(8) and e.peek('GAME_STATE', 'H') != 1: self.shot(label); return
            assert self.fixture, f'{label}: no control on {screen}'
            row = self.fixture_row
            e.run('load', str(self.fixture)); e.wait(3); e.in_control()
            e.gs('pstat', str(self.save['challengerVar']), str(row)); print(f'{label}: battle on arrival, entry {entry + 1}')
        raise AssertionError(f'{label}: no control on {screen}')

    def expected(self, species, partner):
        from tools import city_residents
        w = city_residents.challenge_sheet(next(r for r in self.rows if r['species'] == species), species_sheets())
        sp, pp = self.rule['sheetPercent'], self.rule['partnerPercent']
        names = ('hp', 'mp', 'off', 'def', 'speed', 'brain')
        return {n: min(9999, max(w[n] * (100 + sp) // 100, partner[n] * (100 + pp) // 100)) for n in names}

    def talk_into_battle(self, slot, label):
        e = self.e
        from tools.dev.playtest.birdramon_recruitment import call_section
        e.gs('approach', str(slot))          # beside it, facing it; the talk itself is entered as the game does (5 + slot)
        e.poke('TALKED_TO_ENTITY', bytes([5 + slot])); call_section(e, e.peek('CURRENT_SCRIPT_ID', 'H'), 5 + slot)
        e.wait(1.5); self.shot(label + '-talk')
        for _ in range(60):
            if e.peek('GAME_STATE', 'H') == 1: return True
            e.press('CONFIRM', 6); e.wait(1.5)
        self.shot(label + '-no-battle')
        return False

    def battle(self, pd, partner, species, outcome, label):
        """In the battle: check the challenger's stats, the bag and fromHp, then force `outcome` and wait for the end."""
        e = self.e
        e.wait(4); ram = e.ram()
        off, de, spd, brn = struct.unpack_from('<4h', ram, pd - 0x80000000 + 0x38)
        hp, mp = struct.unpack_from('<2h', ram, pd - 0x80000000 + 0x48)
        got = dict(hp=hp, mp=mp, off=off, def_=de, speed=spd, brain=brn)
        got['def'] = got.pop('def_')
        want = self.expected(species, partner)
        # noItems: the battle bag is filtered when its menu first opens (addInventoryUI -> modBagFilterForBattle), so
        # the test reads the rule's switch for this battle rather than opening the menu
        info = dict(stats=got, expected=want, fromHp=e.peek(f'MOD_BATTLE+{2 * FROM_HP}', 'h', ram),
                    noBag=e.peek('MOD_CHALLENGE_NO_BAG', 'B', ram))
        self.shot(label + '-battle')
        # knock out the loser (0 HP: at 1 the next forced write would undo every hit) and let the battle end
        hp = (lambda: e.run('poke', hex(pd + 0x4c), '0000')) if outcome == 'won' else \
             (lambda: e.poke('PARTNER_ENTITY+0x4c', b'\0\0'))
        hp()
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline and e.peek('GAME_STATE', 'H') == 1:
            e.wait(2)
            if e.peek('GAME_STATE', 'H') == 1: hp()
        self.shot(label + '-end')
        info['ended'] = e.peek('GAME_STATE', 'H') != 1
        return info


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--partner', type=int, default=3, help='partner type on the test card (3 = Agumon, a Rookie)')
    ap.add_argument('--out', default='build/resident-challenges'); ap.add_argument('--port', type=int, default=44211)
    a = ap.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    doc = json.loads((ROOT / 'content/tables/resident-challenges.json').read_text())
    e = Emu(a.disc, a.exe, a.port, str(out / 'emu'))
    for name, (addr, _, _) in elf_symbols(a.exe + '.elf').items(): e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    r = Run(e, doc, out); result = r.log
    try:
        from tools.dev.playtest.birdramon_recruitment import field_card
        field_card(a.card, str(out / 'test.mcd'), partner_type=a.partner)
        e.start(str(out / 'test.mcd')); assert e.continue_game() == 0, 'Continue failed'
        e.wait(5); assert e.in_control()
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('trigger', '50', '1')
        for row in doc['residents']: r.recruit(row['species'])
        result['fromHpNormal'] = e.peek(f'MOD_BATTLE+{2 * FROM_HP}', 'h')
        assert result['fromHpNormal'] > 0, 'NORMAL has no late step in this build'

        day1 = r.midnight('day1')
        # every row: the day it is the challenger, absent from its home and waiting at its site
        result['rows'] = {}
        r.fixture = out / 'day1.state'; e.run('save', str(r.fixture))
        for i, each in enumerate(doc['residents'], 1):
            seen = {}
            home, at_home = r.home_screen(each), r.home_species(each)
            r.fixture_row = i % len(doc['residents']) + 1
            e.gs('pstat', str(doc['save']['challengerVar']), str(r.fixture_row))                     # another's day
            r.go(home, f'row{i}-home-other-day'); seen['homeOtherDay'] = r.npc_slot(at_home)[0] is not None
            r.go(each['site']['screen'], f'row{i}-site-other-day'); seen['siteOtherDay'] = r.npc_slot(each['species'])[0] is None
            r.fixture_row = i
            e.gs('pstat', str(doc['save']['challengerVar']), str(i))                                  # its day
            r.go(home, f'row{i}-home'); seen['home'] = r.npc_slot(at_home)[0] is None
            r.go(each['site']['screen'], f'row{i}-site'); seen['site'] = r.npc_slot(each['species'])[0] is not None
            result['rows'][each['name']] = seen; print(each['name'], seen, flush=True)
        e.run('load', str(r.fixture)); e.wait(3); e.in_control(); r.fixture_row = day1['row']
        bad = {n: v for n, v in result['rows'].items() if not all(v.values())}
        assert not bad, f'not absent from home / not at the site: {bad}'
        assert 1 <= day1['row'] <= len(doc['residents']), day1
        row = doc['residents'][day1['row'] - 1]; result['challenger1'] = row['name']
        assert day1['bag'] == 1 << (day1['row'] - 1) and not day1['won'] and not day1['tried'], day1

        home = r.home_screen(row)
        if home is not None:
            r.go(home, 'home'); slot, _ = r.npc_slot(r.home_species(row))
            result['atHome'] = slot is not None
            assert slot is None, f"{row['name']} still at home on {home}"
        r.go(row['site']['screen'], 'site')
        slot, pd = r.npc_slot(row['species']); assert slot is not None, f"{row['name']} not at its site"
        partner = dict(zip(('off', 'def', 'speed', 'brain'), e.peek('PARTNER_ENTITY+0x38', '4h')))
        partner.update(zip(('hp', 'mp'), e.peek('PARTNER_ENTITY+0x48', '2h')))
        result['partner'] = partner
        before = r.state(); e.run('save', str(out / 'site.state'))

        # a lost fight: everything put back, it is still there
        assert r.talk_into_battle(slot, 'lost'), 'the talk did not start a battle'
        b = r.battle(pd, partner, row['species'], 'lost', 'lost'); result['lostBattle'] = b
        assert b['stats'] == b['expected'], b
        assert b['fromHp'] == 0 and b['noBag'] == 1 and b['ended'], b
        e.wait(5); e.in_control(60); after = r.state(); result['afterLoss'] = after
        # the usual defeat (the bag may lose items); what the challenge took is back: the late step and the bag switch
        assert after['fromHp'] == result['fromHpNormal'] and e.peek('MOD_CHALLENGE_NO_BAG', 'B') == 0, after
        assert after['tried'] == 1 and after['won'] == 0 and after['row'] == day1['row'], after
        r.go(row['site']['screen'], 'site-after-loss')
        result['stillThereAfterLoss'] = r.npc_slot(row['species'])[0] is not None
        assert result['stillThereAfterLoss']

        # a won fight from the same spot: reward, the flag, it runs off
        e.run('load', str(out / 'site.state')); e.wait(3)
        assert r.talk_into_battle(slot, 'won'), 'the talk did not start a battle'
        b = r.battle(pd, partner, row['species'], 'won', 'won'); result['wonBattle'] = b
        assert b['stats'] == b['expected'] and b['fromHp'] == 0 and b['noBag'] == 1 and b['ended'], b
        for _ in range(40):
            if e.in_control(1) and r.flag(doc['save']['wonFlag']): break
            e.press('CONFIRM', 6); e.wait(1)
        e.wait(6); r.shot('after-win'); after = r.state(); result['afterWin'] = after
        assert after['won'] == 1 and after['fromHp'] == result['fromHpNormal'], after
        assert after['items'].get(row['item'], 0) == before['items'].get(row['item'], 0) + 1, (before, after)
        assert after['money'] >= before['money'] + row['bits'], (before['money'], after['money'])
        result['goneAfterWin'] = r.npc_slot(row['species'])[0] is None

        day2 = r.midnight('day2')
        assert day2['row'] and day2['row'] != day1['row'], day2
        assert day2['bag'] == day1['bag'] | 1 << (day2['row'] - 1) and not day2['won'] and not day2['tried'], day2
        result['challenger2'] = doc['residents'][day2['row'] - 1]['name']
        result['pass'] = True
    except BaseException as error:
        result['error'] = str(error)[:2000]; r.shot('failure'); raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
        e.stop()
    print(json.dumps(result, default=str))


if __name__ == '__main__':
    main()
