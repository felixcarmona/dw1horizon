#!/usr/bin/env python3
"""Run the actual food sickness handler with translated suffixes under ASan."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def function(source, signature):
    start = source.index(signature)
    at = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[at] == '{') - (source[at] == '}')
        at += 1
    return source[start:at]


def check(tree):
    handler = function((tree / 'src/main/item.c').read_text(), 'void handleItemSickness(int16_t chance)')
    code = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define VERSION_IS(v) 1
#define CONDITION_SICK 64
#define CONDITION_INJURED 32
#define MOD_CARE_FOOD_SICK_DIE 0
#define FIT_VANILLA 0
struct { int condition, timesBeingSick, sicknessTimer, injuryTimer; } PARTNER_PARA;
struct { char name[20]; } PARTNER_ENTITY;
char *STR_IS_SICK, NAME_FORMAT[]="%s", drawn[256];
int state, color, cursor;
int careDie(int slot) { return 100; }
int randomLimit(int limit) { return 0; }
void tamerSetState(int n) { state=n; }
void clearTextArea(void) { drawn[0]=0;cursor=0; }
void setTextColor(int n) { color=n; }
void drawString(char *s,int x,int y) {
 assert(x==cursor && y==120);
 strcat(drawn,s); cursor+=(int)strlen(s)*6;
}
int drawStringMode(char *s,int x,int y,int mode) {
 drawString(s,x,y);return (int)strlen(s)*6;
}
'''
    code += handler
    code += r'''
int main(int argc,char **argv) {
 char expected[256];
 STR_IS_SICK=argv[1];
 for(int n=1;n<=19;n++) {
  memset(PARTNER_ENTITY.name,'A',n);PARTNER_ENTITY.name[n]=0;
  memset(&PARTNER_PARA,0,sizeof(PARTNER_PARA));
  PARTNER_PARA.condition=CONDITION_INJURED;PARTNER_PARA.injuryTimer=123;
  handleItemSickness(100);
  snprintf(expected,sizeof(expected),"%s%s",PARTNER_ENTITY.name,STR_IS_SICK);
  assert(strcmp(drawn,expected)==0 && color==10 && state==20);
  assert(PARTNER_PARA.condition==CONDITION_SICK && PARTNER_PARA.timesBeingSick==1);
  assert(PARTNER_PARA.sicknessTimer==1 && PARTNER_PARA.injuryTimer==0);
  handleItemSickness(100); assert(PARTNER_PARA.timesBeingSick==1);
  memset(&PARTNER_PARA,0,sizeof(PARTNER_PARA));handleItemSickness(0);
  assert(PARTNER_PARA.condition==0);
 }
 return 0;
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / 'handler.c', Path(tmp) / 'handler'
        src.write_text(code)
        subprocess.run(['cc', '-std=c99', '-g', '-fsanitize=address', '-fno-omit-frame-pointer', str(src), '-o', str(exe)], check=True)
        for lang in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
            suffix = json.loads((ROOT / 'text' / lang / 'names.json').read_text())['main.STR_IS_SICK']
            subprocess.run([str(exe), suffix], check=True)
            print(f'PASS {lang}: names 1..19, sickness, injury replacement, already sick and no sickness')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=ROOT / 'build/decomp-dev')
    check(parser.parse_args().tree)
