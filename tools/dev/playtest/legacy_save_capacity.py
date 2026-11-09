#!/usr/bin/env python3
"""Reproduce the old full-card writer, or check an incomplete historical save.

--write fills a private copy of --legacy-card (a one-block original save), marks
history/recruits in RAM and saves through Cheats' native card menu. Old writers
lose extension-only state; the current writer must preserve it. --expect-loss
is a negative control for the old releases, never an assertion of compatibility.
Without --write, --card selects an already-written incomplete save to inspect.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import memory_card as mcd
from tools.dev.saves import releases
from tools.dev.playtest.chart_card_roundtrip import save
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.save_policy import filled, mark
from tools.dev.playtest.save_upgrade import state, placements


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39577)
    p.add_argument('--write', action='store_true')
    p.add_argument('--legacy-card', type=Path)
    p.add_argument('--card', type=Path)
    expectation = p.add_mutually_exclusive_group()
    expectation.add_argument('--expect-loss', action='store_true')
    expectation.add_argument('--expect-refused', action='store_true')
    a = p.parse_args()
    if a.write and not a.legacy_card:
        p.error('--write requires --legacy-card')
    if a.write and a.expect_refused:
        p.error('--expect-refused is a reader-only check')
    if not a.write and not (a.card and (a.expect_loss or a.expect_refused)):
        p.error('reader-only checks require --card and an expected loss or refusal')
    source = a.legacy_card if a.write else a.card
    original = source.read_bytes()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(source_sha1=hashlib.sha1(original).hexdigest(),
                  disc_sha1=releases.disc_sha1(a.disc))
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    try:
        card = source.resolve()
        if a.write:
            assert len(mcd.Card(str(source)).find(releases.SAVE)['blocks']) == 1
            card = out / 'full.mcd'
            filled(source, card, 15)
        e.start(str(card))
        result['continue_error'] = e.continue_game()
        if a.expect_refused:
            assert result['continue_error'] == 2, 'incomplete extended save was not refused'
            e.run('shot', str(out / 'data-error.png'))
            result['ok'] = True
            print('PASS: incomplete extended save refused', flush=True)
            return
        assert result['continue_error'] == 0
        e.wait(3)
        assert e.in_control()
        if a.write:
            mark(e)
            for symbol in ('SPECIES_RAISED_BITS', 'SPECIES_RECRUITED_BITS'):
                bits = bytearray(e.raw(symbol, 128, e.ram()))
                bits[184 // 8] |= 1 << (184 % 8)
                e.poke(symbol, bits)
            # Keep care interruptions out of the controlled save operation.
            e.gs('set', 'partner.para.foodLevel=100', 'partner.para.energyLevel=100',
                 'partner.para.poopLevel=0', 'partner.para.condition=0',
                 'partner.para.sleepyHour=23', 'partner.para.wakeupHour=1', 'hour=10')
            result['before'] = state(e)
            assert e.warp(218)
            e.wait(2)
            result['save_error'] = save(e)
            assert result['save_error'] == 0
            e.wait(2)
            e.stop()
            written = out / 'written.mcd'
            shutil.copyfile(e.card_out(), written)
            card_file = mcd.Card(str(written))
            result['decoded'] = mcd.decode_save(card_file.read(releases.SAVE))
            result['directory'] = card_file.find(releases.SAVE)
            e.start(str(written))
            assert e.continue_game() == 0
            e.wait(3)
            assert e.in_control()
        result['loaded'] = state(e)
        if a.expect_loss:
            for key in ('raised', 'recruited'):
                assert not any(bytes.fromhex(result['loaded'][key]))
            if a.write:
                for key in ('native_raised', 'native_recruited'):
                    assert result['before'][key] == result['loaded'][key]
        else:
            assert result['loaded'] == result['before']
        result['placements'] = placements(e, out, 'loaded', not a.expect_loss)
        result['ok'] = True
        print('PASS: expected historical loss' if a.expect_loss else 'PASS: full-card progress retained', flush=True)
    finally:
        e.stop()
        assert source.read_bytes() == original, 'source card changed'
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
