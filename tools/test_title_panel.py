#!/usr/bin/env python3
"""Exercise the applied v0.0.7 notice: missing settings, advice and readiness rows."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.test_cheats import compile_check, function


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-dev')
    source = (work / 'src/main/main_menu.c').read_text()
    landing = function((work / 'src/main/main.c').read_text(), 'runLandingScreen')
    assert landing.index('loadTitleMenuOverlays();') < landing.index('addObject(')
    assert 'removeObject(0xfa3, 0);' in landing
    a = source.index('#define MOD_NOTICE_NO_RAM')
    defines = source[a:source.index('void modPlateRect', a)]
    a = source.index('static struct {\n\tchar head[')
    text = source[a:source.index('\n};', a) + 3]
    for name in ('modNoticeDraw', 'modNoticeRender'):
        assert 'modFrameRateLevel' not in function(source, name)
        assert 'MOD_NOTICE_STR_FPS' not in function(source, name)
    for fps in (20, 60):
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#define MOD_CPU_SPINS_FAST 8500
#define MOD_NOTICE_STR_HEAD1 "Emulator settings for smoother play"
#define MOD_NOTICE_STR_HEAD2 "if you turn on these options:"
#define MOD_NOTICE_STR_RAM "8 MB RAM"
#define MOD_NOTICE_STR_CPU "CPU overclock at 250%"
#define MOD_NOTICE_STR_MISSING "NOT DETECTED"
#define MOD_NOTICE_STR_READY "READY"
int MOD_CPU_SPINS, MOD_NOTICE, level;
int modFrameRateLevel(void) { return level; }
''' + defines + text + r'''
struct {int32_t spins; uint8_t widths[MOD_NOTICE_STRS];} MOD_NOTICE_CACHE;
typedef struct {int x,y,w,h;} RECT;
#define setRECT(p,a,b,c,d) (*(p)=(RECT){a,b,c,d})
int draws, plates, strings, colors[6], xs[6], ys[6], status[2];
char rows[6][64];
int row(int v) {
 assert(v>=0 && v<84 && v!=60); /* version's atlas row must stay intact */
 return v==72?5:v/12;
}
void clearTextSubArea(RECT *rect) {if(rect->y==0) {assert(rect->h==60);draws++;}
 else {assert(rect->y==72 && rect->h==12);}}
int fitStringMode(char *s,int width) {assert(width>0);return 0;}
void drawStringMode(char *s,int x,int y,int mode) {strcpy(rows[row(y)],s);}
void DrawSync(int mode) {}
int measureStringMode(char *s,int mode) {return strlen(s)*6;}
void renderString(int color,int x,int y,int w,int h,int u,int v,int depth,int shadow) {
 int i=row(v); if(y==MOD_NOTICE_TOP+38-120 || y==MOD_NOTICE_TOP+52-120) status[(y-(MOD_NOTICE_TOP+38-120))/14]=i; colors[i]=color;xs[i]=x;ys[i]=y;strings++;
}
void modPlateRect(int x,int y,int w,int h,int r,int g,int b,int z) {
 assert(w==296 || w==294); assert(h==72 || h==70);plates++;
}
''' + f'\n#define FPS {fps}\n'
        for name in ('modNoticeDraw', 'modNoticeString', 'modNoticeRender'):
            code += '\n' + function(source, name)
        code += r'''
int main(void) {
 int counts[]={3801,7389,8499,8500,9303,10977};
 for(int ram=0;ram<2;ram++) for(int c=0;c<6;c++) for(level=0;level<3;level++) {
  int fast=counts[c]>=8500, visible=!ram||!fast;
  MOD_NOTICE=(!ram?MOD_NOTICE_NO_RAM:0)|(!fast?MOD_NOTICE_SLOW_CPU:0);
  MOD_CPU_SPINS=counts[c];
  draws=plates=strings=0;modNoticeDraw();modNoticeRender();
  assert(draws==visible && plates==2*visible && strings==6*visible);
  if(!visible) continue; /* both settings present: no notice at any rate */
  assert(!strcmp(rows[0],"Emulator settings for smoother play"));
  assert(!strcmp(rows[1],"if you turn on these options:"));
  assert(!strcmp(rows[2],"8 MB RAM") && !strcmp(rows[3],"CPU overclock at 250%"));
  /* Earlier two-column layout: labels on the left, readiness on the right. */
  assert(xs[2]==-136 && xs[3]==-136 && ys[3]-ys[2]==14);
  assert(status[0]==(ram?5:4) && status[1]==(fast?5:4));
  if(ram) assert(colors[5]==7 && xs[5]+MOD_NOTICE_CACHE.widths[5]==136);
  if(fast) assert(colors[5]==7);
  if(!ram||!fast) assert(colors[4]==6 && xs[4]+MOD_NOTICE_CACHE.widths[4]==136);
  modNoticeRender();assert(draws==1); /* unchanged readings reuse the atlas */
  MOD_CPU_SPINS++;modNoticeRender();assert(draws==2);
  level=(level+1)%3;modNoticeRender();assert(draws==2); /* frame-rate choice does not alter the notice */
  level=(level+2)%3;
 }
 /* With 8 MB, CPU changes can reveal and hide the popup. */
 MOD_NOTICE=0;MOD_CPU_SPINS=9303;level=2;draws=plates=strings=0;
 modNoticeDraw();modNoticeRender();assert(draws==0 && plates==0 && strings==0);
 MOD_NOTICE=2;MOD_CPU_SPINS=3801;modNoticeRender();assert(draws==1 && plates==2);
 MOD_NOTICE=0;MOD_CPU_SPINS=9303;plates=strings=0;modNoticeRender();
 assert(draws==1 && plates==0 && strings==0);
 puts("PASS: missing-setting truth table, threshold, advice, both readiness rows, version row, redraws; rate independent");
}
'''
        compile_check(code)


if __name__ == '__main__':
    main()
