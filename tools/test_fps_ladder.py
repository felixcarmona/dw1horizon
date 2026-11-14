#!/usr/bin/env python3
"""Compile the applied cadence ladder (main.c) natively and replay tick costs through it.

Scenes are given as (tick + first pass, extra pass) line costs, as the ladder records them; the shown frames of a
tick follow the same refresh arithmetic the present helper uses. The ladder's whole block (its constants, globals,
state and functions) is taken from the source as it is. Checks: a screen is entered at steady 30 (or at 60 where 60
held before), 60 is reached only after a long run of ticks with room to spare and only at the end of a steady pair,
the first missed frame at 60 drops to steady 30 and 60 is never tried there again, steady 30 drops to 20 only on a
full window of late frames, the level never flaps, the world and the battle loops keep separate facts, and fast
ticks, the test tick length, curling, pause frames and the locked policies leave it alone."""
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def ladder_block(source):
    """The ladder as shipped: from its first constant to the end of modCadRecord."""
    start = source.index('#define MOD_CAD_WINDOW')
    record = re.search(r'^static void modCadRecord\(', source[start:], re.M)
    assert record, 'modCadRecord not found: update this test'
    end = source.index('\n}\n', start + record.start()) + 3
    return source[start:end]


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-int')
    source = (work / 'src/main/main.c').read_text()
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <stddef.h>
#define MOD_FPS_POLICY_AUTO 0
#define MOD_FPS_POLICY_60 1
#define MOD_FPS_POLICY_30 2
#define MOD_FPS_POLICY_20 3
#define MOD_FPS_POLICY_CPU 4
#define MOD_PRESENT_BATTLE 1
#define MOD_PRESENT_PAUSE 2
int32_t MOD_FPS_MODE_RUN = 2;
#define MOD_FPS_MODE MOD_FPS_MODE_RUN
int32_t MOD_RENDER_CADENCE, MOD_FPS_TICKS, MOD_INTERP_MAP_GEN = 1;
int16_t CURRENT_SCREEN = 168;
''' + ladder_block(source) + r'''
#define MARGIN 12 /* the helper: a pass must end this far before the vblank it is shown at */
/* the frames 60 shows for a tick of these costs: the first pass at the vblank after it ends, each extra pass from
 * the swap of the one before, inside the tick */
static int shown60(int c0, int cx) {
    int frames = 1, end = c0 + MARGIN, s = end > 2 * MOD_CAD_LINES ? 3 : end > MOD_CAD_LINES ? 2 : 1;
    if (end > 3 * MOD_CAD_LINES) return 1;
    while (s < 3) {
        end = s * MOD_CAD_LINES + cx + MARGIN;
        if (end > 3 * MOD_CAD_LINES) break;
        s = end > 2 * MOD_CAD_LINES ? 3 : 2;
        frames++;
    }
    return frames;
}
static int ups, flaps, lastLevel = -9;
/* one tick of a scene whose costs are c0 (tick + first pass) and cx (extra pass): frames as the helper shows them.
 * Returns the cadence the tick rendered with (2 = 60, 1 = a steady pair half, 0 = one frame at 3/3) */
