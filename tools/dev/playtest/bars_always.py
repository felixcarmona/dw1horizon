#!/usr/bin/env python3
"""Capture permanent care/clock/battle displays and legacy OFF migration on 2 MB.

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
    rows = 14 if baseline else 11
    assert e.peek('OPTIONS_CURSOR_COUNT', 'b') == rows
    font_row, lang_row = (9, 10) if baseline else (7, 8)
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
    # The first remaining gameplay row must still control EVOLUTION GUIDE.
    select(e, 3 if baseline else 1)
    before = e.peek('MOD_OPT_EVO_GUIDE', 'i')
    e.press('CONFIRM', 12)
    assert e.peek('MOD_OPT_EVO_GUIDE', 'i') == 1 - before
    e.press('CONFIRM', 12)
    settle_title(e)
    select(e, rows - 1)
    last_symbol = 'MOD_OPT_ENEMY_BARS' if baseline else 'MOD_OPT_CHEATS'
    enemy = e.peek(last_symbol, 'i')
    e.press('CONFIRM', 12)
    settle_title(e)
    assert e.peek(last_symbol, 'i') == 1 - enemy
    e.press('CONFIRM', 12)
    settle_title(e)
    assert e.peek(last_symbol, 'i') == enemy
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
        assert not any(e.has(n) for n in ('MOD_OPT_BARS','MOD_OPT_CLOCK','MOD_OPT_ENEMY_BARS','BATTLE_TOGGLE_LIFEBAR'))
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
    assert len(records[9]) == 14 and records[9][1] == 1 and records[9][3] == 1 and records[9][13] == 0, records[9].hex()
    mirror = call(e, 'saveExtOf', 1)
    e.table['PROOF_SAVE_EXTENSION'] = mirror
    assert e.raw('PROOF_SAVE_EXTENSION', size, e.ram()) == extension
    call(e, 'modTitleNames')
    header = e.raw('SAVE_FILE+80', 16, e.ram())
    assert header[0] == ord('O') and header[5] == 1 and header[7] == 1 and not (header[1] & 0x60), header.hex()
    e.run('resume')
    return dict(record_bytes=records[9].hex(), header_bytes=header.hex(), mirror_identical=True)


def battle_proof(e, out):
    """Observe native head-bar GPU submissions before and after Select presses."""
    from tools.langpatch import section_functions
    e.run('load', str(out / 'field.state'))
    e.run('resume')
    settle_field(e)
    e.poke('MOD_OPT_STORY', struct.pack('<i', 0))
    e.gs('set', 'gametime_running=1', 'partner.stats.off=10',
         'partner.stats.def=999', 'partner.para.evoTimer=0',
         'partner.para.remainingLifetime=1000', 'hour=12', 'minute=0')
    assert e.warp(0) and e.in_control()
    e.gs('approach', '0', '120')
    for _ in range(80):
        if e.peek('GAME_STATE', 'b') == 1 and e.peek('NO_AI_FLAG', 'i') == 0:
            break
        e.press('CONFIRM', 12)
        e.wait(.2)
    else:
        raise AssertionError('wild encounter did not start')
    # Keep the fixture alive; the original AI, camera and renderer keep running.
    e.run('pause')
    ram = e.ram()
    combat = e.peek('COMBAT_DATA_PTR', 'I', ram)
    count = e.peek('ENEMY_COUNT', 'h', ram)
    assert 1 <= count <= 3
    for i in range(1, count + 1):
        slot = ram[combat - 0x80000000 + 1644 + i]
        entity = e.peek(f'ENTITY_TABLE+{4 * slot}', 'I', ram)
        e.run('poke', hex(entity + 72), struct.pack('<h', 5000).hex())
        e.run('poke', hex(entity + 76), struct.pack('<h', 5000).hex())
    _, functions = section_functions(e.exe + '.elf', '.BTL')
    addresses = {name: start for start, _, name in functions}
    rect = addresses['enemyHPRect']
    render = addresses['BTL_renderEnemyHPBars']
    e.run('lua', f"""
      BAR_PROOF={{bp={{}},frames={{}},current=nil}}
      local m=PCSX.getMemPtr()
      local function byte(a) return tonumber(m[a-0x80000000]) end
      BAR_PROOF.bp[1]=PCSX.addBreakpoint({render},'Exec',4,'permanent-bars',function()
        local f={{bars=0,active=byte({e.A('GAME_STATE')})==1 and byte({e.A('NO_AI_FLAG')})==0}}
        table.insert(BAR_PROOF.frames,f);BAR_PROOF.current=f
      end)
      BAR_PROOF.bp[2]=PCSX.addBreakpoint({rect},'Exec',4,'permanent-bars',function()
        local r=PCSX.getRegisters().GPR.n
        if BAR_PROOF.current and tonumber(r.a2)==34 and tonumber(r.a3)==5 then
          BAR_PROOF.current.bars=BAR_PROOF.current.bars+1
        end
      end)
    """)
    e.run('resume')
    for phase in ('ordinary', 'select-once', 'select-twice'):
        if phase != 'ordinary':
            e.press('SELECT', 12)
        start = int(e.run('lua', 'return #BAR_PROOF.frames').strip())
        for _ in range(200):
            if int(e.run('lua', 'return #BAR_PROOF.frames').strip()) >= start + 30:
                break
            e.wait(.2)
        else:
            raise AssertionError('battle renderer stopped')
        capture(e, out / f'battle-{phase}.png')
    rows = e.run('lua', "local t={} for _,f in ipairs(BAR_PROOF.frames) do t[#t+1]=(f.active and '1' or '0')..':'..f.bars end return table.concat(t,',')").strip().strip('\"')
    values = [dict(active=a == '1', bars=int(b)) for a,b in (row.split(':') for row in rows.split(','))]
    e.run('lua', 'for _,b in ipairs(BAR_PROOF.bp) do b:remove() end')
    complete = [f for f in values[:-1] if f['active']]
    assert len(complete) >= 20, len(complete)
    assert all(f['bars'] > 0 for f in complete), complete
    assert len(e.ram()) == 2097152 and e.peek('MOD_COLD_CACHE_TYPE', 'i') == -1
    return dict(enemies=count, observed_frames=len(complete),
                head_bars_every_active_frame=True, select_presses=2,
                minimum_head_bars=min(f['bars'] for f in complete), ram_bytes=2097152)


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
        native = mcd.Card(card)
        data = bytearray(native.read('BASLUS-01032DMR0'))
        size = 0x2000 if len(data) >= 0x6000 else 0x1000
        data[0x51] |= 0x60  # Legacy original-style and brief enemy-bar flags.
        data[0x55] = data[0x57] = 0
        for off in (0x2000, 0x2000 + size):
            head = data[off:off + size]
            updated = []
            for tag, value in mcd.parse_records(head):
                if tag == 9:
                    value = bytearray(value).ljust(14, b'\0')
                    value[1] = value[3] = 0
                    value[13] = 3
                updated.append((tag, value))
            data[off:off + size] = mcd.build_extension(head, updated, size)
        native.write('BASLUS-01032DMR0', 0, data)
        for off in (0x2000, 0x2000 + size):
            options = dict(mcd.parse_records(data[off:off + size]))[9]
            assert options[1] == options[3] == 0 and options[13] == 3
        e.start(str(card))
        report = dict(ram_bytes=len(e.ram()), legacy_saved_byte=0, legacy_clock=0, legacy_enemy_flags=3, baseline=a.baseline,
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
            assert not any(e.has(n) for n in ('MOD_OPT_BARS','MOD_OPT_CLOCK','MOD_OPT_ENEMY_BARS','BATTLE_TOGGLE_LIFEBAR'))
            report['panels'] = [f'{lang}-{font}' for lang in ('en', 'de') for font, _ in FONTS]
        else:
            report['panels'] = panels(e, out, a.baseline)
        if not a.baseline:
            report['save_writer'] = verify_save_writer(e)
            report['battle'] = battle_proof(e, out)
            report['expanded_cache_type'] = e.peek('MOD_COLD_CACHE_TYPE', 'i')
        if a.compare:
            report['comparison'] = compare_panels(out, a.compare.resolve())
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        checks = 'reference title and care panels' if a.baseline else 'title matrix, cursor bounds/value wrap, legacy display choices, care panels, clock and continuous battle bars'
        print('PASS: ' + checks, flush=True)
    finally:
        e.stop()
        if xvfb:
            xvfb.terminate()
            xvfb.wait(timeout=10)


if __name__ == '__main__':
    main()
