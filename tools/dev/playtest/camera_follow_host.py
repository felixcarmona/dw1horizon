#!/usr/bin/env python3
"""Compare actual camera C against the pre-0286 source with a host projection stub.

Usage: python3 tools/dev/playtest/camera_follow_host.py BASE/map.c NEW/map.c
Real projection, map streaming and interpolation still require emulator checks.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

PREFIX = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct { int16_t vx, vy, vz, pad; } SVECTOR;
typedef struct { int16_t vx, vy; } DVECTOR;
typedef struct { int32_t vx, vy, vz; } VECTOR;
typedef struct { VECTOR location; } Pos;
typedef struct { int type, isOnMap; Pos *posData; } Entity;
struct { Entity entity; } TAMER_ENTITY;
struct { struct { Entity entity; } digimonEntity; } PARTNER_ENTITY;
struct { int height; } para[2];
#define DIGI_PARA(t) para[t]
int GAME_STATE, CAMERA_FOLLOW_PLAYER, CAMERA_HAS_TARGET, IS_SCRIPT_PAUSED, IS_IN_MENU;
int POLLED_INPUT, GsWSMATRIX, state, tiles, battles;
struct { int16_t cameraX, cameraY; } MAP_TILE_DATA;
VECTOR STORED_TAMER_POS;
SVECTOR projected;
void copyVector(SVECTOR *a, VECTOR *b) { a->vx=b->vx; a->vy=b->vy; a->vz=b->vz; }
#define SetRotMatrix(x) ((void)0)
#define SetTransMatrix(x) ((void)0)
#define gte_ldv0(x) (projected=*(x))
#define gte_rtps() ((void)0)
#define gte_stsxy(x) do { (x)->vx=projected.vx/10; (x)->vy=(projected.vy+projected.vz)/10; } while(0)
int tamerGetState(void) { return state; }
void updateDrawingOffsets(DVECTOR *a, DVECTOR *b) { (void)a; (void)b; }
void handleTileUpdate(int a, int b) { (void)a; (void)b; tiles++; }
void modCamBattleStep(void) { battles++; }
'''
MAIN = r'''
int main(int argc, char **argv) {
    Pos t={{100,0,100}}, p={{0,0,0}};
    TAMER_ENTITY.entity=(Entity){0,1,&t};
    PARTNER_ENTITY.digimonEntity.entity=(Entity){1,1,&p};
    para[0].height=150; para[1].height=atoi(argv[1]);
    CAMERA_FOLLOW_PLAYER=IS_SCRIPT_PAUSED=1;
    if (argc>2 && strcmp(argv[2],"battle")==0) {
        GAME_STATE=1;
        for(int dx=-20000;dx<=20000;dx+=500) for(int dz=-20000;dz<=20000;dz+=500) {
            p.location=(VECTOR){dx,0,dz}; DVECTOR target; modCamTarget(&target);
            fwrite(&target,sizeof(target),1,stdout);
        }
        return 0;
    }
    if (argc>2) {
        /* Deterministic walking, stale stored position during idle, then caught up. */
        p.location=(VECTOR){-5000,0,5000};
        STORED_TAMER_POS=(VECTOR){80,0,80};
        POLLED_INPUT=0x2000;
        for(int i=0;i<80;i++) tickCameraFollowPlayer();
        printf("stop %d %d\n", MOD_CAM_SHIFT.vx,MOD_CAM_SHIFT.vy);
        POLLED_INPUT=0; p.location=t.location;
        for(int i=0;i<100;i++) tickCameraFollowPlayer();
        DVECTOR want; modCamTarget(&want);
        printf("idle %d %d target %d %d\n",MOD_CAM_SHIFT.vx,MOD_CAM_SHIFT.vy,want.vx,want.vy);
        int x=MAP_TILE_DATA.cameraX, y=MAP_TILE_DATA.cameraY;
        for(int i=0;i<100;i++) tickCameraFollowPlayer();
        if (MAP_TILE_DATA.cameraX!=x || MAP_TILE_DATA.cameraY!=y) return 2;
        /* No idle camera change during a scene, menu, pan, disabled follow or non-idle tamer. */
        int *guards[]={&IS_SCRIPT_PAUSED,&IS_IN_MENU,&CAMERA_HAS_TARGET,&CAMERA_FOLLOW_PLAYER,&state};
        int values[]={0,1,1,0,1};
        for(int i=0;i<5;i++) {
            int old=*guards[i]; *guards[i]=values[i]; MOD_CAM_SHIFT=(DVECTOR){20,20};
            tickCameraFollowPlayer();
            if(MOD_CAM_SHIFT.vx!=20 || MOD_CAM_SHIFT.vy!=20) return 3;
            *guards[i]=old;
        }
        return 0;
    }
    /* Byte comparison across inputs, heights, shifts, states and partner positions. */
    for(int mask=0;mask<16;mask++) for(int dx=-5000;dx<=5000;dx+=1000)
    for(int dy=-5000;dy<=5000;dy+=1000) for(int g=0;g<4;g++) {
        POLLED_INPUT=mask<<12; GAME_STATE=g; p.location=(VECTOR){dx,0,dy};
        STORED_TAMER_POS=(VECTOR){80,0,80};
        MOD_CAM_SHIFT=(DVECTOR){0,0}; MAP_TILE_DATA.cameraX=MAP_TILE_DATA.cameraY=100;
        tiles=battles=0;
        tickCameraFollowPlayer();
        int16_t result[]={MOD_CAM_SHIFT.vx,MOD_CAM_SHIFT.vy,MAP_TILE_DATA.cameraX,MAP_TILE_DATA.cameraY,tiles,battles};
        fwrite(result,sizeof(result),1,stdout);
    }
    return 0;
}
'''


def source(path):
    s = Path(path).read_text()
    block = s[s.index('typedef struct {', s.index('MOD (camera): big partners')):s.index('extern int32_t IS_IN_MENU;', s.index('MOD (camera): big partners'))]
    start = s.index('void tickCameraFollowPlayer(void)\n{')
    follow = s[start:s.index('\n// clang-format off', start)]
    return PREFIX + block + follow + MAIN


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('baseline')
    ap.add_argument('current')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        bins=[]
        for i, path in enumerate((a.baseline, a.current)):
            c=Path(tmp)/f'camera{i}.c'; c.write_text(source(path))
            exe=c.with_suffix('')
            subprocess.run(['cc','-std=c99','-O2',str(c),'-o',str(exe)],check=True)
            bins.append(str(exe))
        for height in (0,150,250,450):
            out=[subprocess.check_output([exe,str(height)]) for exe in bins]
            assert out[0]==out[1], f'small partner height {height} changed'
            print(f'height {height}: {len(out[0])} identical output bytes (7,744 cases)')
        for height in (451,653,1000):
            battle=[subprocess.check_output([exe,str(height),'battle']) for exe in bins]
            assert battle[0]==battle[1], f'battle target changed at height {height}'
            print(f'height {height}: {len(battle[0])} identical battle-target bytes (6,561 positions)')
            old=subprocess.check_output([bins[0],str(height),'idle']).decode()
            new=subprocess.check_output([bins[1],str(height),'idle']).decode()
            print(f'height {height}: baseline {old.strip()!r}; fixed {new.strip()!r}')
            line=new.splitlines()[1].split()
            assert line[1:3]==line[4:6], 'idle did not settle'
            stop=list(map(int,new.splitlines()[0].split()[1:]))
            assert abs(stop[0])<=24 and -64<=stop[1]<=24
        print('PASS: small-partner bytes, bounded framing, idle settling, no stale delta, scene/menu/pan guards')


if __name__ == '__main__':
    main()
