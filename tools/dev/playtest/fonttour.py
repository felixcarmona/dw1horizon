#!/usr/bin/env python3
"""Screenshots of every screen that draws text, for checking a font change (docs/mods/font.md "Fonts").

  EMU_PORT=38770 tools/dev/playtest/fonttour.py DISC.cue OUTDIR [--proof] [--only NAME,...] [--card CARD.mcd]

From a fresh boot of CARD (default build/states/file-city.mcd: Agumon in Jijimon's house), items and bits are given and
these screens are shot (OUTDIR/NAME.png; with --vram also OUTDIR/NAME-text.png, the VRAM text area, white on black, 2x):
  menu (the pause menu, "Year Day"), items (+ the description), status, tech, techselect, techhelp, player, chart,
  medals, cards;
  with --only screens: the screens font b changed that no other tour reaches (needs the emulator with breakpoints, EMU_ARGS="-interpreter -debugger", set here;
  DW_SYMS must name the disc's executable build; about 6 minutes): cal-* (the tournament calendar on days 1, 9, 10, 28 and its info box), cardshop-yes/no
  (the card shop's All right? box), title-new/load/delete and mc-* (the title and memory card Yes/No screens), cond-* (the Tech list's pois/conf/stun/flat
  label), mojyamon (the trade header), curling-start/how (the curling options), gym-1..3 (the "learned!" box of TRN_renderMoveLearnedBox);
  with --proof (the disc's Jijimon runs tools/dws/examples/font-proof.dws: MAIN_STORY in place of dev-save): dialogue1, dialogue2, choice, shopmenu, shop,
  amount, bought, scriptitems, registration, saveslots (the registration slots), saveprompt ("Do you want to save?"); then caption (Native Forest's name), battle, battlemenu, results, results2, gains.
--long-name NAME shows the partner's species under NAME. `naming` boots without a card and shoots the name keyboard of a new game (about 3 minutes): --only naming.
Prints the shots taken; a screen that did not open is reported, not retried forever.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse, os, shutil, struct, subprocess, sys, time
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools', 'dev', 'playtest'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev.playtest.species_proof import run, seq, mem, mset, boot, in_world, partner_type, E, G      # noqa: E402

VRAM = False
ITEMS = [69, 0, 29, 70, 44, 3, 38, 105]          # Happymushrm, sm.recovery, DV Chip A, Chain melon, Digimushrm, ...
AMOUNTS = [3, 5, 1, 2, 9, 1, 12, 1]


def shot(out, name):
    p = os.path.join(out, name + '.png')
    seq(f'shot {p}')
    if VRAM:                                     # the dump pauses the emulator: a press right after it can be lost
        v = os.path.join(out, name + '.vram')
        run(E + ['vram', v])
        text_area(v, os.path.join(out, name + '-text.png'))
        os.remove(v)
        seq('wait 2')
    print(p)
    return p


def text_area(vram, png):
    """The 256x256 4-bpp text area (VRAM x 704, y 256): ink white, 2x."""
    from tools.image import Image
    v = open(vram, 'rb').read()
    im = Image.new('L', (256, 256))
    px = []
    for y in range(256):
        row = struct.unpack_from('<64H', v, ((256 + y) * 1024 + 704) * 2)
        for h in row:
            px += [255 if (h >> (4 * k)) & 15 else 0 for k in range(4)]
    im.putdata(px)
    im.resize((512, 512), Image.NEAREST).save(png)


def give():
    run(G + ['set', 'inventory.types=' + str(ITEMS + [-1] * (30 - len(ITEMS))).replace(' ', ''),
             'inventory.amounts=' + str(AMOUNTS + [0] * (30 - len(AMOUNTS))).replace(' ', ''), 'money=9000'])


def long_name(name, current='Agumon'):
    """The partner's species name in RAM (each 20-byte name field that holds `current`) replaced by `name`: the long-name
    screens without a species that has one (status, tech, battle, results, registration, save slots)."""
    ram = subprocess.run(E + ['ramdump'], capture_output=True, cwd=ROOT).stdout
    old = current.encode() + b'\0'
    n, at = 0, ram.find(old)
    while at >= 0:
        field = ram[at:at + 20]
        if len(name) < 20 and field[len(old):].strip(b'\0') == b'':
            run(E + ['poke', hex(0x80000000 + at), (name.encode() + b'\0' * (20 - len(name))).hex()]); n += 1
        at = ram.find(old, at + 1)
    print(f'long name: {n} fields of "{current}" now "{name}"')


def menus(out):
    """The pause menu and its screens; a tab is pressed until the menu's state says it is open (a press can be dropped)."""
    seq('wait 3, TRIANGLE 8, wait 6'); shot(out, 'menu')
    seq('wait 2, CROSS 10, wait 8'); shot(out, 'items')
    seq('TRIANGLE 8, wait 5, RIGHT 8, wait 2, CROSS 8, wait 8'); shot(out, 'status')
    seq('until DIGIMON_MENU_STATE 1 1 RIGHT 5, wait 4'); shot(out, 'tech')
    seq('CROSS 8, wait 4'); shot(out, 'techselect')
    seq('SQUARE 8, wait 4'); shot(out, 'techhelp')
    seq('TRIANGLE 8, wait 3, TRIANGLE 8, wait 3, TRIANGLE 8, wait 5')
    seq('wait 2, RIGHT 8, wait 2, CROSS 8, wait 8'); shot(out, 'player')
    for name in ('chart', 'medals', 'cards'):
        seq('RIGHT 8, wait 6'); shot(out, name)
    seq('TRIANGLE 8, wait 5, TRIANGLE 8, wait 5')


