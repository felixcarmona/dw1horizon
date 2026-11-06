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
legacy_block = function(added, '\tif (MOD_RING_BADGE > 0)')
current_block = function(renderer, '\tif (MOD_RING_BADGE > 0)')
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
static int32_t VIEWPORT_DISTANCE=4096,MOD_RING_BADGE,MOD_RING_STEPS,MOD_RING_SHOWN[5];
static int fx[6],fy[6],fs[6],drawn,seen[6],badgeCount,badgeX,badgeY,badgeK,badgeSize,minTop;
static int32_t ringPhase(void){return 0;}
static void ringBubbleAt(int j,int p,int*x,int*y,int*s,int*t){
 (void)p;*x=fx[j];*y=fy[j];*s=fs[j];*t=0;
}
static void drawRingBubble(int j,int x,int y,int depth,uint32_t scale,int size,int tail,int k){
 (void)depth;(void)scale;(void)tail;
 assert(!seen[j]);seen[j]=1;drawn++;
 assert(x==200+((fx[j]*k)>>16));assert(y==200-((18*k)>>12)+((fy[j]*k)>>16));
 assert(size==fs[j]);int top=y-((13*k*size)>>20);if(top<minTop)minTop=top;
}
static void renderBadge(int x,int y,int depth,int k,int size){
 (void)depth;badgeCount++;badgeX=x;badgeY=y;badgeK=k;badgeSize=size;
}
'''
tests=r'''
int main(void){
 int cases=0;
 for(int pattern=0;pattern<3;pattern++)
 for(int n=0;n<=6;n++)for(int grow=25;grow<=205;grow+=60)
 for(int k=2048;k<=8192;k+=2048)for(int badge=0;badge<=4;badge++){
  int top=n>2?(n+1)/2:0;
  for(int j=0;j<6;j++){
   int col=j<top?j:j-top,cnt=j<top?top:n-top;
   fx[j]=j<n?((2*col-(cnt-1))*22/2)*16:0;
   fy[j]=j<n&&j<top?-(pattern==2?9:18)*16:0;
   if(pattern==2&&j<n&&(j%2))fy[j]-=32;
   fs[j]=j<n?(pattern==1&&(j%2)?205:grow):0;seen[j]=0;
  }
  drawn=badgeCount=0;minTop=100000;MOD_RING_BADGE=badge;
  renderLegacyConditionRing(200,200,4096,k);
  int oldX=badgeX,oldY=badgeY,oldK=badgeK,oldSize=badgeSize;
  int oldW=(RING_BADGE_W*((oldK*oldSize)>>8))>>12;
  int oldH=(RING_BADGE_H*((oldK*oldSize)>>8))>>12;
  int oldLeft=oldX-oldW/2,oldTop=oldY-oldH/2;
  drawn=badgeCount=0;for(int j=0;j<6;j++)seen[j]=0;
  renderConditionRing(200,200,4096,k);
  assert(drawn==n);assert(badgeCount==(badge>0));
  if(badge){
   int w=(RING_BADGE_W*((badgeK*badgeSize)>>8))>>12;
   int h=(RING_BADGE_H*((badgeK*badgeSize)>>8))>>12;
   assert(badgeX==oldX&&badgeY==oldY&&badgeK==oldK&&badgeSize==oldSize);
   assert(w==oldW&&h==oldH&&badgeX-w/2==oldLeft&&badgeY-h/2==oldTop);
  }
  cases++;
 }
 printf("PASS: %d layouts; 0..6 bubbles, growing/moving edges, four projected scales, all badge phases; legacy centre, size and pixel offsets identical; all condition positions unchanged\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='care-badge-host-') as tmp:
 c=Path(tmp)/'care.c';exe=Path(tmp)/'care'
 c.write_text(prefix+legacy+renderer+tests)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
