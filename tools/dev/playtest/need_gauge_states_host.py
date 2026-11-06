#!/usr/bin/env python3
"""Check the actual need-gauge renderer and original OFF GPU sequence.

Usage: python3 tools/dev/playtest/need_gauge_states_host.py TREE --before PREVIOUS.c
PREVIOUS.c is the partner_impl.c captured before this change.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile


def function(source, signature):
    start = source.index(signature)
    begin = source.index('{', start)
    depth, end = 1, begin + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    p.add_argument('--before', required=True, type=Path)
    a = p.parse_args()
    src = (a.tree/'src/main/partner_impl.c').read_text()
    old = function(a.before.read_text(), 'void renderStatusBars(state)')
    old = old.replace('void renderStatusBars(state)', 'void renderStatusBarsBefore(state)').replace('renderCareHUD();', 'assert(0);')
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
struct PP {int happiness,discipline,condition,foodLevel,starvationTimer,poopLevel,tiredness;} PARTNER_PARA;
struct {struct {struct {int type;} entity;} digimonEntity;} PARTNER_ENTITY;
struct {int poopTimer;} raise;
#define RAISE_ROW(t) raise
#define MOD_CARE_HUNGER_FOOD_PERIOD 0
#define MOD_CARE_POOP_PERIOD 1
#define MOD_CARE_TIRED_EXHAUSTED_AT 2
int rules[3]={20,200,80};
int careGet(int slot) { return rules[slot]; }
struct {int partnerAreaResponse;} MAP_TILE_DATA;
int PLAYTIME_FRAMES,MOD_OPT_BARS,STATUS_UI_OFFSET_X=75;
#define GetClut(x,y) ((y)*64+(x)/16)
struct Draw {int a[10];} calls[512],original[512];
int count;
void renderRectPolyFT4(int a,int b,int c,int d,int e,int f,int g,int h,int i,int j) {
 assert(count<512);calls[count++]=(struct Draw){{a,b,c,d,e,f,g,h,i,j}};
}
'''
    code += function(src, 'static void renderCareHUD(void)') + old + function(src, 'void renderStatusBars(state)')
    code += r'''
static void check(int gauge,int active,int blink,int red) {
 struct PP before=PARTNER_PARA;
 for(int f=0;f<80;f++) {
  PLAYTIME_FRAMES=f;MOD_OPT_BARS=1;count=0;renderStatusBars(1);
  assert(!memcmp(&before,&PARTNER_PARA,sizeof(before)));assert(count<=10);
  int tiles=0,found=0;
  for(int k=0;k<count;k++) if(calls[k].a[2]==34) {
   tiles++;
   if(calls[k].a[1] != 65+(gauge-2)*14) continue;
   assert(calls[k].a[7]==GetClut(272,500+gauge+2+active*4));
   int width=0,v=0;
   if(k+1<count && calls[k+1].a[1]==calls[k].a[1]+6) {
    width=calls[k+1].a[2];v=calls[k+1].a[5];
   }
   assert(calls[k].a[9]==(!active && blink && f%40>=20 ? 8 : 0));
   int value=gauge==2?PARTNER_PARA.foodLevel:gauge==3?(raise.poopTimer>0?2*raise.poopTimer-PARTNER_PARA.poopLevel:0):PARTNER_PARA.tiredness;
   int max=gauge==2?180:gauge==3?(raise.poopTimer>0?2*raise.poopTimer:1):100;
   if(value<0)value=0;if(value>max)value=max;
   int expected=(value*18+max/2)/max;if(value&&!expected)expected=1;
   assert(width==expected);
   if(width) {
    assert(v==251 && calls[k+1].a[4]==164);
    assert(calls[k+1].a[9]==calls[k].a[9]);
   }
   found++;
  }
  assert(tiles==5 && found==1);
 }
}
static void base(void) {
 PARTNER_PARA=(struct PP){52,80,0,120,0,24,40};
 rules[0]=20;rules[1]=200;rules[2]=80;raise.poopTimer=24;
}
int main(void) {
 // The complete original normal-value domain, including every area/blink variant.
 MOD_OPT_BARS=0;
 for(int h=-100;h<=100;h++) for(int d=0;d<=100;d++)
 for(int area=0;area<3;area++) for(int f=0;f<10;f++) {
  PARTNER_PARA.happiness=h;PARTNER_PARA.discipline=d;
  MAP_TILE_DATA.partnerAreaResponse=area;PLAYTIME_FRAMES=f;
  count=0;renderStatusBarsBefore(1);int n=count;memcpy(original,calls,n*sizeof(*calls));
  count=0;renderStatusBars(1);assert(n==count);assert(!memcmp(original,calls,n*sizeof(*calls)));
 }
 // Inclusive one-hour boundaries and species overrides expressed in real timer units.
 base();check(2,0,0,0);
 PARTNER_PARA.foodLevel=61;check(2,0,0,0);
 PARTNER_PARA.foodLevel=60;check(2,0,1,0);
 PARTNER_PARA.foodLevel=1;check(2,0,1,0);
 PARTNER_PARA.foodLevel=0;check(2,1,0,1);
 PARTNER_PARA.foodLevel=120;PARTNER_PARA.condition=4;check(2,1,0,1);
 PARTNER_PARA.starvationTimer=0;check(2,1,0,1);
 base();rules[0]=40;PARTNER_PARA.foodLevel=31;check(2,0,0,0);
 PARTNER_PARA.foodLevel=30;check(2,0,1,0);
 rules[0]=-1;check(2,0,0,0);
 base();PARTNER_PARA.poopLevel=7;check(3,0,0,0);
 PARTNER_PARA.poopLevel=6;check(3,0,1,0);
 PARTNER_PARA.poopLevel=1;check(3,0,1,0);
 PARTNER_PARA.poopLevel=0;check(3,1,0,1);
 base();PARTNER_PARA.condition=8;check(3,1,0,1);
 raise.poopTimer=0;check(3,1,0,1);
 base();rules[1]=400;PARTNER_PARA.poopLevel=4;check(3,0,0,0);
 PARTNER_PARA.poopLevel=3;check(3,0,1,0);
 rules[1]=-1;check(3,0,0,0);
 // One six-point display step before the species' actual exhausted condition.
 base();PARTNER_PARA.tiredness=73;check(4,0,0,1);
 PARTNER_PARA.tiredness=74;check(4,0,1,1);
 PARTNER_PARA.tiredness=79;check(4,0,1,1);
 PARTNER_PARA.tiredness=80;check(4,1,0,1);
 PARTNER_PARA.tiredness=100;check(4,1,0,1);
 base();PARTNER_PARA.condition=2;check(4,1,0,1);
 base();rules[2]=90;PARTNER_PARA.tiredness=83;check(4,0,0,1);
 PARTNER_PARA.tiredness=84;check(4,0,1,1);
 PARTNER_PARA.tiredness=90;check(4,1,0,1);
 rules[2]=-1;check(4,0,0,1);
 // Satisfaction clears the warning without any cached phase or state.
 base();PARTNER_PARA.condition=14;
 check(2,1,0,1);check(3,1,0,1);check(4,1,0,1);
 base();check(2,0,0,0);check(3,0,0,0);check(4,0,0,0);
 puts("PASS: 609030 original OFF call sequences; need normal/blink/active boundaries, overrides, satisfaction, 80 phase ticks and read-only state");
}
'''
    with tempfile.TemporaryDirectory(prefix='need-gauges-') as tmp:
        source, binary = Path(tmp)/'check.c', Path(tmp)/'check'
        source.write_text(code)
        subprocess.run(['cc','-O2','-Wno-implicit-int','-fsanitize=undefined',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)


if __name__ == '__main__':
    main()
