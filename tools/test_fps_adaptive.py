#!/usr/bin/env python3
"""Exercise the actual experimental feedback controller with synthetic deadlines."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-int')
    source = (work / 'src/main/main.c').read_text()
    state = source[source.index('int32_t MOD_ADAPT_POLICY;'):source.index('static void modAdaptiveBegin')]
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define MOD_PRESENT_BATTLE 1
#define MOD_PRESENT_PAUSE 2
#define MOD_CPU_SPINS_FAST 8500
uint32_t refresh, MOD_INTERP_MAP_GEN;
int32_t GAME_STATE, MOD_FPS_MODE_RUN=2, MOD_LOAD_PUMP, MOD_TICK_FAST;
int32_t MOD_FPS_TEST_TICK, MOD_RENDER_CADENCE, modTickV;
int32_t VSync(int unused) { return refresh; }
int32_t modCpuProbe(void) { return 3801; }
''' + state + function(source, 'modAdaptiveBegin') + function(source, 'modAdaptiveEnd') + r'''
static void tick(int flips, int late, int flags) {
    modTickV=refresh; modAdaptiveBegin(flags); refresh+=3;
    modAdaptiveEnd(flags,flips,late);
}
static void ticks(int count, int flips, int late, int flags) {
    for(int i=0;i<count;i++) tick(flips,late,flags);
}
int main(void) {
    /* Even 60 stays at 60 regardless of a standard-speed CPU probe. */
    ticks(2400,3,0,0); assert(MOD_FPS_MODE_RUN==2 && MOD_ADAPT_SWITCHES==0);
    /* One bad window and one clean window never trigger a drop. */
    MOD_INTERP_MAP_GEN++; ticks(30,3,0,0);
    ticks(40,1,0,0); ticks(40,3,0,0);
    assert(MOD_FPS_MODE_RUN==2);
    ticks(80,3,1,0); assert(MOD_FPS_MODE_RUN==0 && MOD_ADAPT_SWITCHES==1);
    /* Time alone never retries; neither does a boundary before cooldown. */
    MOD_INTERP_MAP_GEN++; tick(1,0,0); assert(MOD_FPS_MODE_RUN==0);
    ticks(1200,1,0,0); assert(MOD_FPS_MODE_RUN==0);
    MOD_INTERP_MAP_GEN++; tick(3,0,0);
    assert(MOD_FPS_MODE_RUN==2 && MOD_ADAPT_SWITCHES==2);
    ticks(109,1,0,0); assert(MOD_FPS_MODE_RUN==0 && MOD_ADAPT_SWITCHES==3);
    /* Load/pause/curling/x2/forced samples reset the evidence. */
    MOD_ADAPT_POLICY=2; tick(3,0,0); MOD_ADAPT_POLICY=0;
    MOD_LOAD_PUMP=1; ticks(200,1,1,0); MOD_LOAD_PUMP=0;
    ticks(200,1,1,MOD_PRESENT_PAUSE);
    MOD_TICK_FAST=1; ticks(200,1,1,0); MOD_TICK_FAST=0;
    MOD_FPS_TEST_TICK=8; ticks(200,1,1,0); MOD_FPS_TEST_TICK=0;
    MOD_RENDER_CADENCE=1; ticks(200,1,1,0); MOD_RENDER_CADENCE=0;
    assert(MOD_FPS_MODE_RUN==2);
    ticks(110,1,0,0); assert(MOD_FPS_MODE_RUN==0);
    /* Unsigned refresh wrap preserves cooldown; late restoration is a new run. */
    modAdapt.dropV=UINT32_MAX-899; refresh=900; MOD_INTERP_MAP_GEN++;
    tick(3,0,0); assert(MOD_FPS_MODE_RUN==2);
    MOD_ADAPT_POLICY=1; tick(3,0,0); assert(MOD_FPS_MODE_RUN==0);
    MOD_ADAPT_POLICY=2; ticks(300,1,1,0); assert(MOD_FPS_MODE_RUN==2);
    MOD_ADAPT_POLICY=3; tick(3,0,0); assert(MOD_FPS_MODE_RUN==0);
    /* A synthetic 54/60 stream: three two-flip ticks per ten ticks.
     * This is a controller fixture, not a Gamma or overclock measurement. */
    MOD_ADAPT_POLICY=2; tick(3,0,0); MOD_ADAPT_POLICY=0;
    ticks(30,3,0,0);
    for(int i=0;i<80;i++) tick(i%10<3 ? 2 : 3,0,0);
    assert(MOD_FPS_MODE_RUN==0);
    puts("PASS: even/late/skipped/54-fps streams, windows, exclusions, boundary cooldown, wrap and controls");
}
'''
    compile_check(code)


if __name__ == '__main__':
    main()