static int tick(int flags, int c0, int cx) {
    int armed, level, planned, shown, late = 0;
    MOD_RENDER_CADENCE = 0;
    armed = modCadArm(flags, 3, 0);
    level = armed < 0 ? 2 : armed;
    MOD_FPS_TICKS++;
    if (level == 2) {
        planned = 3; shown = shown60(c0, cx);
        late = c0 + MARGIN > MOD_CAD_LINES;
    } else if (level == 1) {
        int early = (MOD_RENDER_CADENCE & 3) == 2;
        planned = early ? 1 : 2; shown = planned;
        late = c0 + MARGIN > 2 * MOD_CAD_LINES;
        if (!early && (late ? 3 : 2) * MOD_CAD_LINES + cx + MARGIN > 4 * MOD_CAD_LINES) shown = 1;
    } else {
        planned = 1; shown = 1;
    }
    if (armed >= 0) modCadRecord(planned, shown, late, c0, cx);
    if (!(flags & MOD_PRESENT_PAUSE)) {
        if (lastLevel == 1 && MOD_CAD_LEVEL == 2) ups++;
        if (lastLevel == 2 && MOD_CAD_LEVEL == 1) flaps++;
        lastLevel = MOD_CAD_LEVEL;
    }
    return level;
}
/* a tick that is a pair's late half or one at 60 shows no frame two refreshes after one at one refresh */
static void enter(int screen) { CURRENT_SCREEN = screen; MOD_INTERP_MAP_GEN++; }
static void fresh(void) {
    MOD_CAD_RESET = 1; MOD_FPS_POLICY = 0; MOD_FPS_MODE_RUN = 2; MOD_FPS_TICKS = 0; MOD_CAD_KEEP30 = 4;
    ups = flaps = 0; lastLevel = -9; MOD_INTERP_MAP_GEN = 1; CURRENT_SCREEN = 168;
}
static uint16_t fact(int screen, int battle) {
    uint16_t *f = modCadFact((screen & 0x3FF) | battle << 10, 0);
    return f ? *f : 0;
}
int main(void) {
    int i, sw, level;
    unsigned seed = 1;
    /* as shipped: a quarter of a refresh to spare and 6.4 s of such ticks before a climb */
    assert(MOD_CAD_UP >= 48 && MOD_CAD_CLIMB >= 96 && MOD_CAD_LEVEL == 1);

    /* an unknown screen is entered at steady 30: an odd first tick shows one frame at 3/3, never a tick at 60 */
    fresh(); MOD_FPS_TICKS = 1;
    assert(tick(0, 237, 182) == 0 && MOD_RENDER_CADENCE == 16 && MOD_CAD_LEVEL == 1);
    assert(tick(0, 237, 182) == 1 && MOD_RENDER_CADENCE == (8 | 2));
    assert(tick(0, 237, 182) == 1 && MOD_RENDER_CADENCE == (8 | 1));
    /* File City (2.3 of 3 frames at 60 at the stock clock): steady 30 for good, no switch */
    for (i = 0; i < 3000; i++) assert(tick(0, 237, 182) == 1);
    assert(MOD_CAD_SWITCHES == 0);
    /* Gear Savanna, Toy Town standing with its spikes (p50 195, p90 202, max 260), a tournament: never 60 */
    fresh();
    for (i = 0; i < 3000; i++) assert(tick(0, 306, 218) == 1);
    fresh();
    for (i = 0; i < 3000; i++) assert(tick(0, (i % 10) == 9 ? 260 : (i % 3) ? 195 : 202, 150) == 1);
    fresh();
    for (i = 0; i < 3000; i++) assert(tick(MOD_PRESENT_BATTLE, 366, 340) == 1);
    assert(MOD_CAD_SWITCHES == 0);

    /* a light screen climbs to 60 once, after MOD_CAD_CLIMB clean ticks, at the end of a pair; then holds */
    fresh();
    for (i = 0; i < MOD_CAD_CLIMB - 1; i++) assert(tick(0, 150, 110) == 1 && MOD_CAD_LEVEL == 1);
    for (i = 0; MOD_CAD_LEVEL == 1; i++) tick(0, 150, 110);
    assert(i <= 2 && MOD_CAD_SWITCHES == 1);
    assert(MOD_RENDER_CADENCE == (8 | 1)); /* decided on a pair's late half: no odd interval */
    for (i = 0; i < 3000; i++) assert(tick(0, 150, 110) == 2);
    assert(MOD_CAD_SWITCHES == 1 && (fact(168, 0) & MOD_CAD_GOOD));
    /* one heavy tick in the clean run starts the count again */
    fresh();
    for (i = 0; i < MOD_CAD_CLIMB - 10; i++) tick(0, 150, 110);
    tick(0, 263 - MOD_CAD_UP + 1, 110);
    for (i = 0; i < MOD_CAD_CLIMB - 2; i++) assert(tick(0, 150, 110) == 1);
    for (i = 0; i < 4; i++) tick(0, 150, 110);
    assert(MOD_CAD_LEVEL == 2);
    /* the same for the extra pass */
    fresh();
    for (i = 0; i < 3000; i++) assert(tick(0, 150, 263 - MOD_CAD_UP + 1) == 1);

    /* a screen where 60 held is entered at 60 again; a battle there still starts at steady 30 */
    fresh();
    for (i = 0; i < 400; i++) tick(0, 150, 110);
    assert(MOD_CAD_LEVEL == 2);
    enter(169);
    for (i = 0; i < 64; i++) tick(0, 300, 250);
    assert(MOD_CAD_LEVEL == 1);
    enter(168);
    assert(tick(0, 150, 110) == 2 && MOD_CAD_LEVEL == 2);
    MOD_FPS_TICKS |= 1; /* an odd tick: one frame at 3/3, as at any entry */
    assert(tick(MOD_PRESENT_BATTLE, 150, 110) == 0 && MOD_CAD_LEVEL == 1);
    assert(tick(MOD_PRESENT_BATTLE, 150, 110) == 1);
    assert(tick(0, 150, 110) == 2); /* back in the world: 60 */

    /* the first missed frame at 60 drops at once, the screen is marked, and 60 is never tried there again */
    fresh();
    for (i = 0; i < 400; i++) tick(0, 150, 110);
    assert(MOD_CAD_LEVEL == 2 && MOD_CAD_SWITCHES == 1);
    MOD_FPS_TICKS &= ~1;
    tick(0, 300, 110); /* the first pass ends after the vblank of 1/3: one frame of two refreshes */
    assert(MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == 2);
    assert((fact(168, 0) & MOD_CAD_FAIL60) && !(fact(168, 0) & MOD_CAD_GOOD));
    assert(tick(0, 150, 110) == 2); /* from 60, an odd tick aligns at 60 once (not a frame at 3/3) */
    for (i = 0; i < 6000; i++) assert(tick(0, 150, 110) == 1);
    enter(1); tick(0, 150, 110); enter(168);
    for (i = 0; i < 6000; i++) assert(tick(0, 150, 110) <= 1);
    assert(MOD_CAD_LEVEL == 1);
    /* a skipped extra pass counts the same */
    fresh();
    for (i = 0; i < 400; i++) tick(0, 150, 110);
    tick(0, 150, 263);
    assert(MOD_CAD_LEVEL == 1 && (fact(168, 0) & MOD_CAD_FAIL60));

    /* steady 30 drops to 20 only on a full window with more than KEEP30 late or skipped frames, once */
    fresh();
    for (i = 0; i < 31; i++) assert(tick(0, 700, 600) <= 1 && MOD_CAD_LEVEL == 1);
    for (i = 0; i < 3; i++) tick(0, 700, 600);
    assert(MOD_CAD_LEVEL == 0 && MOD_CAD_SWITCHES == 1 && (fact(168, 0) & MOD_CAD_FAIL20));
    for (i = 0; i < 3000; i++) assert(tick(0, 700, 600) == 0 && MOD_RENDER_CADENCE == 16);
    assert(MOD_CAD_SWITCHES == 1);
    /* that world screen is entered at 20 next time; it climbs to steady 30 only after a clean run with room */
    enter(2); tick(0, 150, 110); enter(168);
    assert(tick(0, 700, 600) == 0 && MOD_CAD_LEVEL == 0);
    sw = MOD_CAD_SWITCHES;
    for (i = 0; i < MOD_CAD_CLIMB - 1; i++) assert(tick(0, 400, 380) == 0);
    tick(0, 400, 380);
    assert(MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == sw + 1);
    for (i = 0; i < 2 * MOD_CAD_WINDOW + 4; i++) tick(0, 400, 380);
    assert(!(fact(168, 0) & MOD_CAD_FAIL20)); /* the climb held: entered at steady 30 again */
    /* a climb from 20 that fails waits twice as long before the next */
    fresh();
    for (i = 0; i < 40; i++) tick(0, 700, 600);
    assert(MOD_CAD_LEVEL == 0);
    for (i = 0; i < MOD_CAD_CLIMB + 2; i++) tick(0, 400, 380);
    assert(MOD_CAD_LEVEL == 1);
    for (i = 0; i < 40; i++) tick(0, 700, 600);
    assert(MOD_CAD_LEVEL == 0 && modCad.cool[0] == 2 * MOD_CAD_WINDOW);

    /* a battle at steady 30 with three lone overruns stays; one that overruns every fourth tick goes to 20 only
     * once the window is full, and the next battle on that screen starts at steady 30 again */
    fresh();
    for (i = 0; i < 600; i++) assert(tick(MOD_PRESENT_BATTLE, (i == 3 || i == 7 || i == 12) ? 560 : 330, 240) <= 1);
    assert(MOD_CAD_SWITCHES == 0);
    fresh();
    for (i = 0; i < 31; i++) assert(tick(MOD_PRESENT_BATTLE, (i % 4) == 3 ? 560 : 330, 240) <= 1);
    for (i = 0; i < 40; i++) tick(MOD_PRESENT_BATTLE, (i % 4) == 3 ? 560 : 330, 240);
    assert(MOD_CAD_LEVEL == 0 && MOD_CAD_SWITCHES == 1 && !(fact(168, 1) & MOD_CAD_FAIL20));
    tick(0, 237, 182);
    MOD_FPS_TICKS &= ~1;
    assert(tick(MOD_PRESENT_BATTLE, 330, 240) == 1);

    /* no flapping: a screen whose costs wander around every threshold climbs to 60 at most once in ten minutes */
    for (level = 0; level < 4; level++) {
        fresh();
        for (i = 0; i < 12000; i++) {
            int c0, cx;
            seed = seed * 1103515245u + 12345u;
            c0 = 120 + (seed >> 16) % (level == 0 ? 90 : level == 1 ? 160 : level == 2 ? 300 : 500);
            cx = c0 * 3 / 4;
            if (level == 0 && i > 6000 && i % 700 == 0) c0 = 300; /* rare spikes on a light screen */
            tick(0, c0, cx);
        }
        assert(ups <= 1 && flaps <= 1 && MOD_CAD_SWITCHES <= 3);
    }

    /* pause frames render with the current level and change nothing */
    fresh();
    for (i = 0; i < 64; i++) tick(0, 700, 600);
    assert(MOD_CAD_LEVEL == 0);
    for (i = 0; i < 64; i++) assert(tick(MOD_PRESENT_PAUSE, 150, 110) == 0);
    for (i = 0; i < 64; i++) { MOD_RENDER_CADENCE = 0; modCadArm(MOD_PRESENT_PAUSE | MOD_PRESENT_BATTLE, 3, 0); }
    assert(modCad.ctx == 0 && MOD_CAD_SWITCHES == 1);
    /* the same screen set up again keeps its level (new evidence) */
    MOD_INTERP_MAP_GEN++;
    assert(tick(0, 700, 600) == 0 && modCad.count == 1);

    /* a failed 60 outlives a long session: the table replaces other screens first */
    fresh();
    for (i = 0; i < 400; i++) tick(0, 150, 110);
    tick(0, 300, 110);
    assert(fact(168, 0) & MOD_CAD_FAIL60);
    for (sw = 0; sw < 3 * MOD_CAD_FACTS; sw++) {
        enter(200 + sw);
        for (i = 0; i < 2 * MOD_CAD_CLIMB; i++) tick(0, 150, 110);
    }
    assert(fact(168, 0) & MOD_CAD_FAIL60);
    enter(168);
    for (i = 0; i < 3000; i++) assert(tick(0, 150, 110) <= 1);
    /* the tools' reset forgets every fact */
    MOD_CAD_RESET = 1; tick(0, 150, 110);
    assert(!fact(168, 0) && MOD_CAD_LEVEL == 1 && MOD_CAD_SWITCHES == 0);
    /* before any map is loaded (the title) nothing is remembered: the screen id is a placeholder */
    fresh(); MOD_INTERP_MAP_GEN = 0; CURRENT_SCREEN = 0xCC;
    for (i = 0; i < 400; i++) tick(0, 150, 110);
    assert(MOD_CAD_LEVEL == 2 && !fact(0xCC, 0));

    /* the helper's own cases: fast ticks, the test tick length, curling's cadence, mode 0 */
    MOD_RENDER_CADENCE = 0; assert(modCadArm(MOD_PRESENT_BATTLE, 2, 0) == -1 && MOD_RENDER_CADENCE == 0);
    MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 1) == -1);
    MOD_RENDER_CADENCE = 4; assert(modCadArm(0, 3, 0) == -1 && MOD_RENDER_CADENCE == 4);
    MOD_FPS_MODE_RUN = 0; MOD_RENDER_CADENCE = 0; assert(modCadArm(0, 3, 0) == -1); MOD_FPS_MODE_RUN = 2;
    /* locks: 60, steady 30, 20 and the CPU probe's mode; evidence is recorded but never acts */
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_60;
    for (i = 0; i < 400; i++) assert(tick(0, 700, 600) == 2);
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_30;
    for (i = 0; i < 400; i++) assert(tick(0, 150, 110) >= 0 && MOD_CAD_LEVEL == 1);
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_20;
    for (i = 0; i < 400; i++) assert(tick(0, 150, 110) == 0 && MOD_RENDER_CADENCE == 16);
    fresh(); MOD_FPS_POLICY = MOD_FPS_POLICY_CPU;
    for (i = 0; i < 400; i++) assert(tick(0, 700, 600) == 2);
    assert(MOD_CAD_SWITCHES == 0);
    puts("PASS: ladder entry levels, climb only with room, no second 60 try, 20 on a full window, no flapping");
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
    fast_pair_cadence(source)


