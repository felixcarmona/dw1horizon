#!/usr/bin/env python3
"""Check actual jukebox row writers and fitted-run decoding against built titles.

Usage: jukebox_host.py PREPARED_DECOMP
Reads generated title headers from PREPARED_DECOMP and its language siblings.
No game text is embedded in this test. Scratch C and binaries stay in build/.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def function(source, signature):
    start = source.index(signature + '\n{')
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def check(tree):
    common = (tree/'src/main/script_common.c').read_text()
    textbox = (tree/'src/main/script_textbox.c').read_text()
    titles = []
    for sibling in sorted(tree.parent.glob(tree.name + '*')):
        header = sibling/'build/us/psx/generated/text/main/script_common.h'
        if header.exists():
            titles += re.findall(r'char STR_BGM_TRACK_\w+\[\] = ("[^"\n]*(?:\\"[^"\n]*)*");', header.read_text())
    if not titles:
        raise ValueError('build at least one language before checking jukebox titles')
    code = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define TEXT_COLUMN 0x12
#define TEXT_FIT_TIGHT 0x10
#define FIT_TIGHT 1
#define FIT_CONDENSED 2
typedef struct {int topRow;uint8_t *buf;} ItemMenuBox;
uint8_t guarded[66];
char *BGM_TRACK_NAMES[1];
int fitCode, selected;
uint8_t *getTextboxLine(ItemMenuBox *b,uint8_t row){return guarded+1;}
int readPStat(int n){return selected;}
int textFitCode(char *s,int w){assert(w==176);return fitCode;}
uint8_t *intToStringSJIS(uint8_t *s,int n,int digits,int pad){
 for(int i=0;i<digits;i++){*s++=0x82;*s++=0x50;}return s;
}
void setTextColor(int c){}
char decoded[64];
int drawStringMode(char *s,int x,int y,int mode){strcpy(decoded,s);return 101;}
'''
    for signature in ['uint8_t *padWithSpaces(uint8_t *str, int32_t width, int32_t used)',
                      'void terminateString(uint8_t *str, int32_t flag)',
                      'void calculateMusicMenuStrings(ItemMenuBox *box, uint8_t row, int32_t isLast)']:
        code += function(common, signature) + '\n'
    code += function(textbox, 'static int16_t drawString2Fit(uint8_t **str, int16_t x, int16_t y, int16_t pos, int32_t code)')
    code += '\nchar *titles[] = {\n' + ',\n'.join(titles) + '\n};\n'
    code += r'''
int main(void){
 uint8_t id=0;ItemMenuBox box={0,&id};
 for(unsigned i=0;i<sizeof(titles)/sizeof(*titles);i++){
  BGM_TRACK_NAMES[0]=titles[i];unsigned n=strlen(titles[i]);
  for(fitCode=1;fitCode<=0x11;fitCode+=(fitCode==1?15:1))
   for(selected=0;selected<2;selected++)for(int last=0;last<2;last++){
    memset(guarded,0xcc,sizeof(guarded));guarded[0]=0xab;guarded[65]=0xba;
    calculateMusicMenuStrings(&box,0,last);
    assert(guarded[0]==0xab && guarded[65]==0xba);
    assert(n+16<=64);
    uint8_t *r=guarded+1;
    assert(r[8]==fitCode && r[9]==(selected==0?6:1));
    assert(!memcmp(r+10,titles[i],n));
    assert(r[10+n]==TEXT_COLUMN && r[11+n]==252);
    assert(r[14+n]==(last?0:13) && r[15+n]==0);
    if(fitCode!=1){
     uint8_t *p=r+9;decoded[0]=0;
     assert(drawString2Fit(&p,0,0,22,fitCode)==124);
     assert(!strcmp(decoded,titles[i]));assert(*p==TEXT_COLUMN);
    }
   }
 }
 printf("PASS: %zu built titles, row guards, highlight, both terminators, full-row clear and both fitted-run modes\n",sizeof(titles)/sizeof(*titles));
}
'''
    root = Path(__file__).resolve().parents[3]
    (root/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jukebox-host-', dir=root/'build') as temp:
        p = Path(temp)
        (p/'check.c').write_text(code)
        subprocess.run(['cc', '-std=c99', '-Werror', '-Wno-pointer-sign', str(p/'check.c'), '-o', str(p/'check')], check=True)
        subprocess.run([str(p/'check')], check=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('tree', type=Path)
    check(ap.parse_args().tree)
