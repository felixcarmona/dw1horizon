#!/usr/bin/env python3
"""Exercise the applied title display: calibration, visibility, colors and redraws."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-dev')
    source = (work / 'src/main/main_menu.c').read_text()
    if (work / 'src/main/main.c').exists():
        main_source = (work / 'src/main/main.c').read_text()
        landing = function(main_source, 'runLandingScreen')
        assert landing.index('loadTitleMenuOverlays();') < landing.index('addObject(')
        assert 'removeObject(0xfa3, 0);' in landing
    a = source.index('static const int16_t MOD_NOTICE_CALIBRATION')
    calibration = source[a:source.index(';', a) + 1]
    for fps in (20, 60):
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <limits.h>
#include <assert.h>
#include <string.h>
#define MOD_NOTICE_NO_RAM 1
#define MOD_CPU_SPINS_FAST 8500
#define MOD_NOTICE_LEFT -148
#define MOD_NOTICE_TOP 12
#define MOD_NOTICE_WIDTH 296
#define MOD_NOTICE_HEIGHT 66
#define MOD_NOTICE_STRS 5
#define MOD_NOTICE_V(i) ((i)*12)
#define MOD_NOTICE_STR_HEAD1 "CPU 250%: 60 FPS"
#define MOD_NOTICE_STR_HEAD2 "8 MB: Chinese only"
#define MOD_NOTICE_STR_RAM "RAM %d MB"
#define MOD_NOTICE_STR_CPU "CPU ~%d%%"
#define MOD_NOTICE_STR_FPS "%d FPS"
int MOD_CPU_SPINS, MOD_NOTICE, MOD_FPS_MODE_RUN;
struct {int32_t spins, mode; uint8_t widths[5];} MOD_NOTICE_CACHE;
typedef struct {int x,y,w,h;} RECT;
#define setRECT(p,a,b,c,d) (*(p)=(RECT){a,b,c,d})
int draws, plates, strings, colors[5];
char rows[5][32];
void clearTextSubArea(RECT *rect) {assert(rect->y+rect->h==60);draws++;}
int fitStringMode(char *s,int width) {assert(width>0);return 0;}
void drawStringMode(char *s,int x,int y,int mode) {assert(y>=0 && y<60);strcpy(rows[y/12],s);}
void DrawSync(int mode) {}
int measureStringMode(char *s,int mode) {return strlen(s)*6;}
void renderString(int color,int x,int y,int w,int h,int u,int v,int depth,int shadow) {
 assert(v>=0 && v<60);colors[v/12]=color;strings++;
}
void modPlateRect(int x,int y,int w,int h,int r,int g,int b,int z) {plates++;}
''' + f'\n#define FPS {fps}\n' + calibration
        for name in ('modNoticePercent', 'modNoticeDraw', 'modNoticeString', 'modNoticeRender'):
            code += '\n' + function(source, name)
        code += r'''
int main(void) {
 int counts[]={3801,7389,9303,10977}; int expected[]={100,200,250,300};
 for(int i=0;i<4;i++) assert(modNoticePercent(counts[i])==expected[i]);
 assert(modNoticePercent(INT_MIN)==100); assert(modNoticePercent(INT_MAX)==300);
 int previous=100;
 for(int i=0;i<20000;i++) {int p=modNoticePercent(i);assert(p>=previous && p<=300 && p%25==0);previous=p;}
 for(int ram=0;ram<2;ram++) for(int fast=0;fast<2;fast++) {
  MOD_NOTICE=ram?0:1; MOD_CPU_SPINS=fast?9303:3801; MOD_FPS_MODE_RUN=fast?2:0;
  modNoticeDraw();int before=draws;plates=strings=0;modNoticeRender();
  assert(draws==before && plates==2 && strings==5); /* Always visible, including all-ready. */
  assert(!strcmp(rows[2],ram?"RAM 8 MB":"RAM 2 MB"));
  assert(!strcmp(rows[3],fast?"CPU ~250%":"CPU ~100%"));
  assert(!strcmp(rows[4],FPS!=20 && fast?"60 FPS":"20 FPS"));
  assert(colors[2]==(ram?7:6) && colors[3]==(fast?7:6));
  assert(colors[4]==(FPS!=20 && fast?7:6));
  MOD_CPU_SPINS=7389;modNoticeRender();assert(draws==before+1);
  modNoticeRender();assert(draws==before+1);
 }
 /* Hysteresis: CPU readiness and the selected rate have separate meanings. */
 MOD_CPU_SPINS=8500;MOD_FPS_MODE_RUN=0;modNoticeRender();
 assert(colors[3]==7 && colors[4]==6 && !strcmp(rows[4],"20 FPS"));
 MOD_FPS_MODE_RUN=2;int before=draws;modNoticeRender();
 assert(draws==before+(FPS!=20));
 MOD_CPU_SPINS=8000;modNoticeRender();
 assert(colors[3]==6 && colors[4]==(FPS!=20?7:6));
 puts("PASS: calibrated/clamped percent, both RAM sizes, all-ready display, mode and sample redraws");
}
'''
        compile_check(code)


if __name__ == '__main__':
    main()
