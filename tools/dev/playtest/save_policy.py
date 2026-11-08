#!/usr/bin/env python3
"""Prove card-full refusal and legacy-save growth through the 2 MB game.

The input is an untouched one-block game card. Disposable copies fill the card
with dummy files; no source card is edited.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import memory_card as mcd
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.chart_card_roundtrip import save, history, IMPORTED, RECRUITED, NATIVE
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def mark(e):
    for symbol, species in [('SPECIES_RAISED_BITS', IMPORTED), ('SPECIES_RECRUITED_BITS', RECRUITED)]:
        bits = bytearray(128)
        for n in species:
            bits[n // 8] |= 1 << (n % 8)
        e.poke(symbol, bits)
    for n in NATIVE:
        e.gs('trigger', str(512+n), '1')


def filled(source, target, used):
    shutil.copyfile(source, target)
    card = mcd.Card(target)
    while sum(len(f['blocks']) for f in card.files()) < used:
        card.add_dummy('CAPACITY' + str(len(card.files())))
    target.write_bytes(card.d)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--legacy-card', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39715)
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    assert len(mcd.Card(a.legacy_card).find('BASLUS-01032DMR0')['blocks']) == 1
    e = ProofEmu(a.disc, a.exe, a.port, str(out/'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(a.exe+'.elf').items():
        e.table.setdefault(name, address)
    result = {}
    try:
        full = out/'full.mcr'; filled(a.legacy_card, full, 15)
        old = full.read_bytes()
        e.start(str(full)); assert e.continue_game() == 0
        mark(e); result['full_before'] = history(e)
        assert save(e) == 7, 'full legacy card must report no room'
        e.wait(1); e.run('shot', str(out/'card-full.png')); e.stop()
        assert Path(e.card_out()).read_bytes() == old, 'failed save changed card bytes'
        result['full_card_unchanged'] = True
        spare = out/'spare.mcr'; filled(a.legacy_card, spare, 14)
        e.start(str(spare)); assert e.continue_game() == 0
        mark(e); assert save(e) == 0
        e.wait(2); e.stop()
        written = out/'upgraded.mcr'; shutil.copyfile(e.card_out(), written)
        f = mcd.Card(written).find('BASLUS-01032DMR0')
        assert f['size'] == 0x4000 and len(f['blocks']) == 2, f
        result['upgraded_blocks'] = f['blocks']
        e.start(str(written)); assert e.continue_game() == 0
        result['upgraded_loaded'] = history(e)
        for key in ('native', 'imported', 'recruited'):
            assert all(result['upgraded_loaded'][key].values()), key
        e.stop()
        lost = out/'lost-extension.mcr'; shutil.copyfile(written, lost)
        damaged = mcd.Card(lost)
        damaged.write('BASLUS-01032DMR0', 0x2000, bytes(0x2000))
        e.start(str(lost)); error = e.continue_game()
        assert error == 2, ('missing extension loaded without progress', error)
        result['lost_extension_error'] = error
        e.run('shot', str(out/'lost-extension-data-error.png')); e.stop()
        # A new slot on a card with just one free block must not create a
        # misleading successful one-block Horizon save.
        e.start(str(spare)); e.to_title()
        e.run('pause')
        e.poke('CURRENT_MENU', struct.pack('<i', 0x10))
        e.poke('TARGET_MENU', struct.pack('<i', 0x10))
        e.poke('MAIN_MENU_TICKS', struct.pack('<i', 3))
        e.poke('MEMORY_CARD_ID', struct.pack('<i', 0))
        e.poke('MEMORY_CARD_SLOT', struct.pack('<i', 1))
        e.run('resume')
        e.wait(3)
        assert e.peek('MEMORY_CARD_ERROR', 'i') == 7
        e.run('shot', str(out/'new-slot-one-free-block.png')); e.stop()
        assert not any(f['name'] == 'BASLUS-01032DMR1' for f in mcd.Card(e.card_out()).files())
        result['new_slot_refused'] = True
        result['ok'] = True
        print('PASS: full-card refusal, one-block upgrade, fresh Continue and new-slot capacity', flush=True)
    finally:
        e.stop(); (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