def talk(pages):
    """Talk to Jijimon and go through his `pages` dialogue pages, until his choice is open (its option count is 3: a
    dropped press is pressed again)."""
    run(G + ['approach', '0'])
    seq('wait 1, CROSS 6, wait 4')
    seq('talk DIALOGUE_SELECTION+8 2 3 20, wait 2')


CHOOSE = 'until DIALOGUE_SELECTION+10 2'    # + N DOWN: press DOWN until the choice's cursor is on option N (a press can be dropped)


def proof(out, fresh):
    """Jijimon of font-proof.dws: the dialogue, the choice and the shop; then, each from a fresh boot (`fresh()`), the
    item list a script opens and the save machine."""
    run(G + ['approach', '0'])
    seq('wait 1, CROSS 6, wait 4'); shot(out, 'dialogue1')
    seq('CROSS 6, wait 4'); shot(out, 'dialogue2')
    seq('CROSS 6, wait 4'); shot(out, 'choice')
    seq('CROSS 6, wait 6, CROSS 6, wait 4'); shot(out, 'shopmenu')
    seq('CROSS 6, wait 8'); shot(out, 'shop')
    seq('CROSS 6, wait 6'); shot(out, 'amount')
    seq('CROSS 6, wait 4'); shot(out, 'bought')
    fresh()
    talk(2); seq(f'{CHOOSE} 1 DOWN 6, wait 1, CROSS 6, wait 8'); shot(out, 'scriptitems')
    fresh()
    talk(2); seq(f'{CHOOSE} 2 DOWN 6, wait 1, CROSS 6, wait 10'); shot(out, 'registration')
    seq('wait 2, CROSS 6, wait 8'); shot(out, 'saveslots')                       # Yes: the registration slots
    fresh()
    talk(2); seq(f'{CHOOSE} 2 DOWN 6, wait 1, CROSS 6, wait 12, DOWN 8, wait 3, CROSS 6, wait 8')
    shot(out, 'saveprompt')                                                       # No: "Do you want to save?" Yes / No
    fresh()


def world(out):
    run(G + ['warp', '1', '0']); seq('wait 6'); run(G + ['warp', '0', '0'])
    seq('wait 3'); shot(out, 'caption')
    seq('wait 8'); run(G + ['approach', '0']); seq('wait 1, CROSS 4, wait 4, CROSS 4, wait 30'); shot(out, 'battle')
    seq('CIRCLE 4, wait 6'); shot(out, 'battlemenu')
    mset('NPC_ENTITIES[0].digimonEntity.stats.current.currentHP=0')
    seq('wait 12'); shot(out, 'results')
    seq('wait 8'); shot(out, 'results2')
    seq('CROSS 4, wait 6'); shot(out, 'gains')


