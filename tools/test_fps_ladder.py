#!/usr/bin/env python3
"""Compile the applied cadence ladder (main.c) natively and replay tick costs through it.

Scenes are given as (tick + first pass, extra pass) line costs, as the ladder records them; the shown frames of a
tick follow the same refresh arithmetic the present helper uses. Checks: the level each cost profile settles at, how
fast it drops, that it never flaps within a scene, that a failing trial waits longer each time, that the world and
the battle loops remember their levels, and that fast ticks, the test tick length, curling and the locked policies
leave it alone."""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-int')
    source = (work / 'src/main/main.c').read_text()
    # the shipped defaults: the 60 threshold and the levels the world and the battle loops start at
    keep60 = int(re.search(r'int8_t MOD_CAD_KEEP60 = (\d+);', source).group(1))
    start = re.search(r'modCad = \{ \{ 0 \}, 0, 0, \{ MOD_CAD_WINDOW, MOD_CAD_WINDOW \}, 0, 0, -1, -1, 0, \{ (\d), (\d) \} \};', source)
    assert start, 'modCad initializer changed: update this test'
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define MOD_CAD_WINDOW 32
#define KEEP60_DEFAULT %d
#define START_WORLD %s
#define START_BATTLE %s
#define MOD_CAD_LINES 263
#define MOD_CAD_MARGIN 12
#define MOD_FPS_POLICY_AUTO 0
#define MOD_FPS_POLICY_60 1
#define MOD_FPS_POLICY_30 2
#define MOD_FPS_POLICY_20 3
#define MOD_FPS_POLICY_CPU 4
#define MOD_PRESENT_BATTLE 1
#define MOD_PRESENT_PAUSE 2
int32_t MOD_FPS_MODE_RUN = 2;
#define MOD_FPS_MODE MOD_FPS_MODE_RUN
int32_t MOD_RENDER_CADENCE, MOD_FPS_TICKS, MOD_INTERP_MAP_GEN;
static int32_t modPassSetupLines = 40;
int8_t MOD_FPS_POLICY;
int8_t MOD_CAD_LEVEL = 2;
int8_t MOD_CAD_KEEP60 = KEEP60_DEFAULT;
int8_t MOD_CAD_KEEP30 = 4;
int32_t MOD_CAD_SWITCHES;
int32_t MOD_CAD_LAST;
static struct {
	uint32_t ring[MOD_CAD_WINDOW];
	int32_t mapGen;
	int16_t since;
	int16_t cool[2];
	int8_t count, pos, ctx, prev, up;
	int8_t ctxLevel[2];
} modCad = { { 0 }, 0, 0, { MOD_CAD_WINDOW, MOD_CAD_WINDOW }, 0, 0, -1, -1, 0, { START_WORLD, START_BATTLE } };
'''
    code = code.replace('%d', str(keep60), 1).replace('%s', start.group(1), 1).replace('%s', start.group(2), 1)
    for name in ('modCadPredict60', 'modCadArm', 'modCadRecord'):
        code += '\n' + function(source, name)
    code += r'''
