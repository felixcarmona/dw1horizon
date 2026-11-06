#!/usr/bin/env python3
"""Check Chinese list headers, numeric fields and row recycling using the actual C.

Usage: python3 tools/dev/playtest/chinese_lists_host.py PREPARED_DECOMP
The GPU stubs retain glyph widths and full/half text-slot geometry.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

def function(source, name):
    at = source.index('void '+name+'(')
    # Ignore forward declarations.
    while ';' in source[at:source.index('{',at)]:
        at = source.index('void '+name+'(',at+1)
    end=source.index('{',at)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[at:end]

def check(tree):
    menu=(tree/'src/shop/script_menu.c').read_text()
    common=(tree/'src/main/script_common.c').read_text()
    textbox=(tree/'src/main/script_textbox.c').read_text()
    code=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define VERSION_IS(x) 1
#define MOD_LANG_ZH 8
#define FIT_VANILLA 0
#define ITEM_FIELD_W 96
#define FONT_SWITCH 0
#define TEXT_FIT_TIGHT 0x10
#define TEXT_FIT_CONDENSED 0x11
#define DRAW_STRING2_SPACE_WIDTH 4
#define CLEAR_FROM_PEN(x,y,w) clearFromPenTest(x,y,w)
typedef struct {int x,y,w,h;} RECT;
#define setRECT(r,a,b,c,d) ((r)->x=(a),(r)->y=(b),(r)->w=(c),(r)->h=(d))
int FONT_CELLS, DRAW_STRING2_IS_FIXED_WIDTH, rewardX;
int closeStart=-1,closeEnd,clipped,countX;
void clearFromPenTest(int x,int y,int w){int a=(x+3)&~3;if(closeStart>=0 && a<closeEnd && x+w>closeStart)clipped=1;}
int clearCalls;RECT cleared;
void clearTextSubArea(RECT *r){clearCalls++;cleared=*r;}
void setTextColor(int n){}
int isAsciiEncoded(const char *s){return !((uint8_t)*s&128);}
int swapShortBytes(int n){return (n>>8)|((n&255)<<8);}
int convertAsciiToJis(int n){return n==32?0x8140:n;}
int drawGlyph(int cp,int x,int y){
 if(cp==0x43a0)rewardX=x;
 if(cp==0x2900){closeStart=x;closeEnd=x+5;}
 if(cp==0x3500)countX=x;
 return cp==0x2800 || cp==0x2900 || cp==0x3500 ? 6:12;
}
int16_t drawString2Fit(uint8_t **s,int16_t x,int16_t y,int16_t pos,int code){return pos;}
#define TEXT_COLUMN 0x12
int MOD_LANG, ITEM_MENU_TYPE;
typedef struct { int writeCount,backPage,doubleBuffered,vramRows,vramMode; } TestTextBox;
typedef TestTextBox TextBoxData;
struct { TestTextBox box[4]; } TEXTBOX_DATA;
uint8_t lines[2048],*TEXTBOX_LINES_PTR=lines;
typedef struct { uint8_t buf[6]; int topRow,boxId,cursor; uint8_t itemRow[8]; } ItemMenuBox;
ItemMenuBox left,right,*ITEM_MENU_LEFT=&left,*ITEM_MENU_RIGHT=&right;
uint8_t row[64];
char *names[]={"\xa0\x40\xa0\x41\xa0\x42", "\xa0\x43\xa0\x44"};
#define ITEM_NAME(x) names[x]
int isTriggerSet(int n){return 0;}
int measureStringMode(char *s,int mode){return (int)strlen(s)*6;}
int textFitCode(char *s,int width){return 1;}
uint8_t *getTextboxLine(ItemMenuBox *b,uint8_t n){return row;}
uint8_t *padWithSpaces(uint8_t *p,int width,int used){for(int n=width-used/2;n>0;n--){*p++=0x81;*p++=0x40;}return p;}
void terminateString(uint8_t *p,int last){*p++=1;*p++=1;*p++=last?0:13;*p=0;}
void showMapHeadTextbox(int idx,int owner,int box,int section){
 /* Chinese translated headers can terminate before the native byte offset. */
 int x=box==2?32:0;
 int a=9*64+x,b=(idx==15?13:15)*64+x;
 const char *header=MOD_LANG==MOD_LANG_ZH?"\xa0\x40":"ABCDEFGHIJKLMNOPQRSTUVWXYZ";
 strcpy((char *)lines+a,header);strcpy((char *)lines+b,header);
 TEXTBOX_DATA.box[box].writeCount++;
}
void updateItemMenuStrings(ItemMenuBox *b,int start,int style){}
void calculateItemMenuStrings(ItemMenuBox *b,uint8_t row,int last){}
void calculateCardMenuStrings(ItemMenuBox *b,uint8_t row,int last){}
void calculateMusicMenuStrings(ItemMenuBox *b,uint8_t row,int last){}
void calculateBirdramonMenuStrings(ItemMenuBox *b,uint8_t row,int last){}
void getVRAMModeCoords(int mode,int *x,int *w){*x=mode==2?128:0;*w=mode?127:255;}
'''
    a=textbox.index('#if !VERSION_IS(US)\nint32_t drawString2(')
    b=textbox.index('// clang-format off',a)
    code+=textbox[a:b]
    code+='\n'.join(function(menu,n) for n in ('updateKeeperTextbox','updateMojyaTradeStrings'))
    code+=function(common,'calculateItemListStrings')
    code+=function(common,'updateItemMenuLine')
    code+=r'''
int main(void){
 for(MOD_LANG=0;MOD_LANG<=8;MOD_LANG++){
  memset(lines,0,sizeof lines);updateMojyaTradeStrings();
  assert(drawString2(lines+0x240,0,0,1)==0);
  assert(drawString2(lines+0x340,0,0,1)==0);
  if(MOD_LANG!=8){assert(lines[0x254]==13);assert(lines[0x354]==13);assert(lines[0x240]=='A');}
  for(int side=0;side<2;side++){
   memset(lines,0,sizeof lines);updateKeeperTextbox(side);
   int a=side?0x260:0x240,b=side?0x3e0:0x3c0;
   assert(drawString2(lines+a,0,0,1)==0);
   assert(drawString2(lines+b,128,0,1)==0);
   if(MOD_LANG!=8){assert(lines[a+6]==13);assert(lines[b+6]==13);assert(lines[a]=='A');}
  }
  memset(row,0,sizeof row);left.buf[0]=0x80;right.buf[0]=1;
  calculateItemListStrings(&left,0,1);
  int column=0;
  for(int i=0;i<63;i++)if(row[i]==TEXT_COLUMN&&row[i+1]==0x72)column++;
  assert(column==(MOD_LANG==8));
  rewardX=-1;assert(drawString2(row,0,12,1)==1);
  if(MOD_LANG==8)assert(rewardX==114);
  else assert(rewardX>=0 && rewardX<114);
 }
 MOD_LANG=8;
 uint8_t card[]={1,1,0xa0,0x40,0xa0,0x41,0xa0,0x42,0xa0,0x43,0xa0,0x44,' ','(',0xa0,0x45,0xa0,0x46,0xa0,0x47,')',0x17,0,15,0,'5',0};
 closeStart=-1;clipped=0;countX=-1;
 assert(drawString2(card,0,0,1)==1);
 assert(!clipped && countX==118);
 for(MOD_LANG=0;MOD_LANG<=8;MOD_LANG++)for(int mode=0;mode<3;mode++){
  left.boxId=1;left.cursor=0;left.itemRow[0]=14;
  TEXTBOX_DATA.box[1]=(TestTextBox){.backPage=1,.doubleBuffered=1,.vramRows=6,.vramMode=mode};
  clearCalls=0;updateItemMenuLine(&left,0);
  assert(clearCalls==(MOD_LANG==8));
  if(MOD_LANG==8){assert(cleared.x==(mode==2?128:0));assert(cleared.y==240);assert(cleared.w==(mode?128:256));assert(cleared.h==12);}
 }
 puts("PASS: Chinese headers chain both pages even with short labels; trade fields use column 114; longest Chinese card name survives the count-column clear; recycled Chinese rows clear exactly their full/half slot; eight other languages retain native headers and spacing");
}
'''
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp);(p/'check.c').write_text(code)
        subprocess.run(['cc','-std=c99','-Wall','-Werror','-Wno-pointer-sign',str(p/'check.c'),'-o',str(p/'check')],check=True)
        subprocess.run([str(p/'check')],check=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('tree',type=Path);check(ap.parse_args().tree)