def naming(out, cue):
    run(E + ['stop'])
    run(E + ['start', cue])
    seq('wait 45, START 20, wait 6, START 20, wait 6, CROSS 10, wait 4, DOWN 8, wait 1, DOWN 8, wait 1, CROSS 10, '
        'wait 6, CROSS 10, wait 3, CROSS 10')
    seq('until DRAW_STRING2_IS_FIXED_WIDTH 1 1 CROSS 200')
    seq('wait 20'); shot(out, 'naming')
    seq('RIGHT 4, wait 2, DOWN 4, wait 2, CROSS 4, wait 3, CROSS 4, wait 3, CROSS 4, wait 6'); shot(out, 'naming2')


# ---- screens that only a script or a RAM poke reaches (--only screens) ------------------------------------------------

def call(fn, *args, out):
    """Calls the game function `fn` once, at the next frame, from gameLoop's entry (the hijack of call_function.py; the emulator
    must run with breakpoints: EMU_ARGS="-interpreter -debugger"). True when it ran."""
    from tools.dev import symbols as dwsyms
    t = dwsyms.table(dwsyms.explicit_build(os.environ['DW_SYMS']))
    gl = t['gameLoop']
    v = [((t[a] if isinstance(a, str) else a) & 0xFFFFFFFF) for a in args] + [0] * (4 - len(args))
    lua = f"""
if CF and CF.bp then CF.bp:remove() end
CF = {{ phase = 0, saved = 0, n = 0, q = {{ {{{t[fn]}, {v[0]}, {v[1]}, {v[2]}, {v[3]}}} }} }}
CF.bp = PCSX.addBreakpoint({gl}, 'Exec', 4, 'fonttour', function()
  local r = PCSX.getRegisters()
  if CF.phase == 1 then r.GPR.n.ra = CF.saved; CF.phase = 0; CF.n = CF.n + 1; return end
  if CF.phase == 0 and #CF.q > 0 then
    local c = table.remove(CF.q, 1)
    CF.saved = r.GPR.n.ra
    r.GPR.n.a0 = c[2]; r.GPR.n.a1 = c[3]; r.GPR.n.a2 = c[4]; r.GPR.n.a3 = c[5]
    r.GPR.n.ra = {gl}; r.pc = c[1]; CF.phase = 1
  end
end)
return 'armed'
"""
    p = os.path.join(out, 'call.lua')
    open(p, 'w').write(lua)
    run(E + ['lua', f"dofile('{p}')"])
    for _ in range(60):
        time.sleep(0.5)
        o = run(E + ['lua', 'return CF.n']).strip()
        if o.isdigit() and int(o) >= 1: return True
    return False


def poke32(sym, v):
    run(E + ['poke', sym, (v & 0xFFFFFFFF).to_bytes(4, 'little').hex()])


def set_status(s):
    """Every MOVE_DATA row's status = s (Move is 16 bytes, status at +10): the technique under the Tech list's cursor shows it."""
    from tools.dev import symbols as dwsyms
    a = dwsyms.resolve('MOVE_DATA', dwsyms.explicit_build(os.environ['DW_SYMS'])) & 0x1FFFFFFF
    run(E + ['lua', "local m = PCSX.getMemPtr(); for i = 0, 121 do m[%d + 16 * i + 10] = %d end return 1" % (a, s)])


def all_cups():
    """Every cup's trigger set (200-311 and the grade A cup, 18): the calendar lists the whole schedule."""
    from tools.dev import symbols as dwsyms
    a = (dwsyms.resolve('SCRIPT_STATE', dwsyms.explicit_build(os.environ['DW_SYMS'])) + 245) & 0x1FFFFFFF
    run(E + ['lua', "local m = PCSX.getMemPtr(); for i = 25, 38 do m[%d + i] = 255 end m[%d + 2] = bit.bor(m[%d + 2], 4) return 1" % (a, a, a)])


def press_until(buttons, cond, tries=14, gap='wait 2'):
    """Presses (a step list) until cond() holds; a dropped press is pressed again."""
    for _ in range(tries):
        if cond(): return True
        seq(buttons + ', ' + gap)
    return cond()


