#!/usr/bin/env python3
"""Resident challenges end to end (content/tables/resident-challenges.json, docs/mods/resident-challenges.md).

  xvfb-run -a python3 tools/dev/playtest/resident_challenges.py DISC --exe EXE --card CARD [--partner TYPE] [--rows R ...]

Original 2 MB RAM. With the game beaten (flag 50) and every challenger recruited, it lets the clock run over midnight
and requires: one challenger of each pool picked (its row in the pool's saved var, its bit in the bag), absent from its
city home and waiting at its recruit site, with none of the site's ordinary wild Digimon placed; its fight starts with
every stat max(sheet x (100 + sheetPercent), partner x (100 + partnerPercent)) / 100, no late-game step (NORMAL fromHp
0) and an empty bag, all put back after the battle; a lost fight leaves it at its site with only its pool's tried flag
set; a won fight pays the item and the bits, adds the beaten bit (128) to its pool's var and it runs off, the site's
wilds are back on the next visit, and the other pool's challenger still waits at its own site. A midnight with one new
resident unrecruited sends only the original pool's; another midnight picks two others, never the same, and adds their
bits to the bag; the bag, both vars and both flags come back from a save at Jijimon's machine. Every row is placed on
its day and on another's (a row with no home: its site only); --rows (names or row numbers) lose and win those rows'
fights too. Screenshots and result.json under --out.
"""
from pathlib import Path
import argparse
import json
import re
import shutil
import struct
import sys
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols
from tools.dws.recruit_screens import ordinary_slots

MOD = ROOT / 'story/mods/what-the-island-forgot'
FROM_HP = 175                      # MOD_BT_NORMAL_FROM_HP in include/dw/mod_battle.h
WREGS = 668                        # ScriptState.wregs (include/dw/script.h): smth, cards, triggers, pstats, stack[8]
BAG_WREGS = 5                      # the bag's saved wide registers (tools/city_residents.py: CHALLENGE_MAX / 16 rounded up)
BEATEN = 128                       # MOD_CHALLENGE_BEATEN: added to the pool's var by the win


