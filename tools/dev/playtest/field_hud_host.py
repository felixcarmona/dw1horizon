#!/usr/bin/env python3
"""Exercise the actual field HUD C renderer with independent gauge expectations.

Use a prepared decomp tree: field_hud_host.py build/decomp-dev.
Checks every signed 16-bit timer/value, both need flags, 49/50 boundaries,
invalid toilet baselines, geometry, colour, and positive subpixel readings.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path)
    a=p.parse_args()
    text=(a.tree/'src/main/partner_impl.c').read_text()
    start=text.index('static void renderCareHUD(void)')
    end=text.index('// clang-format off\nvoid renderStatusBars',start)
    renderer=text[start:end]
    harness=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct { int happiness,discipline,condition,starvationTimer,foodLevel,poopLevel,tiredness; } PARTNER_PARA;
struct { struct { struct {int type;} entity; } digimonEntity; } PARTNER_ENTITY;
struct Raise {int poopTimer;} RAISE_DATA[2], importedRaise;
int importedReads;
struct Raise *getSpeciesRaise(int type) { assert(type==200); importedReads++; return &importedRaise; }
#define RAISE_ROW(t) (*((t)<2 ? &RAISE_DATA[t] : getSpeciesRaise(t)))
int STATUS_UI_OFFSET_X=75;
struct Draw {int x,y,w,h,u,v,page,clut,z;} draws[10]; int count;
#define GetClut(x,y) ((y)*64+(x)/16)
void renderRectPolyFT4(int x,int y,int w,int h,int u,int v,int page,int clut,int z,int flag) {
 assert(!flag && count<10); draws[count++]=(struct Draw){x,y,w,h,u,v,page,clut,z};
}
''' + renderer + r'''
int width(int value,int max) {
 if(value<=0)return 0;
 if(value>=max)return 18;
 double exact=(double)value/max*18;
 int out=(int)(exact+0.5);
 return out?out:1;
}
void check(int gauge,int value,int max,int red,int icon) {
 count=0;renderCareHUD();
 int n=0, found=0;
 const int ys[]={72,86,65,79,93};
 for(int k=0;k<count;k++) {
  struct Draw d=draws[k];
  assert(d.page==31);
  if(d.h==13) {
   assert(d.x==(n<2?76:114) && d.y==ys[n]);
   if(n==gauge) {assert(d.clut==GetClut(272,500+icon));found=k;}
   n++;
  }
 }
 assert(n==5);
 int expected=width(value,max);
 if(expected) {
  struct Draw d=draws[found+1];
  assert(d.h==2 && d.w==expected && d.x==draws[found].x+15 && d.y==draws[found].y+6);
  assert(d.u==144 && d.v==251+red*2 && d.clut==GetClut(272,507));
 } else assert(found+1==count || draws[found+1].h==13);
}
int main(void) {
 RAISE_DATA[0].poopTimer=12;
 for(int v=-32768;v<=32767;v++) {
  PARTNER_PARA.happiness=v; check(0,v+100,200,v<0,v<0);
  PARTNER_PARA.discipline=v; check(1,v,100,v<50,2+(v<50));
  PARTNER_PARA.tiredness=v; check(4,v,100,v>=50,6);
  for(int flag=0;flag<2;flag++) {
   PARTNER_PARA.condition=flag?4:0;
   PARTNER_PARA.foodLevel=v;PARTNER_PARA.starvationTimer=v;
   check(2,v,180,flag,4);
   PARTNER_PARA.condition=flag?8:0;
   PARTNER_PARA.poopLevel=v;
   check(3,flag?24:24-v,24,flag,5);
  }
 }
 for(int t=-32768;t<=32767;t++) {
  RAISE_DATA[0].poopTimer=t;
  PARTNER_PARA.poopLevel=0;
  PARTNER_PARA.condition=0;check(3,t>0?2*t:0,t>0?2*t:1,0,5);
  PARTNER_PARA.condition=8;check(3,1,1,1,5);
 }
 // Toilet and portable-potty native resets: 2*T empty, T half full.
 RAISE_DATA[0].poopTimer=12; PARTNER_PARA.condition=0;
 PARTNER_PARA.poopLevel=24;check(3,0,24,0,5);
 PARTNER_PARA.poopLevel=12;check(3,12,24,0,5);
 PARTNER_ENTITY.digimonEntity.entity.type=200; importedRaise.poopTimer=20;
 PARTNER_PARA.condition=0;PARTNER_PARA.poopLevel=20;check(3,20,40,0,5);
 importedRaise.poopTimer=10;check(3,0,20,0,5); assert(importedReads==2);
 puts("PASS: 589828 exhaustive live-value/flag/baseline cases; B5a geometry, fill and palette");
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        src=Path(tmp)/'hud.c';exe=Path(tmp)/'hud'
        src.write_text(harness)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=undefined','-o',exe,src],check=True)
        subprocess.run([exe],check=True)


if __name__=='__main__':main()
