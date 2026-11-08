#!/usr/bin/env python3
"""Compile the actual diagnostic sampler with address/undefined sanitizers."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check,function
w=Path(sys.argv[1]) if len(sys.argv)>1 else Path('build/decomp-int')
s=(w/'src/main/mod_qol.c').read_text()
code=r'''
#include <stdint.h>
#include <assert.h>
int32_t MOD_DIAG_FPS, MOD_DIAG_MISSED, MOD_DIAG_MISS_COUNT, modDiagPresents;
uint32_t modDiagStart, now;
int32_t VSync(int n) { assert(n==-1); return now; }
'''+function(s,'modFpsDiagPresent')+r'''
int main(void) {
    for(now=1;now<=60;now++)modFpsDiagPresent();
    assert(MOD_DIAG_FPS==60);
    for(now=63;now<=120;now+=3)modFpsDiagPresent();
    assert(MOD_DIAG_FPS==20);
    MOD_DIAG_MISS_COUNT=17;now=180;modFpsDiagPresent();
    assert(MOD_DIAG_MISSED==17 && MOD_DIAG_MISS_COUNT==0);
    modDiagStart=UINT32_MAX-29;now=30;modDiagPresents=19;
    modFpsDiagPresent();assert(MOD_DIAG_FPS==20);
}
'''
compile_check(code)
print('PASS: presented counts at 60/20, missed deadlines, counter wrap')
