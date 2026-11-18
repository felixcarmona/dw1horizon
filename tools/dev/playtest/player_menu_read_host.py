#!/usr/bin/env python3
"""Compile the Player view's MENU read on the host; no disc assets needed.

Run after preparing a patched tree: python3 tools/dev/playtest/player_menu_read_host.py build/decomp-dev
Choosing Player in the Triangle menu must not read MENU_REL with a blocking read (the picture stood still for about a
third of a second): the choice only moves to state 5, which queues the read when the file queue and the tile stream
are idle and opens the view once the queue says the read landed.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

from quick_care_host import function


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-dev')
    menu = (root / 'src/main/game_menu.c').read_text()
    a = menu.index('\tcase 3:\n\t\tplayerMenuQueued = 0;')
    choice = menu[a:menu.index('break;', a)]
    assert 'loadMenuOverlay' not in choice and 'TRIANGLE_MENU_STATE = 5' in choice, 'Player reads MENU_REL blocking again'
    assert 'UI_BOX_DATA[0].frame == 0 && playerMenuRead()' in menu, 'state 5 opens the view before MENU landed'
    read_fn = function(menu, 'static int32_t playerMenuRead(void)\n{')
    prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define MENU_REL 17
static int32_t queued, idle, tfsBusy;
static uint8_t playerMenuQueued, playerMenuDone, *readFlag;
static int32_t isFileReadQueueIdle(void) { return idle; }
static int32_t tfsStreamBusy(void) { return tfsBusy; }
static void loadDynamicLibrary(int lib, uint8_t *flag, int async, void *cb, void *param) {
    assert(lib == MENU_REL && flag == &playerMenuDone && async == 1 && cb == 0 && param == 0); queued++; readFlag = flag;
}
'''
    tests = r'''
int main(void) {
    playerMenuQueued = 0; playerMenuDone = 1;                 /* a stale flag from an earlier read */
    idle = 0; assert(!playerMenuRead() && !queued);           /* a battle read ahead in the queue */
    idle = 1; tfsBusy = 1; assert(!playerMenuRead() && !queued); /* a tile read in flight */
    tfsBusy = 0; assert(!playerMenuRead() && queued == 1 && playerMenuQueued);
    for (int i = 0; i < 5; i++) assert(!playerMenuRead() && queued == 1); /* the field keeps going, one request */
    *readFlag = 1; assert(playerMenuRead() && queued == 1);
    puts("Player view reads MENU in the background and opens once it landed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='player-read-host-') as temp:
        source = Path(temp) / 'player.c'
        exe = Path(temp) / 'player'
        source.write_text(prefix + read_fn + tests)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
