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
#define FPS 60
#define MOD_FPS_AUTO 0
#define MOD_FPS_60 1
#define MOD_FPS_20 2
#define MOD_FPS_POLICY_AUTO 0
#define MOD_FPS_POLICY_60 1
#define MOD_FPS_POLICY_20 3
#define MOD_FPS_POLICY_CPU 4
int8_t MOD_FPS_POLICY = MOD_FPS_POLICY_CPU;
int32_t MOD_OPT_FPS, MOD_CPU_SPINS;
#define MOD_CPU_LINES 16
#define MOD_CPU_SPINS_FAST 8500
#define MOD_CPU_SPINS_SLOW 7500
uint32_t modCpuLastV, refresh;
int32_t modLastEndV;
int32_t modCpuVotes, MOD_FPS_MODE_RUN, MOD_LOAD_PUMP, line, spins, probes;
int32_t VSync(int mode) { return mode == -1 ? (int32_t)refresh : line; }
int32_t modCpuProbe(void) { probes++; return spins; }
'''
    for name in ('modSetFrameRate', 'modAutoFrameRateSample', 'modAutoFrameRatePoll'):
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
    /* Forced modes survive arbitrarily many contrary probe samples. */
    MOD_CPU_SPINS = 3801;
    modSetFrameRate(MOD_FPS_60);
    for (int i = 0; i < 100; i++) sample(3801);
    assert(MOD_FPS_MODE_RUN == 2 && MOD_OPT_FPS == MOD_FPS_60);
    modSetFrameRate(MOD_FPS_20);
    for (int i = 0; i < 100; i++) sample(9303);
    assert(MOD_FPS_MODE_RUN == 0 && MOD_FPS_POLICY == MOD_FPS_POLICY_20);
    modSetFrameRate(MOD_FPS_AUTO);
    assert(MOD_FPS_MODE_RUN == 2 && MOD_FPS_POLICY == MOD_FPS_POLICY_AUTO);
    for (int i = 0; i < 100; i++) sample(3801);
    assert(MOD_FPS_MODE_RUN == 2); /* workload, not clock-loop throughput, decides AUTO */
    modSetFrameRate(99); assert(MOD_OPT_FPS == MOD_FPS_AUTO);
    puts("PASS: forced modes, CPU changes, threshold noise, safe idle windows, refresh wrap and restored clocks");
}
'''
    compile_check(code)
    test_level(work)
    test_boot(work)
    test_slots(work)
    test_schedule(work)
    test_lookup(work)


def test_level(work):
    source = (work / 'src/main/main.c').read_text()
    for fps in (20, 60):
        code = r'''
#include <stdint.h>
#include <assert.h>
#define MOD_FPS_POLICY_60 1
#define MOD_FPS_POLICY_30 2
#define MOD_FPS_POLICY_20 3
#define MOD_FPS_POLICY_CPU 4
int MOD_FPS_POLICY, MOD_FPS_MODE_RUN, MOD_CAD_LEVEL;
''' + f'\n#define FPS {fps}\n' + function(source, 'modFrameRateLevel') + r'''
int main(void) {
    for (MOD_CAD_LEVEL=0; MOD_CAD_LEVEL<3; MOD_CAD_LEVEL++) {
        MOD_FPS_POLICY=0;
        assert(modFrameRateLevel()==(FPS==20?0:MOD_CAD_LEVEL));
        for (MOD_FPS_POLICY=1; MOD_FPS_POLICY<=3; MOD_FPS_POLICY++)
            assert(modFrameRateLevel()==(FPS==20?0:3-MOD_FPS_POLICY));
        MOD_FPS_POLICY=4;
        for(MOD_FPS_MODE_RUN=0;MOD_FPS_MODE_RUN<=2;MOD_FPS_MODE_RUN+=2)
            assert(modFrameRateLevel()==(FPS==20?0:MOD_FPS_MODE_RUN));
    }
}
'''
        compile_check(code)


