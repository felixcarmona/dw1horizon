#!/usr/bin/env python3
"""Compile the real food-sickness handler with ASan and exercise translated text.

The harness substitutes renderer/care services and supplies valid maximum-sized
name fields. The handler body is extracted unchanged from the prepared C tree.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree',type=Path,required=True)
    a=p.parse_args()
    source=(a.tree/'src/main/item.c').read_text()
    start=source.index('void handleItemSickness(int16_t chance)\n{')
    end=source.index('\n}',start)+2
    handler=source[start:end]
    # Each script glyph uses at most two bytes. Embedded colour codes are not
    # present in these suffixes, so this covers their complete encoded storage.
    suffixes=[]
    for language in ['ours','es','pt-br','fr','de','it','ja','ca','zh-hans']:
        text=json.loads((ROOT/'text'/language/'names.json').read_text())['main.STR_IS_SICK']
        suffixes.append((language,len(text)*2))
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define VERSION_IS(x) 1
#define CONDITION_SICK 64
#define CONDITION_INJURED 32
#define MOD_CARE_FOOD_SICK_DIE 0
#define FIT_VANILLA 0
struct { int condition,timesBeingSick,sicknessTimer,injuryTimer; } PARTNER_PARA;
struct { char name[20]; } PARTNER_ENTITY;
char *STR_IS_SICK, *NAME_FORMAT="%s";
static char drawn[256];
static int name_width;
int careDie(int k) { return 100; }
int randomLimit(int n) { return 0; }
void tamerSetState(int s) {}
void clearTextArea(void) { drawn[0]=0; }
void setTextColor(int c) {}
int drawStringMode(char *s,int x,int y,int mode) {
 assert(x==0);strcat(drawn,s);name_width=strlen(s)*6;return name_width;
}
void drawString(char *s,int x,int y) { assert(x==0 || x==name_width);strcat(drawn,s); }
'''+handler+r'''
int main(int argc,char **argv) {
 char suffix[128],expected[256];
 int n=0;sscanf(argv[1],"%d",&n);memset(suffix,'s',n);suffix[n]=0;STR_IS_SICK=suffix;
 for(int len=1;len<=19;len++) {
  memset(PARTNER_ENTITY.name,'n',len);PARTNER_ENTITY.name[len]=0;
  for(int injured=0;injured<=1;injured++) {
   memset(&PARTNER_PARA,0,sizeof(PARTNER_PARA));PARTNER_PARA.condition=injured*32;
   PARTNER_PARA.injuryTimer=injured;
   handleItemSickness(100);
   assert(PARTNER_PARA.condition==64 && PARTNER_PARA.timesBeingSick==1);
   assert(PARTNER_PARA.sicknessTimer==1 && PARTNER_PARA.injuryTimer==0);
   sprintf(expected,"%s%s",PARTNER_ENTITY.name,suffix);assert(!strcmp(drawn,expected));
   handleItemSickness(100);assert(PARTNER_PARA.timesBeingSick==1);
  }
  memset(&PARTNER_PARA,0,sizeof(PARTNER_PARA));handleItemSickness(0);
  assert(PARTNER_PARA.condition==0);
 }
 return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='food-sickness-') as tmp:
        path=Path(tmp);(path/'test.c').write_text(code)
        subprocess.run(['cc','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                        str(path/'test.c'),'-o',str(path/'test')],check=True)
        for language,size in suffixes:
            subprocess.run([str(path/'test'),str(size)],check=True)
            print(f'PASS {language}: suffix {size} bytes, name lengths 1..19, injury and illness transitions')

if __name__=='__main__':main()