def fast_pair_cadence(source):
    """Battle x2: modTickStart's due rule, replayed over a fast pair's refresh arithmetic (the shown tick's frame at
    its due refresh, the thrown-away tick waits for none). Whatever the two ticks cost, as long as the pair fits its 3
    refreshes, every frame comes 3 refreshes after the last one; a quick thrown-away tick must not pull the next frame
    a refresh early."""
    rule = re.search(r'modTickV = (\(now >= modFastDue[^;]*\)) \? modFastDue : now;', source)
    assert rule, 'modTickStart fast due rule changed: update this test'
    code = r'''
#include <assert.h>
#include <stdint.h>
static int32_t due_of(int32_t now, int32_t modFastDue) { return %s ? modFastDue : now; }
int main(void) {
    int c1, c2, k;
    for (c1 = 20; c1 <= 500; c1 += 7) for (c2 = 5; c2 <= 760 - c1; c2 += 11) {
        int32_t t = 263 * 100 + 40, due = 100, last = -1, real = 1;
        for (k = 0; k < 60; k++) {
            int32_t now = t / 263, tickV = due_of(now, due), period = real ? 2 : 1;
            due = tickV + period;
            t += real ? c1 : c2;
            if (real) {
                if (t < due * 263) t = due * 263; /* shown at its due refresh */
                if (last >= 0 && k > 4) assert(due - last == 3);
                last = due;
            }
            real ^= 1;
        }
    }
    return 0;
}
''' % rule.group(1)
    compile_check(code)
    print('PASS: battle x2 frames 3 refreshes apart for every pair that fits')


if __name__ == '__main__':
    main()
