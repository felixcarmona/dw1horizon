#!/usr/bin/env python3
"""Drives Patamon's item shop (screen 216) by the game's own RAM state, not by timed presses.

A press can be dropped (a busy machine, a slow disc); every step here presses, waits, reads the state
and presses again until the state is the wanted one. State read (decomp src/main/script_common.c openShop,
tickItemMenu): SCRIPT_STATE_2 (1 = the script waits), SCRIPT_TEXTBOX_MODE (2 only while the
Buy/Sell/See ya choice waits), ITEM_MENU_TYPE (0 buy, 1 sell), UI_BOX_DATA[n].state (1 = open: box 1 = the list,
box 2 = the choice and the bits box, box 3 = the amount box).

Usage (EMU_PORT picks the emulator, GS_MAP = the symbol map of the disc being played, as for game_state.py):
  shopnav.py state              prints the state
  shopnav.py enter              from the world: sets the story flags and money, warps to screen 216, goes to
                                Patamon and talks until the Buy/Sell/See ya choice is open
  shopnav.py goto buy|sell|amount   enter, then the choice, then the buy list / sell list / the amount box over
                                the buy list; exit 0 only when that state was reached (and is still there)
Each goto step prints the state it waited for; a step that never changes fails with exit 1.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, struct, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(_DEV_ROOT, 'tools')
sys.path.insert(0, TOOLS)
from tools.dev import symbols as dwsyms; from tools.dev import game_state as gamestate

if os.environ.get('GS_MAP'):   # an explicit symbol map (as game_state_with_map.py): auto-detection can pick the wrong worktree
    dwsyms.CANDIDATES['explicit-map'] = (dwsyms.CANDIDATES['orig'][0], os.environ['GS_MAP'])
    gamestate.BUILD = 'explicit-map'
UI_BOX_SIZE, UI_STATE_OFF = 0x24, 0x12      # UIBoxData: 2 RECT, frame, state ... (include/dw/ui.h)
EMU = os.path.join(os.path.dirname(TOOLS), 'tools/dev/emulator.py')


def emu(*a):
    return subprocess.run([sys.executable, EMU, *map(str, a)], capture_output=True, text=True).stdout


def state():
    ram = gamestate.read_ram()
    def rd(sym, fmt, off=0):
        a = gamestate.A(sym) + off - 0x80000000
        return struct.unpack_from('<' + fmt, ram, a)[0]
    return dict(screen=rd('CURRENT_SCREEN', 'B'), tamer=rd('TAMER_STATE', 'b'), paused=rd('IS_SCRIPT_PAUSED', 'i'),
                s2=rd('SCRIPT_STATE_2', 'H'), mode=rd('SCRIPT_TEXTBOX_MODE', 'B'), menu=rd('ITEM_MENU_TYPE', 'B'),
                item=rd('SHOP_ITEM_TYPE', 'B'), shopvar=rd('SHOP_VARIABLE', 'i'),
                box=[rd('UI_BOX_DATA', 'h', i * UI_BOX_SIZE + UI_STATE_OFF) for i in range(6)])


def at_choice(s): return s['s2'] == 1 and s['mode'] == 2 and s['box'][2] == 1 and s['box'][1] == 0 and s['box'][3] == 0
def at_list(s, kind): return s['s2'] == 1 and s['menu'] == kind and s['box'][1] == 1 and s['box'][3] == 0 and s['shopvar'] == 0
def at_amount(s): return s['s2'] == 1 and s['menu'] == 0 and s['box'][1] == 1 and s['box'][3] == 1


def settle(cond, secs=6.0, poll=0.5):
    """True if cond(state) holds, and still holds a moment later (a box that is closing does not count)."""
    end = time.time() + secs
    while time.time() < end:
        if cond(state()):
            time.sleep(0.7)
            if cond(state()): return True
        time.sleep(poll)
    return False


def press_until(button, cond, what, tries=12, frames=4, secs=3.0):
    """Presses `button` and waits for cond; presses again if the state did not change (a dropped press)."""
    for n in range(tries):
        if cond(state()) and settle(cond, 1.5): print(f'shopnav: {what} (press {n})'); return True
        emu('press', button, frames)
        if settle(cond, secs): print(f'shopnav: {what} (press {n + 1})'); return True
    print(f'shopnav: FAILED waiting for {what}: {state()}', file=sys.stderr)
    return False


def enter():
    for k in (('trigger', 231, 1), ('trigger', 65, 1), ('pstat', 26, 1), ('set', 'money=50000')):
        gamestate_cmd(*k)
    gamestate_cmd('warp', 216)
    end = time.time() + 30
    while time.time() < end:   # the new screen is loaded and the player is free
        s = state()
        if s['screen'] == 216 and s['tamer'] == 0 and s['paused'] == 1: break
        time.sleep(0.5)
    else:
        print(f'shopnav: FAILED to reach screen 216 with control: {state()}', file=sys.stderr); return False
    time.sleep(1)
    gamestate_cmd('move', -350, -50)   # the counter, in front of Patamon (where the walk of the old recipe ended)
    time.sleep(0.5)
    return press_until('CROSS', at_choice, 'Buy/Sell/See ya choice open', tries=14, secs=3.5)


def gamestate_cmd(*a):
    sys.argv = ['game_state.py', *map(str, a)]
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()): gamestate.main()



def back_to_choice():
    return press_until('CIRCLE', at_choice, 'back at the choice', tries=6)


def goto(target):
    """The cursor moves are not readable from RAM, so what they led to is: a list of the wrong kind, or the
    amount box of the wrong item (SHOP_ITEM_TYPE 1 = Medium Recovery, the buy list's second row), is closed
    with CIRCLE and the whole step is played again."""
    if not enter(): return False
    for attempt in range(4):
        if target == 'sell':
            emu('press', 'DOWN', 6); time.sleep(1.0)
            ok = press_until('CROSS', lambda s: at_list(s, 1) or at_list(s, 0), 'a list open', tries=4)
            if ok and at_list(state(), 1): return True
            if ok: print('shopnav: the buy list opened (a dropped DOWN), going back'); press_until('CIRCLE', at_choice, 'back at the choice', tries=6)
            continue
        if not at_list(state(), 0):
            if not press_until('CROSS', lambda s: at_list(s, 0), 'buy list open'): return False
        if target == 'buy': return True
        emu('press', 'DOWN', 6); time.sleep(1.0)
        if press_until('CROSS', at_amount, 'amount box open', tries=3):
            if state()['item'] == 1: return True
            print(f"shopnav: the amount box is for item {state()['item']}, not 1 (a dropped DOWN), closing it")
            press_until('CIRCLE', lambda s: at_list(s, 0), 'back at the buy list', tries=4)
    print(f'shopnav: FAILED to reach {target}: {state()}', file=sys.stderr)
    return False


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['state']: print(state())
    elif a[:1] == ['enter']: sys.exit(0 if enter() else 1)
    elif a[:1] == ['goto'] and len(a) == 2 and a[1] in ('buy', 'sell', 'amount'): sys.exit(0 if goto(a[1]) else 1)
    else: sys.exit(__doc__)
