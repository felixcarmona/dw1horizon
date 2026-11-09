#!/usr/bin/env python3
"""Cold-load a released card and check history, residents and Hawkmon placements.

The input card is never changed. Optionally resave through the game's machine
and cold-load again. Run against each release's own disc, then the newer disc;
never substitute a cross-version emulator state for a memory-card Continue.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import memory_card as mcd
from tools.dev.saves import releases
from tools.dev.playtest.qol import ProofEmu

NAME = 'BASLUS-01032DMR0'
HAWKMON = 184


def bit(data, index):
    return bool(data[index // 8] & (1 << (index % 8)))


def expected(card):
    _, payload, records = releases.read_card(str(card))
    assert 7 in records and 8 in records, 'use a complete released Horizon card'
    flags = payload[releases.P_TRIGGERS:releases.P_TRIGGERS + 100]
    return dict(raised=records[7][:128].ljust(128, b'\0').hex(),
                recruited=records[8][:128].ljust(128, b'\0').hex(),
                native_raised=[bit(flags, 512 + n) for n in range(180)],
                native_recruited=[bit(flags, 200 + n) for n in range(112)])


def state(e):
    ram = e.ram()  # also rejects expanded RAM
    flags = e.raw('SCRIPT_STATE+245', 100, ram)
    return dict(raised=e.raw('SPECIES_RAISED_BITS', 128, ram).hex(),
                recruited=e.raw('SPECIES_RECRUITED_BITS', 128, ram).hex(),
                native_raised=[bit(flags, 512 + n) for n in range(180)],
                native_recruited=[bit(flags, 200 + n) for n in range(112)])


def npcs(e):
    ram = e.ram()
    out = {}
    for slot in range(2, 10):
        pointer = e.peek(f'ENTITY_TABLE+{slot * 4}', 'I', ram)
        if pointer:
            out[str(slot)] = struct.unpack_from('<i', ram, pointer & 0x1fffff)[0]
    return out


def retained(want, got):
    """Travel can recruit a resident through a pending story event."""
    for key, old in want.items():
        new = got[key]
        if isinstance(old, str):
            old, new = bytes.fromhex(old), bytes.fromhex(new)
            assert len(old) == len(new), f'{key} changed size'
            assert all(a & b == a for a, b in zip(old, new)), f'{key} lost bits'
        else:
            assert len(old) == len(new), f'{key} changed size'
            assert all(not a or b for a, b in zip(old, new)), f'{key} lost flags'


def check(e, want, allow_growth=False):
    got = state(e)
    if allow_growth:
        retained(want, got)
    else:
        for key in want:
            assert got[key] == want[key], f'loaded {key} differs from the card'
    return got


def placements(e, out, label, recruited):
    story = bool(e.peek('MOD_OPT_STORY', 'i'))
    result = {}
    for screen, present in ((36, story and not recruited), (207, story and recruited)):
        assert e.warp(screen), f'cannot reach screen {screen}'
        actors = npcs(e)
        assert (HAWKMON in actors.values()) == present, (screen, present, actors)
        result[str(screen)] = actors
        e.run('shot', str(out / f'{label}-{screen}.png'))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--card', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39573)
    p.add_argument('--roundtrip', action='store_true')
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    before = a.card.read_bytes()
    want = expected(a.card)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    result = dict(card_sha1=hashlib.sha1(before).hexdigest(),
                  disc_sha1=releases.disc_sha1(a.disc), expected=want)
    try:
        e.start(str(a.card.resolve()))
        result['continue_error'] = e.continue_game()
        assert result['continue_error'] == 0, result['continue_error']
        # Continue's menu disappears before field initialization and its fade
        # finish. A warp written during that transition can be overwritten.
        e.wait(3)
        assert e.in_control()
        result['loaded'] = check(e, want)
        result['screen'] = e.peek('CURRENT_SCREEN', 'h')
        result['partner'] = e.peek('PARTNER_ENTITY', 'i')
        result['options'] = {name: e.peek(symbol, 'i') for name, symbol in
                             (('newDigimon', 'MOD_OPT_NEW_DIGIMON'), ('extendedStory', 'MOD_OPT_STORY'))}
        result['learned'] = e.raw('PARTNER_ENTITY+0x58', 16, e.ram()).hex()
        result['equipped'] = e.raw('PARTNER_ENTITY+0x44', 4, e.ram()).hex()
        result['placements'] = placements(e, out, 'loaded', bit(bytes.fromhex(want['recruited']), HAWKMON))
        if a.roundtrip:
            assert e.warp(218)
            before_save = state(e)
            retained(want, before_save)
            e.save_at_jijimon()
            e.stop()
            saved = out / 'resaved.mcd'
            shutil.copyfile(e.card_out(), saved)
            assert expected(saved) == before_save, 'resave changed history or recruits'
            result['resaved_file'] = mcd.decode_save(mcd.Card(saved).read(NAME))
            e.start(str(saved))
            result['reload_error'] = e.continue_game()
            assert result['reload_error'] == 0, result['reload_error']
            e.wait(3)
            assert e.in_control()
            result['reloaded'] = check(e, before_save, allow_growth=True)
            result['reloaded_placements'] = placements(e, out, 'reloaded', bit(bytes.fromhex(want['recruited']), HAWKMON))
        result['ok'] = True
        print('PASS: history, native recruit flags, imported recruit bits and Hawkmon placements', flush=True)
    finally:
        e.stop()
        assert a.card.read_bytes() == before, 'source card changed'
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
