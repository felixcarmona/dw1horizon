#!/usr/bin/env python3
"""Capture every cemetery question and recruit Bakemon on original 2 MB RAM.

Uses a private copy of an original-format memory card. Partner and language are
fixtures; questions, Yes/Yes/No answers, departure and recruitment run normally.
Each language boots fresh so its normal save-option loading selects the scripts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import memory_card
from tools.dev.playtest.qol import ProofEmu
from tools.langpatch import elf_symbols


def fixture(source, target, species, language):
    target.write_bytes(Path(source).read_bytes())
    card = memory_card.Card(target)
    name = next(row['name'] for row in card.files() if row['name'].startswith('BASLUS-01032DMR'))
    data = bytearray(card.read(name))
    assert len(data) == 0x2000, 'use an original-format one-block save'
    decoded = memory_card.decode_save(data)
    for copy, base in enumerate((0x200, 0x1100)):
        assert decoded[f'copy{copy}']['checksum_ok'] and decoded[f'copy{copy}']['version'] == 1
        struct.pack_into('<i', data, base + 0x1b8, species)
        struct.pack_into('<I', data, base + 0x4fc, memory_card.v1_checksum(data[base:base + 0xf00]))
    # Native header options: US controls, proportional font, extended story,
    # normal difficulty and the requested language. Payload checksums are intact.
    data[0x50:0x60] = b'O\x0c\x01\x00' + bytes([0, 1, 20, 1, 1, 1, 1, language, 1, 1, 0, 1])
    card.write(name, 0, data)


def recruited(e):
    return bool(e.peek('SCRIPT_STATE+274', 'B') & 32)  # trigger 237


def box(e, previous=None):
    end = time.monotonic() + 45
    while time.monotonic() < end:
        ram = e.ram()
        if e.peek('ACTIVE_INSTRUCTION', 'B', ram) == 0x1a and (
                previous is None or e.peek('SCRIPT_POINTER', 'I', ram) != previous):
            e.wait(1)
            return
        e.wait(.2)
    raise AssertionError('next dialogue box never opened')


def selection(e):
    for _ in range(12):
        if e.peek('ACTIVE_INSTRUCTION', 'B') == 0x10:
            assert e.peek('DIALOGUE_SELECTION+8', 'H') == 2
            return
        e.press('CONFIRM', 20)
        e.wait(.6)
    raise AssertionError('yes/no selection never opened')


def talk(e):
    assert e.in_control()
    assert e.peek('NPC_ENTITIES', 'i') == 157
    assert e.peek('ENTITY_TABLE+8', 'I') == e.A('NPC_ENTITIES')
    for direction in ('DOWN', 'UP', 'RIGHT', 'LEFT') * 3:
        e.run('pause')
        e.gs('approach', '0', '70')
        e.run('resume')
        # Cemetery Bakemon has automatic contact dialogue. A confirm edge here
        # can skip question one if the contact has already started its script.
        e.press(direction, 20)
        if e.peek('IS_SCRIPT_PAUSED', 'i') == 0:
            assert e.peek('SCRIPT_SECTION', 'H') == 5
            box(e)
            return
    raise AssertionError('pad contact never started the cemetery conversation')


def capture(e, folder, label):
    e.run('pause')
    e.run('shot', str(folder / (label + '.png')))
    ram = e.ram()
    result = {name: e.peek(name, fmt, ram) for name, fmt in (
        ('PARTNER_ENTITY', 'i'), ('CURRENT_SCREEN', 'h'), ('CURRENT_SCRIPT_ID', 'H'),
        ('SCRIPT_SECTION', 'H'), ('ACTIVE_INSTRUCTION', 'B'), ('MOD_LANG', 'i'))}
    result['ram_bytes'] = len(ram)
    assert result['CURRENT_SCREEN'] == result['CURRENT_SCRIPT_ID'] == 35
    assert result['SCRIPT_SECTION'] == 5 and result['ACTIVE_INSTRUCTION'] == 0x1a
    e.run('resume')
    return result


def run(e, source, folder, species, language):
    folder.mkdir(parents=True, exist_ok=True)
    card = folder / 'fixture.mcd'
    fixture(source, card, species, language)
    e.start(str(card))
    assert e.continue_game() == 0 and e.in_control()
    assert e.peek('PARTNER_ENTITY', 'i') == species and e.peek('MOD_LANG', 'i') == language
    configuration = json.loads(e.api('/api/v1/execution-flow'))
    assert not configuration['8mb'] and len(e.ram()) == 0x200000
    e.run('pause')
    e.gs('set', 'gametime_running=0', 'partner.para.condition=0',
         'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000',
         'partner.para.timeAwakeToday=0', 'partner.para.hoursAwakeDefault=100')
    e.poke('MOD_CLOCK', struct.pack('<h', -1))
    e.run('resume')
    e.gs('trigger', '237', '0')
    assert e.warp(35) and e.in_control()
    e.wait(2)
    assert e.in_control()
    before = e.peek('SCRIPT_STATE+346', 'B')
    assert not recruited(e)
    e.run('save', str(folder / 'before-talk.state'))
    talk(e)
    result = {'configuration': configuration, 'boxes': {}}
    for index, label in enumerate(('question1', 'question2', 'question3', 'acceptance')):
        result['boxes'][label] = capture(e, folder, label)
        (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        if index == 3:
            break
        selection(e)
        if index == 2:
            for _ in range(6):
                if e.peek('DIALOGUE_SELECTION+10', 'H') == 1:
                    break
                e.press('DOWN', 20)
            assert e.peek('DIALOGUE_SELECTION+10', 'H') == 1, 'No was not selected'
        else:
            assert e.peek('DIALOGUE_SELECTION+10', 'H') == 0, 'Yes was not selected'
        previous = e.peek('SCRIPT_POINTER', 'I')
        e.press('CONFIRM', 20)
        box(e, previous)
    end = time.monotonic() + 120
    while time.monotonic() < end and not recruited(e):
        e.press('CONFIRM', 20)
        e.wait(.5)
    assert recruited(e) and e.in_control(), 'recruitment did not complete'
    after = e.peek('SCRIPT_STATE+346', 'B')
    assert after == before + 2, (before, after)
    result.update(answers=['yes', 'yes', 'no'], recruited=True,
                  prosperity_before=before, prosperity_after=after, control_returned=True)
    e.run('save', str(folder / 'recruited.state'))
    (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc')
    parser.add_argument('--exe', required=True)
    parser.add_argument('--card', required=True)
    parser.add_argument('--out', type=Path, default=Path('build/bakemon-proof'))
    parser.add_argument('--port', type=int, default=39862)
    parser.add_argument('--languages', default='en,es')
    parser.add_argument('--partners', default='3,37')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(args.disc, args.exe, args.port, str(out))
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    results = {'exe_sha256': hashlib.sha256(Path(e.exe).read_bytes()).hexdigest(), 'cases': {}}
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for language in args.languages.split(','):
            assert language in ('en', 'es')
            for species in map(int, args.partners.split(',')):
                assert species in (3, 37), 'runtime fixtures use raisable partners; twins have compiled-flow coverage'
                name = f'{language}-{species}'
                results['cases'][name] = run(e, args.card, out / name, species, ('en', 'es').index(language))
                e.stop()
                (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                print(name + ': four boxes captured; Yes/Yes/No recruited; prosperity +2; 2 MB', flush=True)
    finally:
        e.stop()


if __name__ == '__main__':
    main()