def test_boot(work):
    menu = (work / 'src/main/main_menu.c').read_text()
    for fps in (20, 30, 60):
        code = r'''
#include <stdint.h>
#include <assert.h>
#define MOD_CPU_SPINS_FAST 8500
#define MOD_NOTICE_NO_RAM 1
#define MOD_NOTICE_SLOW_CPU 2
#define MOD_FPS_AUTO 0
#define MOD_FPS_60 1
#define MOD_FPS_20 2
#define MOD_FPS_POLICY_AUTO 0
#define MOD_FPS_POLICY_60 1
#define MOD_FPS_POLICY_20 3
#define MOD_FPS_POLICY_CPU 4
int8_t MOD_FPS_POLICY = MOD_FPS_POLICY_CPU;
int32_t MOD_CPU_SPINS, MOD_NOTICE, MOD_FPS_MODE_RUN, ram, MOD_OPT_FPS, modCpuVotes;
void modCpuProbe(void) { }
int32_t modProbeRam(void) { return ram; }
''' + f'\n#define FPS {fps}\n' + function((work / 'src/main/main.c').read_text(), 'modSetFrameRate') + '\n' + function(menu, 'modNoticeProbe') + r'''
int main(void) {
    int counts[] = {3801, 7389, 8499, 8500, 9303, 10977};
    for (ram = 0; ram < 2; ram++) {
        for (int i = 0; i < 6; i++) {
            MOD_CPU_SPINS = counts[i]; MOD_FPS_MODE_RUN = 0;
            modNoticeProbe();
            assert(MOD_FPS_MODE_RUN == (FPS != 20 ? 2 : 0));
            assert((MOD_NOTICE & 1) == !ram);
            assert(!!(MOD_NOTICE & 2) == (counts[i] < 8500));
        }
    }
}
'''
        compile_check(code)


def test_slots(work):
    """Exercise the actual shared third-value slots under sanitizers in both fonts."""
    import re
    menu = (work / 'src/main/main_menu.c').read_text()
    constants = menu[menu.index('#define MOD_OPT_ROW_STORY'):menu.index('static void renderOptionsMenu')]
    constants += '\n#define MOD_OPT_ROW_CHEATS (MOD_OPT_ROWS - 1)\n#define MOD_LANGS 9\n'
    for font in (0, 1):
        code = '#include <stdint.h>\n#include <assert.h>\n' + f'#define FONT_SWITCH {font}\n' + constants
        for name in ('MOD_OPT_V', 'MOD_OPT_LANG_V', 'MOD_OPT_FPS_V', 'MOD_OPT_W', 'MOD_OPT_LANG_W'):
            code += re.search(r'^static (?:int16_t|uint8_t) ' + name + r'[^;]*;', menu, re.M)[0] + '\n'
        for name in ('modOptionV', 'modOptionW'):
            start = re.search(r'^static (?:int16_t|uint8_t) \*' + name + r'\([^;]*?\)\n\{', menu, re.M)
            code += menu[start.start():menu.index('\n}', start.end()) + 2] + '\n'
        code += r"""
int main(void) {
    *modOptionV(MOD_OPT_ROW_FPS, 2) = 123;
    *modOptionV(MOD_OPT_ROW_DIFF, 2) = 456;
#if FONT_SWITCH
    *modOptionV(MOD_OPT_ROW_FONT, 2) = 789;
#endif
    for (int row=0; row<MOD_OPT_ROWS; row++) {
        for (int k=0; k<2; k++) *modOptionV(row,k)=0;
        for (int k=0; k<3; k++) *modOptionW(row,k)=0;
    }
    assert(*modOptionV(MOD_OPT_ROW_FPS,2)==123);
    assert(*modOptionV(MOD_OPT_ROW_DIFF,2)==456);
#if FONT_SWITCH
    assert(*modOptionV(MOD_OPT_ROW_FONT,2)==789);
#endif
    *modOptionW(MOD_OPT_ROW_FPS,3)=1;
    *modOptionW(MOD_OPT_ROW_DIFF,3)=2;
#if FONT_SWITCH
    *modOptionW(MOD_OPT_ROW_FONT,3)=3;
#endif
    assert(*modOptionW(MOD_OPT_ROW_FPS,3)==1 && *modOptionW(MOD_OPT_ROW_DIFF,3)==2);
}
"""
        compile_check(code)


