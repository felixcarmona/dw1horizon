#!/usr/bin/env python3
"""Compile the actual scripted-translation C and sweep endpoint remainders.

Run on a prepared decomp tree; --expect-stalls records the pre-fix behavior.
This isolates movement arithmetic. Live scene checks remain necessary.
"""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('tree', type=Path)
parser.add_argument('--out', type=Path, default=Path('build/script-move-host'))
parser.add_argument('--expect-stalls', action='store_true')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
p = (args.tree / 'src/main/tamer.c').read_text()
a=p.index('int32_t tickEntityMoveTo(scriptId1');b=p.index('\nEntity *getEntityFromScriptId',a)
functions=p[a:b]
prefix=r'''
#include <stdint.h>
#include <stdio.h>
typedef struct {long vx,vy,vz,pad;} VECTOR;
typedef struct { VECTOR location; } PositionData;
typedef struct { PositionData *posData; } Entity;
PositionData pos;Entity ent={&pos};
int8_t PREVIOUS_CAMERA_POS_INITIALIZED;
int16_t MOVE_TO_DELTA_X,MOVE_TO_DELTA_Z;
VECTOR PREVIOUS_CAMERA_POS;
Entity *getEntityFromScriptId(uint8_t *id) {return &ent;}
void setEntityPosition(int id,long x,long y,long z) {pos.location=(VECTOR){x,y,z,0};}
void setupEntityMatrix(int id) {}
void moveCameraByDiff(VECTOR *a,VECTOR *b) {}
'''
main=r'''
int main(void) {
 int failed=0,total=0;
 for(int dx=-39;dx<=39;dx++)for(int dz=-39;dz<=39;dz++) {
  pos.location=(VECTOR){-4562-dx,0,41-dz,0};PREVIOUS_CAMERA_POS_INITIALIZED=0;
  int done=0;
  for(int i=0;i<100&&!done;i++)done=tickEntityMoveTo(10,255,-4562,41,20,0);
  total++;if(!done||pos.location.vx!=-4562||pos.location.vz!=41)failed++;
 }
 printf("plane total=%d failed=%d\n",total,failed);
 for(int axis=0;axis<3;axis++) {
  int bad=0;
  for(int d=-39;d<=39;d++) {
   pos.location=(VECTOR){0,0,0,0};((long*)&pos.location)[axis]=-d;PREVIOUS_CAMERA_POS_INITIALIZED=0;
   int done=0;for(int i=0;i<100&&!done;i++)done=tickEntityMoveToAxis(10,0,axis,20,0);
   if(!done||((long*)&pos.location)[axis]!=0)bad++;
  }
  printf("axis %d total=79 failed=%d\n",axis,bad);failed+=bad;
 }
 return failed?1:0;
}
'''
source = args.out / 'move.c'
binary = args.out / 'move'
source.write_text(prefix + functions + main)
subprocess.run(['cc', '-std=gnu99', '-Wno-implicit-int', str(source), '-o', str(binary)], check=True)
result = subprocess.run([str(binary.resolve())], capture_output=True, text=True)
(args.out / 'result.txt').write_text(result.stdout + result.stderr)
print(result.stdout, end='')
raise SystemExit(0 if result.returncode == int(args.expect_stalls) else 1)
