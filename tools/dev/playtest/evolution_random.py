#!/usr/bin/env python3
"""Reload one memory-card save eight times and complete random evolutions on 2 MB.

The private Salamon save has the investigation's stats, four care mistakes and
71 evolution hours. Each real Continue reloads that same file; only the final
hour is advanced by a fixture write after a varied real-time delay. The game
field tick selects and animates evolution. Title checkpoints speed up repeated
Continues; field checkpoints are used only for the separate RNG replay check.
No RNG, timer, path, requirement or selected-target values are poked.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import memory_card as mcd
from tools.dev.game_state import PARTNER_PARA_FIELDS
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.evolution_grace import finish_evolution
from tools.dev.playtest.evo_popup_time import open_chart


def card_fixture(path):
    field_card(str(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd'), str(path), partner_type=221)
    card = mcd.Card(path)
    name = 'BASLUS-01032DMR0'
    data = bytearray(card.read(name))
    size = 0x2000 if len(data) >= 0x6000 else 0x1000
    for i, base in enumerate((0x200, 0x1100)):
        payload = bytearray(data[base:base + 0xf00])
        struct.pack_into('<4h', payload, 0x270, 100, 200, 100, 100)
        struct.pack_into('<4h', payload, 0x280, 2000, 1000, 2000, 1000)
        values = dict(evoTimer=71, careMistakes=4, weight=10, discipline=50, happiness=50,
                      foodLevel=1000, energyLevel=100, remainingLifetime=1000)
        at = 0x1e0
        for field, fmt in PARTNER_PARA_FIELDS:
            if field in values:
                struct.pack_into('<' + fmt, payload, at, values[field])
            at += struct.calcsize('<' + fmt)
        checksum = mcd.v1_checksum(payload) ^ 0xffffffff
        struct.pack_into('<I', payload, 0x4fc, checksum)
        data[base:base + 0xf00] = payload
        offset = 0x2000 + i * size
        head = bytearray(data[offset:offset + size])
        struct.pack_into('<I', head, 8, checksum)
        records = [(tag, bytes(len(value)) if tag == 7 else value)
                   for tag, value in mcd.parse_records(head)]
        data[offset:offset + size] = mcd.build_extension(head, records, size)
    card.write(name, 0, data)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def continue_from_title(e):
    selected = False
    for _ in range(120):
        ram = e.ram()
        menu = e.peek('CURRENT_MENU', 'i', ram)
        if selected and menu == -1:
            assert e.in_control(), 'Continue did not return control'
            return
        if menu == 0 and e.peek('MAIN_MENU_TICKS', 'i', ram) > 3:
            pos = e.peek('MENU_HIGHLIGHTS', 'b', ram)
            if pos != 1:
                e.press('DOWN' if pos == 0 else 'UP', 8)
            else:
                e.press('CONFIRM', 8)
                selected = True
        elif selected and menu in (0x14, 0x17, 0x18):
            assert e.peek('MEMORY_CARD_ERROR', 'i', ram) == 0, 'card refused'
            e.press('CONFIRM', 8)
        e.wait(.25)
    raise AssertionError('Continue never loaded the card')


def timer_read_site(e, function):
    """Observe the two actual LHU results even when the compiler inlines timers."""
    from tools.xref import Elf
    from tools.langpatch import elf_symbols
    elf = Elf(e.exe + '.elf')
    start, size, _ = elf_symbols(e.exe + '.elf')[function]
    section = next(s for s in elf.sh if s['addr'] <= start < s['addr'] + s['size'])
    offset = section['off'] + start - section['addr']
    reads = {}
    for i in range(0, size, 4):
        word, = struct.unpack_from('<I', elf.d, offset + i)
        if word >> 26 == 0x25 and (word & 0xffff) in (0x1100, 0x1120):
            reads[word & 0xffff] = (start + i, (word >> 16) & 31)
    assert set(reads) == {0x1100, 0x1120}, (function, reads)
    assert reads[0x1120][0] == reads[0x1100][0] + 4, reads
    registers = ('zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 '
                 's0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra').split()
    return (reads[0x1120][0] + 8, registers[reads[0x1100][1]],
            registers[reads[0x1120][1]])


def watch(e):
    a = e.A
    refresh_hook = ''
    if e.has('evolutionPad'):
        site, _, _ = timer_read_site(e, 'chooseQualifiedEvolution')
        refresh_hook = f"hook({site},function() if RP.active then local m=PCSX.getMemPtr();local p={a('Vcount') & 0x1fffff};RP.refresh=m[p]+256*m[p+1]+65536*m[p+2]+16777216*m[p+3] end end)"
    e.run('lua', f'''
      RP={{active=false,done=false,raw=-1,refresh=-1,chosen=-1,bp={{}}}}
      local function hook(a,f)
        local b=PCSX.addBreakpoint(a,'Exec',4,'random-evolution-proof',f)
        RP.bp[#RP.bp+1]=b;return b
      end
      {refresh_hook}
      hook({a('rollNaturalEvolutionTarget')},function()
        RP.active=true
        local b;b=hook(PCSX.getRegisters().GPR.n.ra,function()
          RP.chosen=PCSX.getRegisters().GPR.n.v0
          RP.active=false;RP.done=true
          for _,bp in ipairs(RP.bp) do bp:remove() end
          PCSX.pauseEmulator()
        end)
      end)
      hook({a('randomLimit')},function()
        if not RP.active or PCSX.getRegisters().GPR.n.a0~=32768 then return end
        local b;b=hook(PCSX.getRegisters().GPR.n.ra,function()
          RP.raw=PCSX.getRegisters().GPR.n.v0;b:remove()
        end)
      end)
      hook({a('VSync')},function()
        if not RP.active or PCSX.getRegisters().GPR.n.a0~=4294967295 then return end
        local b;b=hook(PCSX.getRegisters().GPR.n.ra,function()
          RP.refresh=PCSX.getRegisters().GPR.n.v0;b:remove()
        end)
      end)
    ''')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39453)
    p.add_argument('--rolls', type=int, default=8)
    a = p.parse_args()
    assert a.rolls >= 8, 'at least eight actual card reloads required'
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    card = out / 'salamon.mcd'
    digest = card_fixture(card)
    e = emulator(a.disc, a.exe, a.port, out)
    rows, replay, champion_case = [], [], {}
    try:
        e.start(str(card))
        e.to_title()
        e.run('pause')
        title = out / 'title.state'; e.run('save', str(title))
        for trial in range(a.rolls):
            e.run('load', str(title)); e.run('resume')
            continue_from_title(e)
            e.run('pause')
            assert len(e.ram()) == 0x200000
            assert not json.loads(e.api('/api/v1/execution-flow'))['8mb']
            assert e.peek('PARTNER_ENTITY', 'i') == 221
            e.gs('set', 'gametime_running=0')
            assert e.peek('PARTNER_PARA+0x52', 'h') == 4
            assert e.peek('PARTNER_PARA+0x42', 'h') == 10
            # The fixture intentionally has just the two documented qualifiers.
            assert call(e, 'evoRequirementsMet', 221, 234, 1, 0).bit_count() >= 3
            assert call(e, 'evoRequirementsMet', 221, 222, 0, 0).bit_count() >= 3
            if trial == 0:
                field = out / 'rng-replay.state'; e.run('save', str(field))
                for _ in range(2):
                    e.run('load', str(field))
                    replay.append(call(e, 'randomLimit', 32768))
                assert replay[0] == replay[1], ('RNG state replay differs', replay)
                e.run('load', str(field))
            # All preview calls must return without touching the RNG.
            assert call(e, 'getNaturalEvolutionTarget', 221) == 234
            e.run('resume')
            delay = .19 + trial * .347
            e.wait(delay)
            e.run('pause')
            watch(e)
            e.gs('set', 'partner.para.evoTimer=72', 'gametime_running=1')
            e.run('resume')
            for _ in range(300):
                if e.run('lua', 'return RP.done').strip() == 'true':
                    break
                e.wait(.1)
            else:
                raise AssertionError('natural evolution did not roll')
            result = {key: int(e.run('lua', 'return RP.' + key).strip())
                      for key in ('chosen', 'raw', 'refresh')}
            assert result['chosen'] in (234, 222), result
            assert result['raw'] >= 0 and result['refresh'] >= 0, result
            result.update(trial=trial + 1, delay_seconds=delay, card_sha256=digest)
            e.run('resume')
            finish_evolution(e, result['chosen'])
            e.gs('set', 'gametime_running=0')
            e.wait(1)
            result['final_species'] = e.peek('PARTNER_ENTITY', 'i')
            assert result['final_species'] == result['chosen']
            e.run('shot', str(out / f'evolution-{trial+1}.png'))
            rows.append(result)
            print(json.dumps(result), flush=True)
            assert hashlib.sha256(Path(e.card_out()).read_bytes()).hexdigest() == digest
        # Also run the shared picker through the Champion -> Ultimate field gate.
        parent = e.peek('PARTNER_ENTITY', 'i')
        e.run('pause')
        e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=168',
             'partner.para.remainingLifetime=1000', 'partner.para.careMistakes=0',
             'partner.para.discipline=100', 'partner.para.happiness=100',
             *[f'partner.stats.{stat}={9000 if stat in ("hp", "mp") else 900}'
               for stat in ('hp', 'mp', 'off', 'def', 'speed', 'brain')])
        assert call(e, 'getNaturalEvolutionTarget', parent) != 0xffffffff
        watch(e)
        e.gs('set', 'gametime_running=1'); e.run('resume')
        for _ in range(300):
            if e.run('lua', 'return RP.done').strip() == 'true':
                break
            e.wait(.1)
        else:
            raise AssertionError('Champion evolution did not roll')
        target = int(e.run('lua', 'return RP.chosen').strip())
        assert target != 0xffffffff
        e.run('resume'); finish_evolution(e, target)
        e.gs('set', 'gametime_running=0'); e.wait(1)
        e.run('shot', str(out / 'champion-to-ultimate.png'))
        champion_case = dict(parent=parent, target=target,
                             final_species=e.peek('PARTNER_ENTITY', 'i'))
        assert champion_case['final_species'] == target
        print('PASS: Champion evolution', champion_case, flush=True)
        # Separate UI fixture: revealed flags let the chart be navigated directly.
        # This happens after all reload draws and never changes their input card.
        e.run('load', str(field)); e.run('resume'); e.wait(1)
        open_chart(e, parent=221, target=234)
        for number, label in ((0, 'new-font'), (1, 'original-font')):
            call(e, 'modSetFont', number); e.run('resume')
            e.poke('CHART_CARD_ID', struct.pack('<h', -1)); e.wait(1)
            assert e.peek('CHART_CARD_MINE', 'b') == 1
            hint = e.peek('CHART_CARD_FOOTER_W', 'h')
            close = e.peek('CHART_PROMPT_W', 'h')
            assert hint > 0 and 28 + hint + 6 <= 286 - close - 13, 'hint overlaps Close'
            assert ((hint + 7) & ~3) + close <= 256, 'footer text rows overlap'
            e.run('shot', str(out / ('random-rule-' + label + '.png')))
        e.run('load', str(field)); e.run('resume'); e.wait(1)
        assert e.warp(207), 'screen 207 did not load on 2 MB'
        e.run('shot', str(out / 'screen-207.png'))
        distribution = Counter(row['chosen'] for row in rows)
        assert len(distribution) > 1, ('all reloads chose the same target', distribution)
        print(f'PASS: {a.rolls} card reloads; multiple outcomes; completed evolutions:', dict(distribution), flush=True)
    finally:
        (out / 'result.json').write_text(json.dumps(dict(ram_bytes=0x200000,
            rng_replay=replay, card_sha256=digest, cases=rows, champion_case=champion_case,
            distribution=dict(Counter(row['chosen'] for row in rows))), indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
