#!/usr/bin/env python3
"""Compile the care menu's opening on the host; no disc assets needed.

Run after preparing a patched tree: python3 tools/dev/playtest/care_menu_read_host.py build/decomp-dev
Square must not read MENU_REL with a blocking read (the field stood still for about 20 refreshes): feedOpen only
enters the menu, the read is queued when the file queue and the tile stream are idle, and the list is drawn once the
queue says the read landed.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

from quick_care_host import function


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-dev')
    feed = (root / 'src/main/mod_feed.c').read_text()
    open_fn = function(feed, 'static int32_t feedOpen(void)\n{')
    assert 'loadMenuOverlay' not in open_fn and 'readFile' not in open_fn, 'feedOpen reads MENU_REL blocking again'
    a = feed.index('\tcase FEED_QUEUING:')
    cases = feed[a:feed.index('\tcase FEED_OPENING:', a)]
    prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define MENU_REL 17
enum { FEED_OPENING, FEED_OPEN, FEED_CLOSING, FEED_GIVING, FEED_WATCHING, FEED_QUEUING, FEED_LOADING };
static int32_t feedState = -1, count = 1, entered, shown, queued, idle, tfsBusy;
static uint8_t feedMenuRead, *readFlag;
static int feedCollect(int needsOnly) { (void)needsOnly; return count; }
static void feedEnterMenu(void) { entered++; }
static void feedShow(void) { shown++; feedState = FEED_OPENING; }
static int isFileReadQueueIdle(void) { return idle; }
static int tfsStreamBusy(void) { return tfsBusy; }
static void loadDynamicLibrary(int lib, uint8_t *flag, int async, void *cb, void *param) {
    assert(lib == MENU_REL && flag == &feedMenuRead && async == 1 && cb == 0 && param == 0); queued++; readFlag = flag;
}
'''
    harness = '\nstatic void step(void) {\n\tswitch (feedState) {\n' + cases + '\tdefault:\n\t\tbreak;\n\t}\n}\n'
    tests = r'''
int main(void) {
    count = 0; assert(!feedOpen() && !entered && feedState == -1);
    count = 1; assert(feedOpen() && entered == 1 && feedState == FEED_QUEUING && !queued && !shown);
    idle = 0; step(); assert(!queued && feedState == FEED_QUEUING);           /* a battle read ahead in the queue */
    idle = 1; tfsBusy = 1; step(); assert(!queued && feedState == FEED_QUEUING); /* a tile read in flight */
    tfsBusy = 0; feedMenuRead = 1; step(); assert(queued == 1 && feedState == FEED_LOADING && feedMenuRead == 0);
    for (int i = 0; i < 5; i++) { step(); assert(!shown && feedState == FEED_LOADING); } /* the field keeps going */
    *readFlag = 1; step(); assert(shown == 1 && feedState == FEED_OPENING && queued == 1);
    puts("care menu reads MENU in the background and opens once it landed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='care-read-host-') as temp:
        source = Path(temp) / 'care.c'
        exe = Path(temp) / 'care'
        source.write_text(prefix + open_fn + harness + tests)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