def screens(out, cue, card, parts):
    os.environ.setdefault('EMU_ARGS', '-interpreter -debugger')
    cue = cue if os.path.isabs(cue) else os.path.join(ROOT, cue)
    st_title, st_world = os.path.join(out, 'title.state'), os.path.join(out, 'world.state')
    run(E + ['stop'])
    shutil.copy(os.path.join(ROOT, card), os.path.join(out, 'card.mcd'))
    run(E + ['start', cue, '--card', os.path.join(out, 'card.mcd')])
    seq('wait 45, START 20, wait 6, START 20, wait 6')
    run(E + ['save', st_title])
    seq('DOWN 8, wait 1, CROSS 10, wait 5, CROSS 10, wait 5, CROSS 10, wait 4, CROSS 10, wait 14')
    for _ in range(6):
        if in_world(): break
        seq('CROSS 10, wait 12')
    else:
        sys.exit('did not reach the world')
    seq('wait 12')
    run(E + ['save', st_world])
    load = lambda st: (run(E + ['load', st]), seq('wait 3'))

    def warp(n):
        run(G + ['warp', str(n)])
        for _ in range(40):
            seq('wait 1')
            m = mem('CURRENT_SCREEN', 'TAMER_STATE', 'IS_SCRIPT_PAUSED')
            if m.get('CURRENT_SCREEN') == n and m.get('TAMER_STATE') == 0 and m.get('IS_SCRIPT_PAUSED') == 1: break
        seq('wait 2')
    box = lambda i: mem(f'UI_BOX_DATA[{i}].state').get(f'UI_BOX_DATA[{i}].state')

    if 'cal' in parts:
        # tournament calendar: the arena desk (script 168 section 81 -> 213/81), days 1, 9 (first date padded), 10, 28 (wraps)
        for name, day, cups in (('cal-day1', 0, 0), ('cal-day9', 8, 0), ('cal-day10', 9, 0), ('cal-day28', 27, 0),
                                ('cal-all-day1', 0, 1), ('cal-all-day9', 8, 1), ('cal-all-day10', 9, 1), ('cal-all-day17', 16, 1)):
            load(st_world); warp(208)
            run(G + ['trigger', '91', '1']); run(G + ['set', f'day={day}'])
            if cups: all_cups()
            call('callScriptSection', 168, 81, 1, out=out)
            if not press_until('CROSS 6', lambda: box(1) == 1 and box(2) == 1, tries=14, gap='wait 4'):
                print(f'{name}: the calendar did not open'); continue
            seq('wait 3'); shot(out, name)
            if name == 'cal-day1':
                seq('CROSS 6, wait 6'); shot(out, 'cal-info')                  # the first grade's info box

    if 'card' in parts:
        # card shop (Gear Savanna): Buy cards > Buy one card > a card: the "All right?" Yes/No box
        load(st_world); warp(131)
        run(G + ['trigger', '139', '1']); run(G + ['set', 'money=5000'])
        call('callScriptSection', 126, 81, 1, out=out)
        seq('wait 3, CROSS 6, wait 5, CROSS 6, wait 5, CROSS 6, wait 5, DOWN 6, wait 3, CROSS 6, wait 6')   # talk, Buy cards, Buy one card
        if press_until('CROSS 6', lambda: box(3) == 1, tries=6, gap='wait 4'):
            seq('wait 3'); shot(out, 'cardshop-yes')
            seq('RIGHT 6, wait 3'); shot(out, 'cardshop-no')
        else:
            print('cardshop: the Yes/No box did not open')

    if 'title' in parts:
        # title and memory card Yes/No screens: the menu is forced (TARGET_MENU) with the slot action it belongs to
        for name, menu, act in (('title-new', 15, 0), ('title-load', 24, 1), ('title-delete', 34, 2), ('mc-format', 1, 0),
                                ('mc-nocard', 19, 0), ('mc-replace', 48, 0), ('mc-battle', 50, 0), ('mc-saveyes', 66, 0), ('mc-saveprompt', 69, 0)):
            load(st_title)
            poke32('MAIN_MENU_ACTION', act); poke32('TARGET_MENU', menu)
            seq('wait 4'); shot(out, name)

    if 'cond' in parts:
        # the Tech list's status label (pois conf stun flat): the technique under the cursor made to inflict each status
        load(st_world)
        seq('wait 3, TRIANGLE 8, wait 6, wait 2, CROSS 10, wait 8, TRIANGLE 8, wait 5, RIGHT 8, wait 2, CROSS 8, wait 8')
        seq('until DIGIMON_MENU_STATE 1 1 RIGHT 5, wait 4, CROSS 8, wait 4, RIGHT 6, wait 3, RIGHT 6, wait 3')   # the cursor on the learned technique
        for s, name in ((0, 'none'), (1, 'pois'), (2, 'conf'), (3, 'stun'), (4, 'flat')):
            set_status(s); seq('wait 3'); shot(out, 'cond-' + name)

    if 'mojyamon' in parts:
        # Mojyamon's trade list (script 129 section 7 on screen 134)
        load(st_world); warp(134)
        call('callScriptSection', 129, 7, 1, out=out)
        press_until('CROSS 6', lambda: box(1) == 1, tries=8, gap='wait 4')
        seq('wait 3'); shot(out, 'mojyamon')

    if 'curling' in parts:
        # curling: Penguinmon's talk up to the Start / How to play box
        load(st_world); warp(235)
        run(G + ['approach', '0']); seq('wait 1, CROSS 6, wait 4')
        if press_until('CROSS 6', lambda: mem('MAIN_D_80135250').get('MAIN_D_80135250') == 3 and box(0) == 1, tries=30, gap='wait 6'):
            seq('wait 8'); shot(out, 'curling-start')       # the box opens before its text and the scoreboards are drawn
            seq('DOWN 6, wait 3'); shot(out, 'curling-how')
        else:
            print('curling: the options box did not open')

    if 'gym' in parts:
        # the gym's "learned!" box: the training library loaded, the partner's techniques forgotten, every weight 100
        load(st_world); warp(112)
        from tools.dev import symbols as dwsyms
        t = dwsyms.table(dwsyms.explicit_build(os.environ['DW_SYMS']))
        call('loadTrainingLibrary', 112, out=out); seq('wait 8')
        run(E + ['poke', hex(t['TRN_D_8008F184']), '64' * 24])
        mset('PARTNER_ENTITY.learnedMoves[0]=0', 'PARTNER_ENTITY.learnedMoves[1]=0')
        ptype = partner_type()
        for i in (1, 2, 3):                       # each call learns the next technique, so a different name
            call('TRN_tryLearnMove', ptype, out=out); seq('wait 4'); shot(out, f'gym-{i}')



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cue'); ap.add_argument('out')
    ap.add_argument('--proof', action='store_true')
    ap.add_argument('--long-name', help='the partner species shown with this name (e.g. MetalGreymonVaccine)')
    ap.add_argument('--vram', action='store_true', help='also each VRAM text area (NAME-text.png)')
    ap.add_argument('--only', default='menus,proof,world')
    ap.add_argument('--card', default='build/states/file-city.mcd')
    ap.add_argument('--parts', default='cal,card,title,cond,mojyamon,curling,gym', help='for --only screens: which of its parts')
    a = ap.parse_args()
    assert os.environ.get('EMU_PORT'), 'set EMU_PORT'
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    global VRAM
    VRAM = a.vram
    only = a.only.split(',')
    if 'screens' in only:
        screens(out, a.cue, a.card, a.parts.split(','))
    if [x for x in only if x not in ('naming', 'screens')]:
        def fresh():
            card = os.path.join(out, 'card.mcd'); shutil.copy(os.path.join(ROOT, a.card), card)
            if not boot(os.path.join(ROOT, a.cue) if not os.path.isabs(a.cue) else a.cue, card):
                sys.exit('did not reach the world')
            give()
            if a.long_name: long_name(a.long_name)
        fresh()
        if 'menus' in only: menus(out)
        if 'proof' in only and a.proof: proof(out, fresh)
        if 'world' in only: world(out)
    if 'naming' in only:
        naming(out, a.cue)
    run(E + ['stop'])


if __name__ == '__main__':
    main()
