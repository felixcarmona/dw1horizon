#!/usr/bin/env python3
"""Exercise the applied title trial against presentation rates and clock wrap."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-int')
    source = (work / 'src/main/main.c').read_text()
    for fps in (20, 60):
        for diagnostics in (0, 1):
            code = r'''
#include <stdint.h>
#include <assert.h>
#include <stddef.h>
#define MOD_WORKLOAD_MIN_FPS 40
#define FPS_DIAGNOSTICS DIAGNOSTICS
#define FPS BUILD_FPS
typedef struct { int marker; } MATRIX;
struct { MATRIX coord; int flg; } MEDAL_COORDINATES;
int modTrialDone, MOD_FPS_MODE_RUN, MOD_FPS_AUTO_MODE, MOD_NOTICE;
uint32_t MOD_FPS_TRIAL_SWAPS, MOD_FPS_TRIAL_VBLANKS;
int MOD_FPS_TRIAL_FPS100, MOD_FPS_TRIAL_CPU_SPINS;
uint32_t MOD_FPS_RENDERS, refresh, trialElapsed;
int rate, period=3, objects, invalidated, probeCalls, presents;
int VSync(int mode) { assert(mode==-1); return refresh; }
void modTrialRender(int unused) {}
void addObject(int id,int instance,void *tick,void (*render)(int)) {
 assert(id==0x7f60 && !instance && !tick && render==modTrialRender);objects++;
}
void removeObject(int id,int instance) { objects--; }
void modTickStart(int flags) { assert(!flags); }
void modFpsBeginFrame(void) {}
void modPresent(int flags,void *rollback) {
 assert(MOD_FPS_MODE_RUN==2); refresh+=period;trialElapsed+=period;
 MOD_FPS_RENDERS=(uint32_t)((uint64_t)trialElapsed*rate/60);presents++;
}
void modInterpInvalidate(void) { invalidated++; }
int modCpuProbe(void) { probeCalls++;MOD_NOTICE=3;return 3801; }
'''.replace('#define FPS_DIAGNOSTICS DIAGNOSTICS', '#define FPS_DIAGNOSTICS '+str(diagnostics)).replace('BUILD_FPS',str(fps))
            code += function(source, 'modFrameRateTrial')
            code += r'''
static void run(int expected) {
 modTrialDone=0;objects=0;invalidated=0;probeCalls=0;presents=0;
 MOD_NOTICE=1;MOD_FPS_MODE_RUN=0;trialElapsed=0;MOD_FPS_RENDERS=0;
 MEDAL_COORDINATES.coord.marker=42;
 modFrameRateTrial();
 if (FPS==20) { assert(presents==0 && MOD_FPS_MODE_RUN==0);return; }
 assert(MOD_FPS_MODE_RUN==expected && objects==0 && invalidated==1);
 assert(MOD_NOTICE==(expected ? 1 : 3));
 assert(MEDAL_COORDINATES.coord.marker==42);
 assert(probeCalls==FPS_DIAGNOSTICS);
 if (FPS_DIAGNOSTICS) {
  assert(MOD_FPS_TRIAL_VBLANKS>=120 && MOD_FPS_TRIAL_VBLANKS<120+period);
  assert(MOD_FPS_TRIAL_CPU_SPINS==3801);
  assert(MOD_FPS_TRIAL_FPS100/100==rate);
 }
 int previous=presents;
 modFrameRateTrial();assert(presents==previous); /* no oscillation/retrial */
}
int main(void) {
 for (rate=0;rate<=60;rate++) { refresh=100;run(rate>=40 ? 2 : 0); }
 /* Lost whole ticks count in elapsed time; long ticks cannot inflate FPS. */
 period=5;rate=30;run(0);rate=55;run(2);
 /* Unsigned vblank subtraction crosses the 32-bit counter boundary. */
 period=3;rate=60;refresh=UINT32_MAX-20;run(2);
}
'''
            compile_check(code)
    assert 'modAutoFrameRatePoll' not in source
    menu = (work / 'src/main/main_menu.c').read_text()
    boot = function(menu, 'modNoticeProbe')
    assert 'MOD_CPU_SPINS >= MOD_CPU_SPINS_FAST ? 2 : 0' not in boot
    print('PASS: 0–60 fps, inclusive 40 fps, long ticks, wrap, one-shot, diagnostics, FPS=20')


if __name__ == '__main__':
    main()
