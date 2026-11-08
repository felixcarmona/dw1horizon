#!/usr/bin/env python3
"""Compile the applied CPU selector and exercise clock changes and idle budgeting."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-int')
    source = (work / 'src/main/main.c').read_text()
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define MOD_CPU_LINES 16
#define MOD_CPU_SPINS_FAST 8500
#define MOD_CPU_SPINS_SLOW 7500
uint32_t modCpuLastV, refresh;
int32_t modLastEndV;
int32_t modCpuVotes, MOD_FPS_MODE_RUN, MOD_LOAD_PUMP, line, spins, probes;
int32_t VSync(int mode) { return mode == -1 ? (int32_t)refresh : line; }
int32_t modCpuProbe(void) { probes++; return spins; }
'''
    for name in ('modAutoFrameRateSample', 'modAutoFrameRatePoll'):
        code += '\n' + function(source, name)
    code += r'''
static void sample(int count) {
    refresh += 120; modLastEndV = refresh; spins = count; modAutoFrameRatePoll();
}
int main(void) {
    /* Original CPU must never enable extra passes, including a noisy sample. */
    for (int i = 0; i < 100; i++) sample(3801);
    assert(MOD_FPS_MODE_RUN == 0);
    sample(9303); sample(3801); sample(9303);
    assert(MOD_FPS_MODE_RUN == 0 && modCpuVotes == 1);
    sample(9303); assert(MOD_FPS_MODE_RUN == 2);
    /* The hysteresis band keeps either current mode stable. */
    for (int i = 0; i < 100; i++) sample(8000);
    assert(MOD_FPS_MODE_RUN == 2);
    sample(7499); sample(7500); sample(7499);
    assert(MOD_FPS_MODE_RUN == 2);
    sample(7499); assert(MOD_FPS_MODE_RUN == 0);
    for (int i = 0; i < 100; i++) sample(8499);
    assert(MOD_FPS_MODE_RUN == 0);
    /* Busy/load waits defer rather than consume the interval or a vote. */
    int before = probes; uint32_t last = modCpuLastV;
    refresh += 120; modLastEndV = refresh; spins = 9303; line = 231;
    modAutoFrameRatePoll(); assert(probes == before && modCpuLastV == last);
    line = 230; MOD_LOAD_PUMP = 1;
    modAutoFrameRatePoll(); assert(probes == before && modCpuLastV == last);
    MOD_LOAD_PUMP = 0;
    modAutoFrameRatePoll(); assert(probes == before + 1 && modCpuVotes == 1);
    refresh += 119;
    modAutoFrameRatePoll(); assert(probes == before + 1);
    refresh++; modLastEndV = refresh;
    modAutoFrameRatePoll(); assert(MOD_FPS_MODE_RUN == 2);
    /* A wrapped SDK line count after a long stall cannot authorize a probe. */
    before = probes; refresh += 240; line = 0;
    modAutoFrameRatePoll(); assert(probes == before);
    modLastEndV = refresh;
    modAutoFrameRatePoll(); assert(probes == before + 1);
    modCpuVotes = 0;
    /* Refresh wrap and a restored clock do not stall later CPU changes. */
    modCpuLastV = UINT32_MAX - 59; refresh = 60; modLastEndV = refresh; spins = 3801;
    modAutoFrameRatePoll(); assert(modCpuVotes == 1);
    sample(3801); assert(MOD_FPS_MODE_RUN == 0);
    modCpuLastV = 100000; refresh = 300; modLastEndV = refresh; spins = 9303;
    modAutoFrameRatePoll(); sample(9303); assert(MOD_FPS_MODE_RUN == 2);
    puts("PASS: CPU changes, threshold noise, safe idle windows, refresh wrap and restored clocks");
}
'''
    compile_check(code)
    test_boot(work)


def test_boot(work):
    menu = (work / 'src/main/main_menu.c').read_text()
    for fps in (20, 30, 60):
        code = r'''
#include <stdint.h>
#include <assert.h>
#define MOD_CPU_SPINS_FAST 8500
#define ADAPTIVE_FPS 0
#define MOD_NOTICE_NO_RAM 1
#define MOD_NOTICE_SLOW_CPU 2
int32_t MOD_CPU_SPINS, MOD_NOTICE, MOD_FPS_MODE_RUN, ram;
void modCpuProbe(void) { }
int32_t modProbeRam(void) { return ram; }
''' + f'\n#define FPS {fps}\n' + function(menu, 'modNoticeProbe') + r'''
int main(void) {
    int counts[] = {3801, 7389, 8499, 8500, 9303, 10977};
    for (ram = 0; ram < 2; ram++) {
        for (int i = 0; i < 6; i++) {
            MOD_CPU_SPINS = counts[i]; MOD_FPS_MODE_RUN = 0;
            modNoticeProbe();
            assert(MOD_FPS_MODE_RUN == (FPS != 20 && counts[i] >= 8500 ? 2 : 0));
            assert((MOD_NOTICE & 1) == !ram);
            assert(!!(MOD_NOTICE & 2) == (counts[i] < 8500));
        }
    }
}
'''
        compile_check(code)


if __name__ == '__main__':
    main()
