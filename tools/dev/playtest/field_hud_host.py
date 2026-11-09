#!/usr/bin/env python3
"""Exercise the actual field HUD C renderer with independent gauge expectations.

Use a prepared decomp tree: field_hud_host.py build/decomp-dev.
Checks every signed 16-bit timer/value, native need flags, 49/50 boundaries,
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
struct { int partnerAreaResponse; } MAP_TILE_DATA;
struct { int happiness,discipline,condition,starvationTimer,foodLevel,poopLevel,tiredness; } PARTNER_PARA;
struct { struct { struct {int type;} entity; } digimonEntity; } PARTNER_ENTITY;
struct Raise {int poopTimer;} RAISE_DATA[2], importedRaise;
int importedReads;
struct Raise *getSpeciesRaise(int type) { assert(type==200); importedReads++; return &importedRaise; }
#define RAISE_ROW(t) (*((t)<2 ? &RAISE_DATA[t] : getSpeciesRaise(t)))
int STATUS_UI_OFFSET_X=75,PLAYTIME_FRAMES;
#define MOD_CARE_HUNGER_FOOD_PERIOD 0
#define MOD_CARE_POOP_PERIOD 1
#define MOD_CARE_TIRED_EXHAUSTED_AT 2
int careGet(int slot) { const int rules[]={20,200,80}; return rules[slot]; }
struct Draw {int x,y,w,h,u,v,page,clut,z,flag;} draws[13]; int count;
#define GetClut(x,y) ((y)*64+(x)/16)
#define getClut GetClut
void renderRectPolyFT4(int x,int y,int w,int h,int u,int v,int page,int clut,int z,int flag) {
 assert((flag==0 || flag==8) && count<13); draws[count++]=(struct Draw){x,y,w,h,u,v,page,clut,z,flag};
}
''' + renderer + r'''
int width(int value,int max) {
 if(value<=0)return 0;
 if(value>=max)return 18;
 double exact=(double)value/max*18;
 int out=(int)(exact+0.5);
 return out?out:1;
}
void check(int gauge,int value,int max,int red,int icon,int active,int warn) {
 for(int phase=0;phase<2;phase++) {
 PLAYTIME_FRAMES=phase?23:3;
 count=0;renderCareHUD();
 int n=0, found=0;
 const int ys[]={72,86,65,79,93};
 for(int k=0;k<count;k++) {
  struct Draw d=draws[k];
  assert(d.page==31);
  if(d.h==13) {
   assert(d.x==(n<2?76:114) && d.y==ys[n]);
   if(n==gauge) {assert(d.clut==GetClut(272,500+icon+active*4));found=k;}
   n++;
  }
 }
 assert(n==5);
 int expected=width(value,max);
 int dim=!active&&warn&&phase?8:0;
 assert(draws[found].flag==0);
 assert(draws[found].w==(dim?13:34));
 if(dim) {
  struct Draw track=draws[found+1],iconDraw=draws[found];
  assert(track.w==20 && track.h==4 && track.x==iconDraw.x+14 && track.y==iconDraw.y+5);
  assert(track.u==iconDraw.u+14 && track.v==iconDraw.v+5 && track.clut==iconDraw.clut && track.flag==8);
  found++;
 }

 if(expected) {
  struct Draw d=draws[found+1];
  assert(d.h==2 && d.w==expected && d.x==draws[found].x+(dim?1:15) && d.y==draws[found].y+(dim?1:6));
  assert(d.u==(gauge<2?144:164) && d.v==(gauge<2?251+red*2:251) && d.clut==GetClut(272,507) && d.flag==dim);
 } else assert(found+1==count || draws[found+1].h==13);
 }
}
int main(void) {
 RAISE_DATA[0].poopTimer=12;
 for(int v=-32768;v<=32767;v++) {
  PARTNER_PARA.happiness=v; check(0,v+100,200,v<0,v<0,0,0);
  PARTNER_PARA.discipline=v; check(1,v,100,v<50,2+(v<50),0,0);
  PARTNER_PARA.tiredness=v; check(4,100-v,100,v>=50,6,v>=80,v>=74);
  for(int flag=0;flag<2;flag++) {
   PARTNER_PARA.condition=flag?4:0;
   PARTNER_PARA.foodLevel=v;PARTNER_PARA.starvationTimer=v;
   check(2,v,180,flag,4,flag||v<=0,v<=60);
   PARTNER_PARA.condition=flag?8:0;
   PARTNER_PARA.poopLevel=v;
   check(3,v,24,flag,5,flag||v<=0,v<=6);
  }
 }
 for(int t=-32768;t<=32767;t++) {
  RAISE_DATA[0].poopTimer=t;
  PARTNER_PARA.poopLevel=0;
  PARTNER_PARA.condition=0;check(3,0,t>0?2*t:1,0,5,t>0,0);
  PARTNER_PARA.condition=8;check(3,0,t>0?2*t:1,1,5,1,0);
 }
 // Toilet and portable-potty native resets: 2*T full, T half full.
 RAISE_DATA[0].poopTimer=12; PARTNER_PARA.condition=0;
 PARTNER_PARA.poopLevel=24;check(3,24,24,0,5,0,0);
 PARTNER_PARA.poopLevel=12;check(3,12,24,0,5,0,0);
 PARTNER_ENTITY.digimonEntity.entity.type=200; importedRaise.poopTimer=20;
 PARTNER_PARA.condition=0;PARTNER_PARA.poopLevel=20;check(3,20,40,0,5,0,0);
 importedRaise.poopTimer=10;check(3,20,20,0,5,0,0); assert(importedReads==4);
 // Preserve the existing one-second need warning phases at every counter value.
 PARTNER_ENTITY.digimonEntity.entity.type=0; RAISE_DATA[0].poopTimer=12;
 PARTNER_PARA.condition=0; PARTNER_PARA.foodLevel=20;
 PARTNER_PARA.poopLevel=4; PARTNER_PARA.tiredness=75;
 for(int frame=0;frame<=65535;frame++) {
  PLAYTIME_FRAMES=frame; count=0;renderCareHUD();
  int row=0;
  for(int k=0;k<count;k++) if(draws[k].h==13) {
   if(row>=2) assert(draws[k].w==(frame%40>=20?13:34));
   row++;
  }
  assert(row==5);
 }
 // The original phase owns exactly five of every ten play ticks, including wrap.
 for(int frame=0;frame<=65535;frame++) for(int response=0;response<3;response++) {
  PLAYTIME_FRAMES=frame; MAP_TILE_DATA.partnerAreaResponse=response;
  for(int negative=0;negative<2;negative++) {
   PARTNER_PARA.happiness=negative?-50:50;
   count=0;renderCareHUD();
   int expected=(response==2 && frame%10<5) ? GetClut(272,511)-negative : GetClut(272,500+negative);
   assert(draws[0].clut==expected);
   // No habitat effect may change the gauge value or its red/green colour.
   assert(draws[1].w==width(negative?50:150,200));
   assert(draws[1].v==251+negative*2);
  }
 }
 puts("PASS: native habitat phase over all 65536 play ticks and both happiness signs");
 puts("PASS: 589828 exhaustive live-value/flag/baseline cases, both blink halves; B5a geometry, fill and palettes");
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        src=Path(tmp)/'hud.c';exe=Path(tmp)/'hud'
        src.write_text(harness)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Wno-unused-parameter','-fsanitize=undefined','-o',exe,src],check=True)
        subprocess.run([exe],check=True)


if __name__=='__main__':main()
