#!/usr/bin/env python3
"""Compile the real care entry on the host; no disc assets needed.

Run after preparing a patched tree: python3 tools/dev/playtest/quick_care_host.py build/decomp-dev
Tests entry ownership and guards in both control layouts.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def function(source, signature):
    a = source.index(signature)
    start = source.index('{', a)
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[a:end]


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-dev')
    feed = (root / 'src/main/mod_feed.c').read_text()
    prefix = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define FEED_LIST_BOX 0
#define FEED_DESC_BOX 1
#define PARTNER_NORMAL 1
#define ITEM_NONE -1
#define FEED_OBJECT_ID 0x1f9b
static int32_t GAME_STATE, IS_IN_MENU, TAMER_STATE, IS_SCRIPT_PAUSED=1, FADE_PROTECTION;
static int32_t PARTNER_STATE=1, MOD_FEED_HINT, CHANGED_INPUT, CONFIRM_BUTTON;
static struct { int state, frame; } UI_BOX_DATA[2];
static struct { struct { int type; } worldItem; } TAMER_ITEM = {{-1}};
static int count=1, opened, objects;
static int feedCollect(void) { return count; }
static int feedOpen(void) { opened++; return 1; }
static void feedTick(int id) { (void)id; }
static void addObject(int id, int n, void (*tick)(int), void *render) {
    assert(id==FEED_OBJECT_ID && n==0 && tick==feedTick && render==0); objects++;
}
'''
    tests = r'''
static void entry(void) {
    for(int jp=0;jp<2;jp++) {
        CONFIRM_BUTTON=jp?0x20:0x40;
        CHANGED_INPUT=CONFIRM_BUTTON; assert(!modFeedTick() && !opened);
        CHANGED_INPUT=0x80; assert(modFeedTick() && opened==1 && objects==1);
        opened=objects=0; CHANGED_INPUT=CONFIRM_BUTTON|0x80; assert(!modFeedTick() && !opened);
        CHANGED_INPUT=0; assert(!modFeedTick() && !opened);
        CHANGED_INPUT=0x80;
        int32_t *guards[]={&GAME_STATE,&IS_IN_MENU,&TAMER_STATE,&FADE_PROTECTION};
        for(unsigned i=0;i<sizeof(guards)/sizeof(guards[0]);i++) {
            *guards[i]=1; MOD_FEED_HINT=0; assert(!modFeedTick() && !MOD_FEED_HINT); *guards[i]=0;
        }
        IS_SCRIPT_PAUSED=0;assert(!modFeedTick());IS_SCRIPT_PAUSED=1;
        PARTNER_STATE=5;assert(!modFeedTick());PARTNER_STATE=1;
        count=0;assert(!modFeedTick());count=1;
        TAMER_ITEM.worldItem.type=3;assert(!modFeedTick());TAMER_ITEM.worldItem.type=-1;
        for(int box=0;box<2;box++) {
            UI_BOX_DATA[box].state=1;assert(!modFeedTick());UI_BOX_DATA[box].state=0;
            UI_BOX_DATA[box].frame=1;assert(!modFeedTick());UI_BOX_DATA[box].frame=0;
        }
    }
}
int main(void) { entry();puts("care entry guards and control-layout ownership passed"); }
'''
    with tempfile.TemporaryDirectory(prefix='care-host-') as temp:
        source = Path(temp) / 'care.c'
        exe = Path(temp) / 'care'
        source.write_text(prefix + function(feed, 'int32_t modFeedTick(void)') + tests)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
