#!/usr/bin/env python3
"""Exercise the compiled field-idle selector, including condition and native guards.

Usage: python3 tools/dev/playtest/wolf_stop_host.py BUILD_TREE OUT_DIR
The real C function is extracted from the prepared patch series. This checks
selection and interruption; the 2 MB emulator covers movement and rendering.
"""
import subprocess
import sys
from pathlib import Path

PREFIX = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define VERSION_EQUAL_OR_NEWER(x) 0
typedef struct { int animId,animFrame; } EntityAnim;
typedef struct { int type; EntityAnim anim; } Entity;
struct { struct { Entity entity; } digimonEntity; } PARTNER_ENTITY;
struct { int condition; } PARTNER_PARA;
int PARTNER_ANIMATION,calls,chosen;
void startAnimation(Entity *e,uint8_t slot) { calls++;chosen=slot;e->anim.animId=slot; }
'''
MAIN = r'''
int main(void) {
    Entity *e=&PARTNER_ENTITY.digimonEntity.entity;
    int cases=0;
    for(int type=0;type<2;type++) for(int slot=0;slot<44;slot++) {
        e->type=type?191:22;
        int normal=slot<=5 || slot==18;
        int stop=slot==6 || slot==20 || slot==26 || slot==28 || (slot>=29 && slot<=32);
        assert(smoothSlot(e,slot)==(normal || (type && stop)));
    }
    for(int type=0;type<2;type++) for(int source=0;source<5;source++)
    for(int condition=0;condition<128;condition++) for(int frame=0;frame<36;frame++) {
        e->type=type?191:22;e->anim.animId=source;e->anim.animFrame=frame;
        PARTNER_PARA.condition=condition;PARTNER_ANIMATION=source;calls=0;chosen=-1;
        setPartnerIdle();cases++;
        int brake=type && !(condition&0x63) && (source==2 || source==4);
        if(brake) {
            assert(calls==1);
            static const int slots[8]={6,20,26,28,29,30,31,32};
            int period=source==2?18:14;
            assert(chosen==slots[(((frame*4+period/2)/period)&3)+(source==4?4:0)]);
            assert(source==2 ? (chosen==6 || chosen==20 || chosen==26 || chosen==28) :
                              (chosen>=29 && chosen<=32));
        } else if(source>1) {
            assert(calls==1);assert(chosen==((condition&0x63)?1:0));
        } else assert(calls==0);
    }
    for(int slot=6;slot<=32;slot++) {
        e->type=191;e->anim.animId=slot;PARTNER_ANIMATION=slot;
        PARTNER_PARA.condition=0;calls=0;setPartnerIdle();assert(calls==1 && chosen==0);
    }
    printf("%d selector cases and 27 completion cases passed\n",cases);
    return 0;
}
'''


def main():
    tree, out = map(Path, sys.argv[1:])
    source = (tree / 'src/main/partner.c').read_text()
    start = source.index('void setPartnerIdle(void)\n{')
    end = source.index('\nvoid partnerSetState', start)
    out.mkdir(parents=True, exist_ok=True)
    file = out / 'wolf-stop.c'
    smooth = (tree / 'src/main/smooth_runtime.inc').read_text()
    first = smooth.index('static int32_t smoothSlot(')
    last = smooth.index('\nvoid modSmoothForget', first)
    file.write_text(PREFIX + smooth[first:last] + source[start:end] + MAIN)
    exe = out / 'wolf-stop'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(file), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