/* one tick of a scene whose costs are c0 (tick + first pass) and cx (extra pass): frames as the helper would show */
static int tick(int flags, int c0, int cx, int shownOverride) {
    int level, armed, planned, shown, late = 0, due, end, s;
    MOD_RENDER_CADENCE = 0;
    armed = modCadArm(flags, 3, 0);
    level = armed < 0 ? 2 : armed;
    if (level == 2) {
        planned = 3; shown = shownOverride >= 0 ? shownOverride : modCadPredict60(c0, cx);
        if (c0 + MOD_CAD_MARGIN > MOD_CAD_LINES) late = 1;
    } else if (level == 1) {
        int early = (MOD_RENDER_CADENCE & 3) == 2;
        planned = early ? 1 : 2; shown = planned;
        due = early ? 2 * MOD_CAD_LINES : 2 * MOD_CAD_LINES; /* the first frame has two refreshes in both halves */
        if (c0 + MOD_CAD_MARGIN > due) late++;
        if (!early) { s = c0 + MOD_CAD_MARGIN > due ? 3 : 2; end = s * MOD_CAD_LINES + cx; if (end + MOD_CAD_MARGIN > 4 * MOD_CAD_LINES) shown = 1; }
    } else {
        planned = 1; shown = 1;
    }
    MOD_FPS_TICKS++;
    if (armed >= 0) modCadRecord(planned, shown, late, c0, cx);
    return level;
}
static void fresh(void) {
    MOD_CAD_LEVEL = 2; modCad.count = modCad.pos = 0; modCad.ctx = -1; modCad.prev = -1; modCad.up = 0;
    modCad.ctxLevel[0] = modCad.ctxLevel[1] = 2; modCad.since = 0; modCad.cool[0] = modCad.cool[1] = MOD_CAD_WINDOW;
    MOD_CAD_SWITCHES = 0; MOD_FPS_POLICY = 0; MOD_FPS_MODE_RUN = 2; MOD_FPS_TICKS = 0;
}
int main(void) {
    int i, sw;
    /* as shipped: the world starts at 60, a battle at steady 30 (no battle fits 60 at the stock clock: its first
     * pass alone costs about a refresh), and 60 is kept only while nearly every frame of it is shown */
    assert(START_WORLD == 2 && START_BATTLE == 1 && KEEP60_DEFAULT >= 88 && KEEP60_DEFAULT + 4 <= 96);
    MOD_RENDER_CADENCE = 0; MOD_FPS_TICKS = 0;
    assert(modCadArm(MOD_PRESENT_BATTLE, 3, 0) == 1 && MOD_CAD_LEVEL == 1); /* the first battle: no 60 trial */
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == 2);              /* the world, back at its own level */
    /* File City (2.3 of 3 frames shown) and Gear Savanna (1,2,1,2): mixed intervals, so steady 30 by default.
     * File City's line costs predict 60 (the failed-try waits below bound how often it is tried again) */
    fresh();
    for (i = 0; i < 16; i++) tick(0, 237, 182, (i % 10) < 3 ? 3 : 2);
    assert(MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == 1);
    fresh();
    for (i = 0; i < 1200; i++) tick(0, 306, 218, -1);
    assert(MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == 1);
    MOD_CAD_KEEP60 = 60; /* the cases below were measured against the old threshold */
    /* the frames 60 could show: light, File City, Gear Savanna, a tournament (measured profiles) */
    assert(modCadPredict60(150, 110) == 3);
    assert(modCadPredict60(237, 182) == 3);
    assert(modCadPredict60(306, 218) == 2);
    assert(modCadPredict60(366, 340) == 1);
    assert(modCadPredict60(240, 300) == 2); /* the second frame lands on refresh 3, no third */
    /* a light scene stays at 60 */
    fresh();
    for (i = 0; i < 2000; i++) assert(tick(0, 150, 110, -1) == 2);
    assert(MOD_CAD_SWITCHES == 0);
    /* a tournament's costs: down to steady 30 after 16 ticks, then no change in a minute */
    fresh();
    for (i = 0; i < 16; i++) assert(tick(MOD_PRESENT_BATTLE, 366, 340, -1) == 2);
    assert(MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == 1);
    for (i = 0; i < 1200; i++) assert(tick(MOD_PRESENT_BATTLE, 366, 340, -1) == 1);
    assert(MOD_CAD_SWITCHES == 1 && MOD_RENDER_CADENCE == (8 | ((MOD_FPS_TICKS - 1) & 1 ? 1 : 2)));
    /* a scene too heavy for steady 30 goes to 20 and stays */
    fresh();
    for (i = 0; i < 16; i++) tick(0, 700, 600, -1);
    assert(MOD_CAD_LEVEL == 0 && MOD_CAD_SWITCHES == 1);
    for (i = 0; i < 1200; i++) assert(tick(0, 700, 600, -1) == 0 && MOD_RENDER_CADENCE == 16);
    assert(MOD_CAD_SWITCHES == 1);
    /* File City: three frames predicted, 2.3 shown on average: stays at 60 (above KEEP60 = 1.875 a tick) */
    fresh();
    for (i = 0; i < 1200; i++) assert(tick(0, 237, 182, (i % 10) < 3 ? 3 : 2) == 2);
    assert(MOD_CAD_SWITCHES == 0);
    /* Gear Savanna: two frames a tick (the 1,2,1,2 pattern) stays at 60 by the default threshold... */
    fresh();
    for (i = 0; i < 1200; i++) assert(tick(0, 306, 218, -1) == 2);
    assert(MOD_CAD_SWITCHES == 0);
    /* ...and with KEEP60 raised to 2.5 frames a tick (80) it is steady 30 instead, settled once */
    fresh(); MOD_CAD_KEEP60 = 80;
    for (i = 0; i < 1200; i++) tick(0, 306, 218, -1);
    assert(MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == 1);
    MOD_CAD_KEEP60 = 60;
    /* an emulator whose frames at 60 do not follow its line counts (predicted 3, shown 1): every failed try
     * doubles the wait before the next, up to 1024 ticks (51 s), so in five minutes of such a scene the ladder
     * tries 60 fewer than ten times, 16 ticks each */
    fresh();
    for (i = 0; i < 6000; i++) { tick(0, 240, 180, 1); }
    assert(MOD_CAD_SWITCHES <= 20 && modCad.cool[0] == 1024);
    sw = MOD_CAD_SWITCHES;
    for (i = 0; i < 2048; i++) tick(0, 240, 180, 1);
    assert(MOD_CAD_SWITCHES - sw <= 4); /* at most once up and down per 1024 ticks */
    /* the world and the battle loops remember their levels */
    fresh();
    for (i = 0; i < 64; i++) tick(0, 150, 110, -1);
    for (i = 0; i < 64; i++) tick(MOD_PRESENT_BATTLE, 366, 340, -1);
    assert(MOD_CAD_LEVEL == 1);
    assert(tick(0, 150, 110, -1) == 2);
    assert(tick(MOD_PRESENT_BATTLE, 366, 340, -1) == 1 || MOD_CAD_LEVEL == 1);
    /* pause frames render with the current level and change nothing */
    fresh();
    for (i = 0; i < 64; i++) tick(0, 366, 340, -1);
    assert(MOD_CAD_LEVEL == 1);
    for (i = 0; i < 64; i++) { MOD_RENDER_CADENCE = 0; assert(modCadArm(MOD_PRESENT_PAUSE, 3, 0) == 1); }
    assert(modCad.ctx == 0 && MOD_CAD_SWITCHES == 1);
    /* a map change clears the evidence and the wait, keeps the level */
    MOD_INTERP_MAP_GEN++;
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == 1 && modCad.count == 0 && modCad.cool[0] == MOD_CAD_WINDOW);
    /* after it, a light map steps up after one full window */
    for (i = 0; i < 40; i++) tick(0, 150, 110, -1);
    assert(MOD_CAD_LEVEL == 2 && MOD_CAD_SWITCHES == 2);
    /* the helper's own cases: fast ticks, the test tick length, curling's cadence, mode 0 */
    MOD_RENDER_CADENCE = 0; assert(modCadArm(MOD_PRESENT_BATTLE, 2, 0) == -1 && MOD_RENDER_CADENCE == 0);
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 1) == -1);
    MOD_RENDER_CADENCE = 4; assert(modCadArm(0, 3, 0) == -1 && MOD_RENDER_CADENCE == 4);
    MOD_FPS_MODE_RUN = 0; MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == -1); MOD_FPS_MODE_RUN = 2;
    /* the steady pair starts on an even tick: an odd first tick renders at 60 once */
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_30; MOD_FPS_TICKS = 1;
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == -1); MOD_FPS_TICKS++;
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == 1 && MOD_RENDER_CADENCE == (8 | 2)); MOD_FPS_TICKS++;
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == 1 && MOD_RENDER_CADENCE == (8 | 1));
    /* An odd entry into steady 30 must not charge its alignment tick as a failed 30 frame. */
    fresh(); MOD_CAD_LEVEL=1; modCad.ctxLevel[0]=1; MOD_FPS_TICKS=1;
    assert(tick(0,366,340,-1)==2 && modCad.count==0);
    for(i=0;i<120;i++) assert(tick(0,366,340,-1)==1);
    assert(MOD_CAD_LEVEL==1 && MOD_CAD_SWITCHES==0);
    /* locks: 60, 20, and the CPU probe's mode; evidence is recorded but never acts */
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_60;
    for (i = 0; i < 200; i++) assert(tick(0, 700, 600, -1) == 2);
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_20;
    for (i = 0; i < 200; i++) assert(tick(0, 150, 110, -1) == 0 && MOD_RENDER_CADENCE == 16);
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_CPU;
    for (i = 0; i < 200; i++) assert(tick(0, 700, 600, -1) == 2);
    assert(MOD_CAD_SWITCHES == 0);
    puts("PASS: ladder levels, drop speed, no flapping, failed-try waits, context memory, locks");
    return 0;
}
'''
    compile_check(code)
    # Both curling entry points must stay in its loaded overlay. World 30/20 use bits 8/16.
    replay = function(source, 'modReplayTickPrims')
    present = function(source, 'modPresent')
    code = r'''
#include <stdint.h>
#include <assert.h>
int32_t MOD_RENDER_CADENCE, MOD_TICK_PRIM_MAIN_MENU, MOD_TICK_PRIM_MERAMON;
int curling, menu, meramon;
void KAR_replayTickPrims(void) { curling++; }
void modReplayMainMenu(void) { menu++; }
void addMeramonShakePrim(void) { meramon++; }
''' + replay + r'''
int main(void) {
    int before;
    MOD_TICK_PRIM_MAIN_MENU = MOD_TICK_PRIM_MERAMON = 1;
    for (MOD_RENDER_CADENCE=0; MOD_RENDER_CADENCE<=18; MOD_RENDER_CADENCE++) {
        before = curling;
        modReplayTickPrims();
        assert(curling-before == (MOD_RENDER_CADENCE!=0 && !(MOD_RENDER_CADENCE & 0x18)));
    }
    assert(menu==19 && meramon==19);
}
'''
    compile_check(code)
    assert 'if (MOD_RENDER_CADENCE && !(MOD_RENDER_CADENCE & 0x18))' in present
    print('PASS: ladder cadences never call curling overlay helpers')


if __name__ == '__main__':
    main()
