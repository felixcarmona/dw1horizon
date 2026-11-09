#!/usr/bin/env python3
"""Play all seven quiz questions through the first partner sighting on original 2 MB RAM.

Save result, optional-name question, empty partner keyboard and neutral name
confirmation screenshots. Uses fresh cards and pad input for every question and
name. Sets only the boot language cursor; English/Spanish use separate boots. Example:
  python3 tools/dev/playtest/starter_reveal.py build/full.cue \
    --exe build/full/exe/SLUS_010.32 --lang es --out build/reveal-es
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc')
    parser.add_argument('--exe', required=True)
    parser.add_argument('--lang', choices=('en', 'es'), default='en')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--port', type=int, default=39481)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(out))
    for name, (address, _, _) in elf_symbols(args.exe + '.elf').items():
        e.table.setdefault(name, address)
    trace, shots, questions = [], set(), []
    started = time.monotonic()
    def shot(name):
        e.wait(1.5)
        e.run('shot', str(out / (name + '.png')))
        shots.add(name)
    def peek(name, fmt='i', ram=None):
        return e.peek(name, fmt, ram)
    try:
        e.start(None)
        # Pin only the language cursor: START can dismiss the intro and picker in
        # one press on faster hosts. No quiz, naming or world state is injected.
        e.wait(35)
        e.poke('MOD_BOOT_LANGUAGE_CURSOR', struct.pack('<i', 1 if args.lang == 'es' else 0))
        e.press('START', 4)
        e.wait(3)
        for _ in range(100):
            ram = e.ram()
            menu, ticks = peek('CURRENT_MENU', ram=ram), peek('MAIN_MENU_TICKS', ram=ram)
            if menu == 0 and ticks > 3:
                if peek('MOD_BOOT_LANGUAGE', ram=ram):
                    e.press('CONFIRM', 4)
                    e.wait(3)
                else:
                    assert peek('MOD_LANG', ram=ram) == (1 if args.lang == 'es' else 0)
                    break
            else:
                e.press('START', 4)
                e.wait(1)
        else:
            raise RuntimeError('title/language picker timed out')
        # NEW GAME, no memory card, yes. No card format/save fixture is involved.
        for _ in range(100):
            ram = e.ram()
            menu = peek('CURRENT_MENU', ram=ram)
            if menu == -1:
                break
            if menu == 1 and peek('MENU_HIGHLIGHTS+1', 'B', ram) != 2:
                e.press('DOWN', 4)
            else:
                e.press('CONFIRM', 4)
            e.wait(0.7)
        last = None
        keyboard_done = set()
        while time.monotonic() - started < 900:
            ram = e.ram()
            state = peek('SCRIPT_STATE_2', 'H', ram)
            next_state = peek('SCRIPT_NEXT_STATE_2', 'H', ram)
            mode = peek('SCRIPT_TEXTBOX_MODE', 'B', ram)
            flags = peek('NAMING_BOX_FLAG', 'B', ram)
            screen = peek('CURRENT_SCREEN', 'h', ram)
            now = (state, next_state, mode, flags, screen)
            if now != last:
                row = dict(seconds=round(time.monotonic()-started, 2), state=state,
                           next=next_state, mode=mode, flags=flags, screen=screen)
                trace.append(row)
                print(row, flush=True)
                last = now
            # The seven selection entries share next state 0x26.
            if 'result' not in shots and state == 1 and mode == 2 and next_state == 0x26:
                # Each occurrence is separated by a numbered heading and question.
                if not trace[-1].get('answer'):
                    questions.append(0)
                    trace[-1]['answer'] = 0
            if state == 1 and next_state == 0x12 and mode == 1 and 'result' not in shots:
                shot('result')
            if state == 1 and next_state == 0x20 and mode == 1 and 'naming-question' not in shots:
                shot('naming-question')
                e.run('save', str(out / 'before-naming.state'))
            # An open selector box plus text mode zero identifies the keyboard.
            boxes = e.A('UI_BOX_DATA') - 0x80000000
            keyboard = state == 1 and mode == 0 and struct.unpack_from('<h', ram, boxes + 36 + 18)[0] == 1
            if keyboard:
                is_partner = bool(flags & 1)
                if is_partner and 'partner-keyboard' not in shots:
                    assert e.raw('NAMING_BUFFER', 20, ram)[0] == 0
                    shot('partner-keyboard')
                if is_partner not in keyboard_done:
                    if not is_partner:
                        e.press('CONFIRM', 4)  # the first letter is A
                        e.wait(0.3)
                    e.press('START', 4)  # move to OK; keep the partner's keyboard empty
                    e.wait(0.3)
                    keyboard_done.add(is_partner)
                e.press('CONFIRM', 4)
            else:
                if state == 1 and next_state == 0x1b and mode == 1 and 'name-confirmation' not in shots:
                    shot('name-confirmation')
                if 'result' in shots and screen > 0 and peek('ENTITY_TABLE+4', 'I', ram) != 0:
                    # Screen id changes before the CD read and fade finish. A
                    # near-black transition compresses to a few KB; wait for the
                    # actual scene, which the captured image must also be reviewed.
                    candidate = out / 'first-partner.png'
                    e.run('shot', str(candidate))
                    if candidate.stat().st_size > 12000:
                        shots.add('first-partner')
                        break
                    e.wait(0.5)
                    continue
                e.press('CONFIRM', 4)
            e.wait(0.35)
        else:
            raise RuntimeError('quiz/awakening timed out')
        assert len(questions) == 7, questions
        assert {'result', 'naming-question', 'partner-keyboard', 'name-confirmation', 'first-partner'} <= shots, shots
        e.run('save', str(out / 'first-partner.state'))
        result = dict(ok=True, language=args.lang, ram_bytes=len(e.ram()), answers=questions,
                      screenshots=sorted(shots), trace=trace,
                      executable_sha256=hashlib.sha256(Path(args.exe).read_bytes()).hexdigest())
        (out / 'evidence.json').write_text(json.dumps(result, indent=2) + '\n')
    finally:
        (out / 'trace.json').write_text(json.dumps(trace, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
