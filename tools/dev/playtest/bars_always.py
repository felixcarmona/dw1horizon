#!/usr/bin/env python3
"""Capture permanent care panels, title settings and legacy OFF migration on 2 MB.

Use --baseline with the unchanged main disc for HUD/status comparison frames.
The title matrix uses pad input for language/font settings and cursor bounds and value wrap.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.field_hud import shot_after_swaps
from tools.dev import memory_card as mcd

LANGS = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')
FONTS = (('NEW', 0), ('CLASSIC', 2), ('ORIGINAL', 1))
CURSOR = 'MENU_HIGHLIGHTS+352'  # 22 * sizeof(MenuHighlight), 16 bytes.


def capture(e, path):
    shot_after_swaps(e, path)
    e.run('resume')


def await_value(e, name, fmt, expected):
    for _ in range(120):
        if e.peek(name, fmt) == expected:
            return
        e.wait(.2)
    raise AssertionError((name, e.peek(name, fmt), expected))


def settle_title(e):
    # Language/font loads can produce refreshes while menu logic is blocked.
    # Wait for completed menu ticks before reading geometry or sending input.
    start = e.peek('MAIN_MENU_TICKS', 'i')
    for _ in range(200):
        if e.peek('MAIN_MENU_TICKS', 'i') >= start + 3:
            return
        e.wait(.1)
    raise AssertionError('title menu ticks did not resume')


def cursor_press(e, button, expected):
    before = e.peek(CURSOR, 'b')
    for _ in range(5):
        e.press(button, 12)
        settle_title(e)
        got = e.peek(CURSOR, 'b')
        if got == expected:
            return
        assert got == before, (button, before, got, expected)
    raise AssertionError((button, before, expected))


def select(e, row):
    e.poke(CURSOR, bytes([row]))


def title_matrix(e, out, baseline):
    e.to_title()
    assert e.peek('MOD_COLD_CACHE_TYPE', 'i') == -1, 'game detected expanded RAM'
    e.run('save', str(out / 'title.state'))
    # Select the title's OPTIONS row with the real menu input.
    for _ in range(8):
        if e.peek('MENU_HIGHLIGHTS', 'b') == 4:
            break
        e.press('DOWN', 8)
    assert e.peek('MENU_HIGHLIGHTS', 'b') == 4
    e.press('CONFIRM', 12)
    await_value(e, 'CURRENT_MENU', 'i', 4)
    e.wait(.5)
    rows = 14 if baseline else 13
    assert e.peek('OPTIONS_CURSOR_COUNT', 'b') == rows
    font_row, lang_row = (9, 10) if baseline else (8, 9)
    matrix = []
    for lang in ((0, 4) if baseline else range(8)):
        select(e, lang_row)
        while e.peek('MOD_LANG', 'i') < lang:
            e.press('RIGHT', 12)
            settle_title(e)
        assert e.peek('MOD_LANG', 'i') == lang
        for name, font in FONTS:
            select(e, font_row)
            for _ in range(3):
                if e.peek('MOD_FONT', 'b') == font:
                    break
                e.press('CONFIRM', 12)
                settle_title(e)
            assert e.peek('MOD_FONT', 'b') == font
            select(e, 0)
            cursor_press(e, 'UP', 0)
            select(e, rows - 1)
            cursor_press(e, 'DOWN', rows - 1)
            cursor_press(e, 'UP', rows - 2)
            cursor_press(e, 'DOWN', rows - 1)
            select(e, 0)
            x = e.peek('MOD_OPT_TEXT_X', 'h')
            w = e.peek('MOD_OPT_TEXT_W', 'h')
            assert x >= 8 and x + w <= 312, (LANGS[lang], name, x, w)
            e.wait(.3)
            capture(e, out / f'options-{LANGS[lang]}-{name}.png')
            if lang in (0, 4):
                e.run('save', str(out / f'choice-{LANGS[lang]}-{name}.state'))
            matrix.append(dict(language=LANGS[lang], font=name, rows=rows, x=x, width=w,
                               cursor_bounds=True, font_value_wrap=True, file=f'options-{LANGS[lang]}-{name}.png'))
            print('OPTIONS', LANGS[lang], name, x, w, flush=True)
        # The row following DIGITAL CLOCK must still control EVOLUTION GUIDE.
    select(e, 3 if baseline else 2)
    before = e.peek('MOD_OPT_EVO_GUIDE', 'i')
    e.press('CONFIRM', 12)
    assert e.peek('MOD_OPT_EVO_GUIDE', 'i') == 1 - before
    e.press('CONFIRM', 12)
    settle_title(e)
    select(e, rows - 1)
    enemy = e.peek('MOD_OPT_ENEMY_BARS', 'i')
    e.press('CONFIRM', 12)
    settle_title(e)
    assert e.peek('MOD_OPT_ENEMY_BARS', 'i') == 1 - enemy
    e.press('CONFIRM', 12)
    settle_title(e)
    assert e.peek('MOD_OPT_ENEMY_BARS', 'i') == enemy
    return matrix


def settle_field(e):
    # Control returns before the map's native fade finishes.
    await_value(e, 'FADE_PROTECTION', 'i', 0)
    await_value(e, 'FADE_IN_CURRENT', 'h', 0)
    await_value(e, 'FADE_OUT_CURRENT', 'h', 0)
    e.wait(.5)


def open_status(e, menu_shot):
    # UIBoxData.state is at +18 in each 36-byte entry (boxes 0 and 1).
    for _ in range(5):
        if e.peek('IS_IN_MENU', 'i'):
            break
        e.press('TRIANGLE', 16)
        e.wait(.2)
    await_value(e, 'IS_IN_MENU', 'i', 1)
    await_value(e, 'UI_BOX_DATA+18', 'h', 1)
    capture(e, menu_shot)
    for _ in range(5):
        if e.peek('MENU_OPTIONS+4', 'h') == 2:
            break
        e.press('RIGHT', 16)
        e.wait(.2)
    assert e.peek('MENU_OPTIONS+4', 'h') == 2
    e.press('CONFIRM', 16)
    await_value(e, 'UI_BOX_DATA+54', 'h', 1)
    await_value(e, 'DIGIMON_MENU_STATE', 'b', 0)
    await_value(e, 'MENU_STATE', 'b', 1)
    e.wait(.3)


def panels(e, out, baseline):
    # Restore the untouched title state: Continue must apply the legacy OFF byte.
    e.run('load', str(out / 'title.state'))
    e.run('resume')
    assert e.continue_game() == 0
    settle_field(e)
    assert len(e.ram()) == 2097152
    assert e.peek('MOD_COLD_CACHE_TYPE', 'i') == -1, 'game detected expanded RAM'
    assert e.peek('MOD_OPT_TOUCHED', 'i') == 0
    if baseline:
        assert e.peek('MOD_OPT_BARS', 'i') == 0
        e.poke('MOD_OPT_BARS', struct.pack('<i', 1))
    else:
        assert not e.has('MOD_OPT_BARS')
    # Record the loaded field before applying presentation fixtures.
    e.gs('set', 'gametime_running=1')
    await_value(e, 'STATUS_UI_OFFSET_X', 'h', 75)
    e.wait(.3)
    capture(e, out / 'old-OFF-loaded.png')
    e.run('save', str(out / 'field.state'))
    captured = []
    for lang in ('en', 'de'):
        if lang == 'de':
            e.run('load', str(out / 'choice-de-NEW.state'))
            e.run('resume')
            e.press('CANCEL', 12)
            await_value(e, 'CURRENT_MENU', 'i', 0)
            assert e.continue_game() == 0
            settle_field(e)
            assert e.peek('MOD_LANG', 'i') == 4
            if baseline:
                e.poke('MOD_OPT_BARS', struct.pack('<i', 1))
            e.run('save', str(out / 'field-de.state'))
        for name, font in FONTS:
            e.run('load', str(out / ('field.state' if lang == 'en' else 'field-de.state')))
            e.run('resume')
            call(e, 'modSetFont', font)
            e.run('resume')
            e.gs('set', 'partner.para.happiness=52', 'partner.para.discipline=32',
                 'partner.para.tiredness=40', 'partner.para.foodLevel=120',
                 'partner.para.poopLevel=24', 'partner.para.condition=0',
                 'partner.para.virusBar=6', 'partner.para.careMistakes=7',
                 'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000',
                 'hour=12', 'minute=0', 'partner.para.energyLevel=500',
                 'partner.para.sleepyHour=23', 'gametime_running=1')
            await_value(e, 'STATUS_UI_OFFSET_X', 'h', 75)
            e.wait(.3)
            capture(e, out / f'hud-{lang}-{name}.png')
            open_status(e, out / f'field-menu-{lang}-{name}.png')
            capture(e, out / f'status-{lang}-{name}.png')
            captured.append(f'{lang}-{name}')
            print('PANELS', lang, name, flush=True)

    return captured


def verify_save_writer(e):
    # The release compiler may inline the private header helper. Exercise the
    # real save preparation and its header caller, retaining optimized code.
    call(e, 'loadMenuOverlay')
    call(e, 'prepareSaveFile', 1)
    size = call(e, 'saveExtSize')
    address = call(e, 'saveExtOf', 0)
    e.table['PROOF_SAVE_EXTENSION'] = address
    extension = e.raw('PROOF_SAVE_EXTENSION', size, e.ram())
    records = dict(mcd.parse_records(extension))
    assert len(records[9]) == 14 and records[9][3] == 1, records[9].hex()
    mirror = call(e, 'saveExtOf', 1)
    e.table['PROOF_SAVE_EXTENSION'] = mirror
    assert e.raw('PROOF_SAVE_EXTENSION', size, e.ram()) == extension
    call(e, 'modTitleNames')
    header = e.raw('SAVE_FILE+80', 16, e.ram())
    assert header[0] == ord('O') and header[7] == 1, header.hex()
    e.run('resume')
    return dict(record_bytes=records[9].hex(), header_bytes=header.hex(), mirror_identical=True)


def compare_panels(out, before):
    from tools.image import Image, ImageChops
    results = []
    for lang in ('en', 'de'):
        for font, _ in FONTS:
            for kind, box in (('hud', (235, 184, 310, 228)),
                              ('status', (16, 165, 310, 222)),
                              ('status', (161, 112, 310, 222))):
                name = f'{kind}-{lang}-{font}.png'
                old = Image.open(before / name).convert('RGB').crop(box)
                new = Image.open(out / name).convert('RGB').crop(box)
                diff = ImageChops.difference(old, new)
                bounds = diff.getbbox()
                if bounds:
                    diff.save(out / ('difference-' + name))
                assert bounds is None, (name, box, bounds)
                results.append(dict(file=name, crop=box, pixels_identical=True))
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disc', required=True)
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=41971)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--resume-validation', action='store_true', help='validate completed capture files and the native save writer')
    p.add_argument('--compare', type=Path, help='baseline capture directory for exact care-panel pixel checks')
    p.add_argument('--resume-panels', action='store_true', help="reuse this build's captured title states")
    a = p.parse_args()
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = emulator(str(Path(a.disc).resolve()), str(Path(a.exe).resolve()), a.port, out)
    # Emu expressions accept a single offset, so name the count byte explicitly.
    e.table['OPTIONS_CURSOR_COUNT'] = e.A(CURSOR) + 1
    xvfb = None
    if not os.environ.get('DISPLAY'):
        display = ':' + str(300 + a.port % 1000)
        xvfb = subprocess.Popen(['Xvfb', display, '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        e.env['DISPLAY'] = display
        time.sleep(.5)
    try:
        card = field_card(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd', out / 'old-off.mcd')
        data = mcd.Card(card).read('BASLUS-01032DMR0')
        assert data[0x57] == 0
        size = 0x2000 if len(data) >= 0x6000 else 0x1000
        for off in (0x2000, 0x2000 + size):
            records = dict(mcd.parse_records(data[off:off + size]))
            assert records[9][3] == 0
        e.start(str(card))
        report = dict(ram_bytes=len(e.ram()), legacy_saved_byte=0, baseline=a.baseline,
                      emulator_args=e.env['EMU_ARGS'])
        if not a.resume_panels and not a.resume_validation:
            report['title'] = title_matrix(e, out, a.baseline)
            (out / 'title-result.json').write_text(json.dumps(report, indent=2) + '\n')
        else:
            report = json.loads((out / 'title-result.json').read_text())
        if a.resume_validation:
            e.run('load', str(out / 'field.state'))
            e.run('resume')
            settle_field(e)
            assert e.peek('MOD_OPT_TOUCHED', 'i') == 0
            assert e.peek('MOD_COLD_CACHE_TYPE', 'i') == -1
            assert not e.has('MOD_OPT_BARS')
            report['panels'] = [f'{lang}-{font}' for lang in ('en', 'de') for font, _ in FONTS]
        else:
            report['panels'] = panels(e, out, a.baseline)
        if not a.baseline:
            report['save_writer'] = verify_save_writer(e)
            report['expanded_cache_type'] = e.peek('MOD_COLD_CACHE_TYPE', 'i')
        if a.compare:
            report['comparison'] = compare_panels(out, a.compare.resolve())
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('PASS: title matrix, cursor bounds/value wrap, evolution row, legacy OFF load, permanent care panels', flush=True)
    finally:
        e.stop()
        if xvfb:
            xvfb.terminate()
            xvfb.wait(timeout=10)


if __name__ == '__main__':
    main()