def test_schedule(work):
    source=(work/'src/main/main.c').read_text()
    start=source.index('/* the thirds of the tick at which a frame is shown */')
    block=source[start:source.index('/* at 20 fps nothing below touches the interpolation */',start)]
    code=r"""
#include <stdint.h>
#include <assert.h>
int main(void) {
    int32_t n,r=0,period=3,MOD_FPS_MODE,MOD_RENDER_CADENCE=0,MOD_FPS_TICKS=0,thirds[3];
    for (MOD_FPS_MODE=0;MOD_FPS_MODE<=2;MOD_FPS_MODE+=2) {
"""+block+r"""
        if (MOD_FPS_MODE==0)assert(n==1 && thirds[0]==3);
        else assert(n==3 && thirds[0]==1 && thirds[1]==2 && thirds[2]==3);
    }
    return r;
}
"""
    compile_check(code)


def test_lookup(work):
    """Compile the real row table and lookups after compacting MENU storage."""
    import re
    menu=(work/'src/main/main_menu.c').read_text()
    constants=menu[menu.index('#define MOD_OPT_ROW_STORY'):menu.index('static void renderOptionsMenu')]
    start=menu.index('static char *MOD_OPT_TEXT[')
    table=menu[start:menu.index('\n};',start)+3]
    names=re.search(r'^static char \*MOD_LANGUAGE_NAMES[^;]+;',menu,re.M)[0]
    strings=''.join(f'#define {key} "{key}"\n' for key in sorted(set(re.findall(r'MOD_OPT_STR_\w+',table+names))))
    codebase='#include <stdint.h>\n#include <assert.h>\n#include <string.h>\n#define MOD_LANGS 9\n#define MOD_LANG_ZH 8\nint MOD_LANG;\nint modLanguageAt(int n){return n;}\nint modLanguageCount(void){return 9;}\n'
    for font in (0,1):
        code=codebase+f'#define FONT_SWITCH {font}\n'+constants+'\n'+strings+table+'\n'+names+'\n'
        for name in ('modOptionLanguageName','modOptionText'):
            start=re.search(r'^static (?:__attribute__\(\(noinline\)\) )?char \*'+name+r'\([^;]*?\)\n\{',menu,re.M)
            code+=menu[start.start():menu.index('\n}',start.end())+2]+'\n'
        code+=function(menu,'modOptionCount')+r"""
int main(void) {
    for(MOD_LANG=0;MOD_LANG<=8;MOD_LANG+=8) {
        assert(modOptionCount(MOD_OPT_ROW_FPS)==3);
        assert(modOptionCount(MOD_OPT_ROW_DIFF)==3);
        assert(modOptionCount(MOD_OPT_ROW_LANG)==9);
        assert(strcmp(modOptionText(MOD_OPT_ROW_FPS,1),MOD_OPT_STR_AUTO)==0);
        assert(strcmp(modOptionText(MOD_OPT_ROW_FPS,2),MOD_OPT_STR_60)==0);
        assert(strcmp(modOptionText(MOD_OPT_ROW_FPS,3),MOD_OPT_STR_20)==0);
        assert(strcmp(modOptionText(MOD_OPT_ROW_DIFF,3),MOD_OPT_STR_HARD)==0);
#if FONT_SWITCH
        assert(modOptionCount(MOD_OPT_ROW_FONT)==(MOD_LANG==8?1:3));
        assert(strcmp(modOptionText(MOD_OPT_ROW_FONT,3),MOD_OPT_STR_ORIGINAL)==0);
#endif
        for(int k=1;k<=9;k++)assert(modOptionText(MOD_OPT_ROW_LANG,k)==MOD_LANGUAGE_NAMES[k-1]);
    }
}
"""
        compile_check(code)


if __name__ == '__main__':
    main()