def species_sheets():
    return {s['id']: s for p in (ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}


class Run:
    def __init__(self, e, doc, out):
        self.e, self.doc, self.out = e, doc, out
        self.save = doc['save']; self.rows = doc['residents']; self.rule = doc['rule']
        self.log = {}
        self.fixture = None; self.fixture_day = {}

    def var(self, row):
        """The saved pstat holding the challenger of row's pool (row: a row dict or its 1-based number)."""
        row = self.rows[row - 1] if isinstance(row, int) else row
        return self.save['newChallengerVar' if row['pool'] == 'new' else 'challengerVar']

    def tried(self, row):
        row = self.rows[row - 1] if isinstance(row, int) else row
        return self.save['newTriedFlag' if row['pool'] == 'new' else 'triedFlag']

    def set_day(self, day):
        """{var: value}: today's challengers, written into their saved pstats (also after a fixture reload in go())."""
        for v, n in day.items(): self.e.gs('pstat', str(v), str(n))
        self.fixture_day = dict(day)

    def present(self, ram=None):
        """The NPC slots 0-7 set up on this screen (ENTITY_TABLE[2 + slot] points at its record)."""
        ram = ram or self.e.ram(); base = self.e.A('NPC_ENTITIES')
        return {slot for slot in range(8) if self.e.peek(f'ENTITY_TABLE+{4 * (2 + slot)}', 'I', ram) == base + slot * 0x68}

    def wilds(self, screen):
        """The screen's ordinary wild slots placed now (tools/dws/recruit_screens.py ordinary_slots)."""
        return sorted(self.present() & ordinary_slots(screen))

    def pstat(self, n):
        return int(re.search(r'= (\d+)', self.e.gs('pstat', str(n))).group(1))

    def flag(self, n):
        return int(re.search(r'= (\d+)', self.e.gs('trigger', str(n))).group(1))

    def recruit(self, species, on=True):
        if species < 112: self.e.gs('trigger', str(200 + species), '1' if on else '0'); return
        a = f'SPECIES_RECRUITED_BITS+{species >> 3}'; b = self.e.peek(a, 'B')
        self.e.poke(a, bytes([b | 1 << (species & 7) if on else b & ~(1 << (species & 7))]))

    def shot(self, name):
        self.e.run('shot', str(self.out / f'{name}.png'), check=False)

    def state(self):
        e = self.e; ram = e.ram()
        return dict(row=self.pstat(self.save['challengerVar']), new=self.pstat(self.save['newChallengerVar']),
                    bag=self.bag(ram),
                    tried=self.flag(self.save['triedFlag']), newTried=self.flag(self.save['newTriedFlag']),
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
            k = re.search(rf'^{name}: NPC +# slot \d+(?: of screen \d+)?, (\w+)', stub, re.M)
            if k and re.match(r'[A-Za-z]+', k.group(1)).group(0) == row['name']:
                return int(re.search(rf'^    {k.group(1)} = (\d+)', (ROOT / 'typings/dw/__init__.pyi').read_text(), re.M).group(1))
        if re.search(rf'Species\.{row["name"]}\b', src): return row['species']      # its own NPC beside the game's
        raise AssertionError(f"{row['name']}: no NPC of it imported in {row['home']}")

    def go(self, screen, label):
        """Warp to `screen` with control. An arrival can start a wild battle (Ancient Speedy Region): then back to the
        fixture (self.fixture, with the challenger vars as they were) and in by the next entry."""
        e = self.e
        for entry in range(3):
            if e.warp(screen, entry):
                e.wait(3)
                if e.in_control(8) and e.peek('GAME_STATE', 'H') != 1: self.shot(label); return
            assert self.fixture, f'{label}: no control on {screen}'
            e.run('load', str(self.fixture)); e.wait(3); e.in_control()
            self.set_day(self.fixture_day); print(f'{label}: battle on arrival, entry {entry + 1}')
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


    def fight(self, which, other):
        """Today's challenger is row `which` and row `other` is the other pool's: `which` away from home and at its site
        with no wilds; a lost fight puts back what the challenge took and leaves it there; a won one, from the same spot,
        pays the item and the bits, adds the beaten bit, and it goes; the site's wilds come back, and `other` still waits."""
        e, out, save = self.e, self.out, self.save
        row = self.rows[which - 1]; tag = f'row{which}'; result = {}
        var, tried = self.var(which), self.tried(which)
        ovar, otried = self.var(other), self.tried(other)
        assert var != ovar, (which, other)
        home = self.home_screen(row)
        if home is not None:
            self.go(home, tag + '-home'); slot, _ = self.npc_slot(self.home_species(row))
            result['atHome'] = slot is not None
            assert slot is None, f"{row['name']} still at home on {home}"
        self.go(row['site']['screen'], tag + '-site')
        slot, pd = self.npc_slot(row['species']); assert slot is not None, f"{row['name']} not at its site"
        result['wildsWaiting'] = self.wilds(row['site']['screen'])
        assert not result['wildsWaiting'], f"{row['name']}: wild slots {result['wildsWaiting']} placed while it waits"
        partner = dict(zip(('off', 'def', 'speed', 'brain'), e.peek('PARTNER_ENTITY+0x38', '4h')))
        partner.update(zip(('hp', 'mp'), e.peek('PARTNER_ENTITY+0x48', '2h')))
        result['partner'] = partner
        before = self.state(); site = out / f'{tag}-site.state'; e.run('save', str(site))

        # a lost fight: everything put back, it is still there
        assert self.talk_into_battle(slot, tag + '-lost'), f"{row['name']}: the talk did not start a battle"
        b = self.battle(pd, partner, row['species'], 'lost', tag + '-lost'); result['lostBattle'] = b
        assert b['stats'] == b['expected'], b
        assert b['fromHp'] == 0 and b['noBag'] == 1 and b['ended'], b
        e.wait(5); e.in_control(60); after = self.state(); result['afterLoss'] = after
        # the usual defeat (the bag may lose items); what the challenge took is back: the late step and the bag switch
        assert after['fromHp'] == self.fromHpNormal and e.peek('MOD_CHALLENGE_NO_BAG', 'B') == 0, after
        assert self.flag(tried) == 1 and self.flag(otried) == 0, after
        assert self.pstat(var) == which and self.pstat(ovar) == self.fixture_day[ovar], after
        self.go(row['site']['screen'], tag + '-site-after-loss')
        result['stillThereAfterLoss'] = self.npc_slot(row['species'])[0] is not None
        assert result['stillThereAfterLoss'], f"{row['name']} gone after a lost fight"

        # a won fight from the same spot: reward, the flag, it leaves
        e.run('load', str(site)); e.wait(3)
        assert self.talk_into_battle(slot, tag + '-won'), f"{row['name']}: the talk did not start a battle"
        b = self.battle(pd, partner, row['species'], 'won', tag + '-won'); result['wonBattle'] = b
        assert b['stats'] == b['expected'] and b['fromHp'] == 0 and b['noBag'] == 1 and b['ended'], b
        for _ in range(40):
            if e.in_control(1) and self.pstat(var) & BEATEN: break
            e.press('CONFIRM', 6); e.wait(1)
        e.wait(6); self.shot(tag + '-after-win'); after = self.state(); result['afterWin'] = after
        assert self.pstat(var) == which + BEATEN and after['fromHp'] == self.fromHpNormal, after
        assert self.pstat(ovar) == other and self.flag(otried) == 0, after       # the other pool's fight is untouched
        assert after['items'].get(row['item'], 0) == before['items'].get(row['item'], 0) + 1, (before, after)
        assert after['money'] >= before['money'] + row['bits'], (before['money'], after['money'])
        result['goneAfterWin'] = self.npc_slot(row['species'])[0] is None
        assert result['goneAfterWin'], f"{row['name']} still at its site after the win"
        # the next visit: the site's wilds are back (as on another resident's day), it is not there
        self.fixture = out / f'{tag}-won.state'; e.run('save', str(self.fixture))       # a battle on arrival comes back here
        self.fixture_day = {var: which + BEATEN, ovar: other}
        self.go(row['site']['screen'], tag + '-site-after-win')
        result['wildsAfterWin'] = self.wilds(row['site']['screen'])
        assert result['wildsAfterWin'] == self.wilds_other_day.get(which, []), (result['wildsAfterWin'], self.wilds_other_day.get(which))
        assert self.npc_slot(row['species'])[0] is None, f"{row['name']} back at its site after the win"
        # the other pool's challenger still waits at its own site
        orow = self.rows[other - 1]
        self.go(orow['site']['screen'], tag + '-other-site')
        result['otherStillThere'] = self.npc_slot(orow['species'])[0] is not None
        assert result['otherStillThere'], f"{orow['name']} gone after {row['name']}'s win"
        print(row['name'], 'lost and won', flush=True)
        return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--partner', type=int, default=3, help='partner type on the test card (3 = Agumon, a Rookie)')
    ap.add_argument('--rows', nargs='*', default=[], help="also lose and win these rows' fights (name or number)")
    ap.add_argument('--out', default='build/resident-challenges'); ap.add_argument('--port', type=int, default=44211)
    a = ap.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    doc = json.loads((ROOT / 'content/tables/resident-challenges.json').read_text())
    names = [row['name'] for row in doc['residents']]
    a.rows = [int(n) if n.isdigit() else names.index(n) + 1 for n in a.rows]
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
        result['fromHpNormal'] = r.fromHpNormal = e.peek(f'MOD_BATTLE+{2 * FROM_HP}', 'h')
        assert result['fromHpNormal'] > 0, 'NORMAL has no late step in this build'

        rows = doc['residents']; pool = {i: row['pool'] for i, row in enumerate(rows, 1)}
        ORIG, NEW = doc['save']['challengerVar'], doc['save']['newChallengerVar']
        bit = lambda n: 1 << (n - 1)
        day1 = r.midnight('day1')
        # both pools out: one of each, its bit in the bag
        assert pool.get(day1['row']) == 'original' and pool.get(day1['new']) == 'new', day1
        assert day1['bag'] == bit(day1['row']) | bit(day1['new']) and not day1['tried'] and not day1['newTried'], day1
        result['challenger1'] = rows[day1['row'] - 1]['name']; result['newChallenger1'] = rows[day1['new'] - 1]['name']
        today = {ORIG: day1['row'], NEW: day1['new']}

        # every row: the day it is the challenger, absent from its home and waiting at its site with no wilds; on
        # another's day at home, not at the site, the site's wilds as the game places them
        result['rows'] = {}; r.wilds_other_day = {}
        r.fixture = out / 'day1.state'; e.run('save', str(r.fixture))
        for i, each in enumerate(rows, 1):
            seen = {}; v = r.var(i)
            home = r.home_screen(each); at_home = home is not None and r.home_species(each)
            mates = [n for n in pool if pool[n] == pool[i]]; another = mates[(mates.index(i) + 1) % len(mates)]
            r.set_day({ORIG: 0, NEW: 0, v: another})                                                   # another's day
            if home is not None:
                r.go(home, f'row{i}-home-other-day'); seen['homeOtherDay'] = r.npc_slot(at_home)[0] is not None
            r.go(each['site']['screen'], f'row{i}-site-other-day'); seen['siteOtherDay'] = r.npc_slot(each['species'])[0] is None
            r.wilds_other_day[i] = r.wilds(each['site']['screen'])
            r.set_day({ORIG: 0, NEW: 0, v: i})                                                         # its day
            if home is not None:
                r.go(home, f'row{i}-home'); seen['home'] = r.npc_slot(at_home)[0] is None
            r.go(each['site']['screen'], f'row{i}-site'); seen['site'] = r.npc_slot(each['species'])[0] is not None
            seen['noWilds'] = not r.wilds(each['site']['screen'])
            result['rows'][each['name']] = dict(seen, wildsOtherDay=r.wilds_other_day[i]); print(each['name'], seen, flush=True)
        e.run('load', str(r.fixture)); e.wait(3); e.in_control(); r.set_day(today)
        # a game's own resident its screen's setup keeps away at this hour and state (Elecmon, Ogremon in the lower City)
        # is not at home on another's day either: its home check proves nothing, listed, not failed
        result['homeNotShown'] = [n for n, v in result['rows'].items() if v.get('homeOtherDay') is False]
        bad = {n: v for n, v in result['rows'].items() if not all(x for k, x in v.items() if k not in ('wildsOtherDay', 'homeOtherDay'))}
        assert not bad, f'not absent from home / not at the site / wilds while waiting: {bad}'
        assert len(result['homeNotShown']) < len([v for v in result['rows'].values() if 'home' in v]) // 2, result['homeNotShown']
        result['sitesWithWilds'] = sum(bool(w) for w in r.wilds_other_day.values())
        assert result['sitesWithWilds'], 'no site has wild Digimon on another day: the wild check checks nothing'

        # fights: each pool's challenger of day 1, then --rows; the other pool's challenger waits meanwhile
        result['fights'] = {}
        for which in [day1['row'], day1['new']] + [n for n in a.rows if n not in (day1['row'], day1['new'])]:
            other = day1['new'] if pool[which] == 'original' else day1['row']
            e.run('load', str(r.fixture)); e.wait(3); e.in_control()
            r.fixture = out / 'day1.state'
            r.set_day({r.var(which): which, r.var(other): other}); r.set_bag(day1['bag'] | bit(which))
            result['fights'][rows[which - 1]['name']] = r.fight(which, other)
        r.fixture = out / 'day1.state'

        # the new pool closed: one new resident not recruited, only the original pool sends one
        e.run('load', str(r.fixture)); e.wait(3); e.in_control(); r.set_day(today); r.set_bag(day1['bag'])
        missing = rows[next(n for n in pool if pool[n] == 'new') - 1]; r.recruit(missing['species'], False)
        closed = r.midnight('closed'); result['closedWithout'] = missing['name']
        assert closed['new'] == 0 and not closed['newTried'], closed
        assert pool.get(closed['row']) == 'original' and closed['row'] != day1['row'], closed
        assert closed['bag'] == day1['bag'] | bit(closed['row']), closed

        # both pools again, two others, never the same
        e.run('load', str(r.fixture)); e.wait(3); e.in_control(); r.set_day(today); r.set_bag(day1['bag'])
        day2 = r.midnight('day2')
        assert pool.get(day2['row']) == 'original' and day2['row'] != day1['row'], day2
        assert pool.get(day2['new']) == 'new' and day2['new'] != day1['new'], day2
        assert day2['bag'] == day1['bag'] | bit(day2['row']) | bit(day2['new']), day2
        assert not day2['tried'] and not day2['newTried'], day2
        result['challenger2'] = rows[day2['row'] - 1]['name']; result['newChallenger2'] = rows[day2['new'] - 1]['name']

        # the bag and today's challenger through a save at Jijimon's machine and a fresh Continue
        r.fixture = None
        assert e.warp(218, 2) or e.warp(218), "no control in Jijimon's house"
        e.in_control(); e.gs('set', 'gametime_running=0'); kept = r.state()
        e.save_at_jijimon(); e.stop()
        saved = out / 'saved.mcd'; shutil.copyfile(e.card_out(), saved)
        e.start(str(saved)); assert e.continue_game() == 0, 'Continue of the saved card failed'
        e.wait(3); e.in_control(); back = r.state(); result['reloaded'] = back
        keys = ('row', 'new', 'bag', 'tried', 'newTried')
        assert [back[k] for k in keys] == [kept[k] for k in keys], (kept, back)
        result['pass'] = True
    except BaseException as error:
        result['error'] = str(error)[:2000]; r.shot('failure'); raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
        e.stop()
    print(json.dumps(result, default=str))


if __name__ == '__main__':
    main()
