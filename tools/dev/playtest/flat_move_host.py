#!/usr/bin/env python3
"""Check the real animation-to-technique lookup, including the flattened spit.

Usage: python3 tools/dev/playtest/flat_move_host.py PREPARED_DECOMP/src/main/utils2.c [--before]
"""
from pathlib import Path
import subprocess,sys,tempfile
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools').is_dir())
source=Path(sys.argv[1]).read_text();a=source.index('uint8_t entityGetTechFromAnim(Entity *e, uint8_t anim)\n{');b=source.index('\nvoid entityLookAtTile',a)
source=source[a:b];before='--before' in sys.argv[2:]
h=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef struct {int type;int8_t flatSprite;} Entity;
struct {uint8_t prefix[46],moves[16];} params[61];
#define DIGI_PARA(t) params[t]
'''
t=r'''
int main(void){
 Entity e={1,-1};memset(params,86,sizeof(params));
 for(int i=0;i<16;i++)params[1].moves[i]=i+1;
 for(int i=0;i<16;i++)assert(entityGetTechFromAnim(&e,46+i)==i+1);
 assert(entityGetTechFromAnim(&e,255)==255);
 for(int f=0;f<4;f++){
  e.flatSprite=f;uint8_t move=entityGetTechFromAnim(&e,0);
  assert(move==(BEFORE?86:121));assert((move>=58&&move<113)==BEFORE);
 }
 if(!BEFORE){
  e.flatSprite=-1;
  for(int i=0;i<46;i++)assert(entityGetTechFromAnim(&e,i)==255);
  for(int i=62;i<256;i++)assert(entityGetTechFromAnim(&e,i)==255);
  e.flatSprite=4;assert(entityGetTechFromAnim(&e,0)==255);
 }
 e.type=60;assert(entityGetTechFromAnim(&e,60)==112);
}
'''
(ROOT/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
 p=Path(tmp);(p/'check.c').write_text('#define BEFORE '+str(int(before))+'\n'+h+source+t)
 subprocess.run(['cc','-std=c99',str(p/'check.c'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True)
print('pass: flat spit, all sixteen move slots, invalid animation IDs, special finisher')
