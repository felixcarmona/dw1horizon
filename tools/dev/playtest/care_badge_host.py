#!/usr/bin/env python3
"""Compare the field renderer with the legacy badge offsets, including pixel quads."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev.playtest.quick_care_host import function

root=Path(sys.argv[1] if len(sys.argv)>1 else 'build/decomp-dev')
source=(root/'src/main/bubble.c').read_text()
renderer = function(source, 'static void renderConditionRing(int32_t x, int32_t y, int32_t depth,')
patch = (ROOT/'mods/patches/Patch-0158-X-badge.-The-dialogue-box-s-X-button-rend.patch').read_text()
added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
legacy_block = function(added, '\tif (MOD_RING_BADGE > 0)').replace('j < 6', 'j < 8')
current_block = function(renderer, '\tif (MOD_RING_BADGE > 0) {\n\t\tint32_t right')
legacy = renderer.replace(current_block, legacy_block).replace(
    'static void renderConditionRing(', 'static void renderLegacyConditionRing(', 1)
prefix=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#define RING_SIZE 205
#define RING_BADGE_W 16
#define RING_BADGE_H 12
#define RING_BADGE_TICKS 4
static int32_t DRAWING_OFFSET_X=160,DRAWING_OFFSET_Y=120,CLOCK_OFFSET_X=-220;
static int32_t VIEWPORT_DISTANCE=4096,MOD_RING_BADGE,MOD_RING_STEPS,MOD_RING_SHOWN[5];
static int fx[8],fy[8],fs[8],drawn,seen[8],gx[8],gy[8],badgeCount,badgeX,badgeY,badgeK,badgeSize,minTop;
static int32_t ringPhase(void){return 0;}
static void ringBubbleAt(int j,int p,int*x,int*y,int*s,int*t){
 (void)p;*x=fx[j];*y=fy[j];*s=fs[j];*t=0;
}
static void drawRingBubble(int j,int x,int y,int depth,uint32_t scale,int size,int tail,int k){
 (void)depth;(void)scale;(void)tail;
 assert(!seen[j]);seen[j]=1;drawn++;
 gx[j]=x;gy[j]=y;
 int left=x+DRAWING_OFFSET_X-((13*k*size)>>20),right=x+DRAWING_OFFSET_X+((13*k*size)>>20);
 int groupTop=y+DRAWING_OFFSET_Y-((13*k*size)>>20),groupBottom=y+DRAWING_OFFSET_Y+((13*k*size)>>20);
 assert(left>=0 && right<=320);
 if(CLOCK_OFFSET_X==-135 && groupTop<84 && groupBottom>20)assert(left>=78 || right<=23);

 assert(size==fs[j]);int top=y-((13*k*size)>>20);if(top<minTop)minTop=top;
}
static void renderBadge(int x,int y,int depth,int k,int size){
 (void)depth;
 int w=(RING_BADGE_W*((k*size)>>8))>>12;
 if(drawn)assert(x+DRAWING_OFFSET_X-w/2>=0 && x+DRAWING_OFFSET_X+w/2<=320);
 badgeCount++;badgeX=x;badgeY=y;badgeK=k;badgeSize=size;
}
'''
tests=r'''
int main(void){
 int cases=0;
 for(DRAWING_OFFSET_X=96;DRAWING_OFFSET_X<=224;DRAWING_OFFSET_X+=32)
 for(int hud=0;hud<2;hud++)for(int oy=30;oy<=200;oy+=85)
 for(int origin=8;origin<=312;origin+=152)
 for(int pattern=0;pattern<3;pattern++)
 for(int n=0;n<=8;n++)for(int grow=25;grow<=205;grow+=60)
 for(int k=2048;k<=8192;k+=2048)for(int badge=0;badge<=4;badge++){
  CLOCK_OFFSET_X=hud?-135:-220;
  int top=n>2?(n+1)/2:0;
  for(int j=0;j<8;j++){
   int col=j<top?j:j-top,cnt=j<top?top:n-top;
   fx[j]=j<n?((2*col-(cnt-1))*22/2)*16:0;
   fy[j]=j<n&&j<top?-(pattern==2?9:18)*16:0;
   if(pattern==2&&j<n&&(j%2))fy[j]-=32;
   fs[j]=j<n?(pattern==1&&(j%2)?205:grow):0;seen[j]=0;
  }
  drawn=badgeCount=0;minTop=100000;MOD_RING_BADGE=badge;
  renderLegacyConditionRing(origin-DRAWING_OFFSET_X,oy-DRAWING_OFFSET_Y,4096,k);
  int oldGX[8],oldGY[8];for(int j=0;j<n;j++){oldGX[j]=gx[j];oldGY[j]=gy[j];}
  int oldX=badgeX,oldY=badgeY,oldK=badgeK,oldSize=badgeSize;
  int oldW=(RING_BADGE_W*((oldK*oldSize)>>8))>>12;
  int oldH=(RING_BADGE_H*((oldK*oldSize)>>8))>>12;
  int oldLeft=oldX-oldW/2,oldTop=oldY-oldH/2;
  drawn=badgeCount=0;for(int j=0;j<8;j++)seen[j]=0;
  renderConditionRing(origin-DRAWING_OFFSET_X,oy-DRAWING_OFFSET_Y,4096,k);
  for(int j=0;j<n;j++)assert(gx[j]==oldGX[j]&&gy[j]==oldGY[j]);
  assert(drawn==n);assert(badgeCount==(badge>0));
  if(badge){
   int w=(RING_BADGE_W*((badgeK*badgeSize)>>8))>>12;
   int h=(RING_BADGE_H*((badgeK*badgeSize)>>8))>>12;
   assert(badgeX==oldX&&badgeY==oldY&&badgeK==oldK&&badgeSize==oldSize);
   assert(w==oldW&&h==oldH&&badgeX-w/2==oldLeft&&badgeY-h/2==oldTop);
  }
  cases++;
 }
 printf("PASS: %d layouts; 0..8 bubbles at left/centre/right, growing/moving edges, four projected scales, all badge phases; legacy centre, size and pixel offsets identical; all relative condition positions unchanged; condition-group footprints inside the viewport and clear of the fixed HUD clock under five camera offsets\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='care-badge-host-') as tmp:
 c=Path(tmp)/'care.c';exe=Path(tmp)/'care'
 c.write_text(prefix+legacy+renderer+tests)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
