#!/usr/bin/env python3
"""Sweep the actual walk-wait C with disc model travel and model travel.

python3 tools/dev/playtest/partner_walk_host.py TREE BUILD --out build/walk-host

This isolates arrival/deadline logic. It does not emulate map loading, scripts,
collision geometry or rendering. Run the emulator checks separately.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import animsheet
import mmd
import species
import coldsplit

PREFIX = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
typedef struct { int32_t vx,vy,vz,pad; } VECTOR;
typedef struct { int16_t vx,vy,vz,pad; } SVECTOR;
typedef struct { VECTOR location,scale; SVECTOR rotation; } PositionData;
typedef struct { int16_t delta[9]; int8_t subValue[9]; } MomentumData;
typedef struct { MomentumData *momentum; int32_t locX,locY,locZ; unsigned char animFlag; } EntityAnim;
typedef struct { PositionData *posData; EntityAnim anim; } Entity;
Entity entities[3],*ENTITY_TABLE[]={&entities[0],&entities[1],&entities[2]};
int NPC_IS_WALKING_TOWARDS[8],PREVIOUS_CAMERA_POS_INITIALIZED;
int32_t MOD_FPS_TICKS;
int16_t CURRENT_SCREEN;
VECTOR PREVIOUS_CAMERA_POS;
static int collision=-1,cameraMoves;
Entity *getEntityFromScriptId(uint8_t *id) {
    if(*id==0xfc) *id=1; else if(*id==0xfd) *id=0; else *id=2;
    return ENTITY_TABLE[*id];
}
void getModelTile(VECTOR *p,int16_t *x,int16_t *z) {
    *x=p->vx/100+50-(p->vx<0); *z=50-p->vz/100-(p->vz>0);
}
void entityLookAtLocation(Entity *e,VECTOR *t) {
    e->posData->rotation.vy=(int)(atan2(t->vx-e->posData->location.vx,t->vz-e->posData->location.vz)*4096/(2*M_PI));
}
void moveCameraByDiff(VECTOR *a,VECTOR *b) { (void)a;(void)b;cameraMoves++; }
int entityCheckCollision(int a,Entity *e,int b,int c) { (void)a;(void)e;(void)b;(void)c;return collision; }
void setEntityPosition(int id,int x,int y,int z) {
    Entity *e=ENTITY_TABLE[id]; e->posData->location=(VECTOR){x,y,z,0};
    e->anim.locX=x*32768; e->anim.locY=y*32768; e->anim.locZ=z*32768;
}
void setupEntityMatrix(int id) { (void)id; }
'''

MAIN = r'''
int main(int argc,char **argv) {
    FILE *f=fopen(argv[1],"rb"); if(!f) return 2;
    PositionData pos[3]={0}; MomentumData momentum[3]={0};
    for(int i=0;i<3;i++) { entities[i].posData=&pos[i]; entities[i].anim.momentum=&momentum[i];pos[i].scale=(VECTOR){4096,4096,4096,0}; }
    int32_t models,ntargets; if(fread(&models,4,1,f)!=1 || fread(&ntargets,4,1,f)!=1) return 2;
    int16_t targets[32][4]; if(ntargets>32) return 3;
    if(fread(targets,8,ntargets,f)!=(size_t)ntargets) return 2;
    int runs=0,failed=0,maxTicks=0; int fixed=argc>2;
    for(int model=0;model<models;model++) {
        int32_t id,n; if(fread(&id,4,1,f)!=1 || fread(&n,4,1,f)!=1) return 2;
        int16_t speeds[601];if(n>601 || n<1) return 4; if(fread(speeds,2,n,f)!=(size_t)n) return 2;
        int modelFailed=0,modelMax=0;
        for(int target=0;target<ntargets;target++) for(int start=0;start<30;start++) {
            double a=(start*701%4096)*2*M_PI/4096, angle=(start%10)*2*M_PI/10;
            int radius=250+125*(start/10),leg=0,done=0,tick;
            setEntityPosition(1,targets[target][0]+(int)(radius*cos(angle)),0,targets[target][1]+(int)(radius*sin(angle)));
            double matrix=a;
            for(tick=0;tick<2100;tick++) {
                MOD_FPS_TICKS++;
                int ix=leg==1?2:0, tx=targets[target][ix],tz=targets[target][ix+1];
                int speed=speeds[tick%n]; momentum[1].delta[8]=-speed;
                if(tickEntityWalkTo(0xfc,0xff,tx,tz,0)) {
                    leg++; if(leg==3) { done=1;break; }
                }
                Entity *e=&entities[1];
                /* tickMomentum rebuilds the facing matrix before applying root
                 * travel. Keep the engine's 15 fractional bits. */
                matrix=e->posData->rotation.vy*2*M_PI/4096;
                e->anim.locX+=(int32_t)(sin(matrix)*speed*32768);
                e->anim.locZ+=(int32_t)(cos(matrix)*speed*32768);
                e->posData->location.vx=e->anim.locX>>15;
                e->posData->location.vz=e->anim.locZ>>15;
                matrix=e->posData->rotation.vy*2*M_PI/4096;
            }
            runs++; if(!done) {
                failed++;modelFailed++;
                printf("stall model %d toilet %d start %d leg %d x %d z %d\n",id,target+1,start,leg,pos[1].location.vx,pos[1].location.vz);
            }
            if(tick>maxTicks) maxTicks=tick;if(tick>modelMax) modelMax=tick;
        }
        printf("model %d runs %d failed %d max_ticks %d\n",id,ntargets*30,modelFailed,modelMax);
    }
    if(fixed) {
        /* No progress, a zero-speed clip, repeated calls in one tick, a moving
         * entity target, changed destinations/screens, and an interrupted walk. */
        for(int kind=0;kind<6;kind++) {
            MOD_FPS_TICKS+=2; setEntityPosition(1,0,0,0);
            momentum[1].delta[8]=0; int done=0;
            for(int t=1;t<=600;t++) {
                MOD_FPS_TICKS++;
                int target=kind==1?0xfd:0xff;
                setEntityPosition(0,5000+t,0,5000);
                int x=5000,z=5000;
                if(kind==2 && t==300) x=4000;
                if(kind==3 && t==300) CURRENT_SCREEN++;
                if(kind==4 && t==300) MOD_FPS_TICKS+=2;
                if(kind==2 && t>300) x=4000;
                done=tickEntityWalkTo(0xfc,target,x,z,0);
                if(kind==5 && !done && tickEntityWalkTo(0xfc,target,x,z,0)) return 6;
                if(done && t!=600) return 7;
            }
            if(kind==2 || kind==3 || kind==4) {
                if(done) return 8;
                int t=0;
                while(!done && t++<300) {
                    MOD_FPS_TICKS++;
                    done=tickEntityWalkTo(0xfc,0xff,kind==2?4000:5000,5000,0);
                }
                if(!done || t!=299) return 9;
            } else if(!done) return 10;
        }
        /* Partner-only watchdog: neither another actor nor camera bookkeeping
         * can borrow it. Original entity-collision completion still works. */
        setEntityPosition(0,0,0,0);
        for(int t=0;t<700;t++) {
            MOD_FPS_TICKS++;
            if(tickEntityWalkTo(0xfd,0xff,5000,5000,1)) return 11;
        }
        collision=5;
        if(!tickEntityWalkTo(0xfd,0xfc,0,0,1) || PREVIOUS_CAMERA_POS_INITIALIZED) return 12;
        puts("PASS: deadline, moving target, reset, duplicate poll, actor isolation, camera and collision");
    }
    printf("TOTAL models %d runs %d failed %d max_ticks %d\n",models,runs,failed,maxTicks);
    if(fixed && failed) return 5;
    return 0;
}
'''


def walk_source(tree):
    text = (tree / 'src/main/tamer.c').read_text()
    start = text.index('int32_t tickEntityWalkTo(scriptId, targetId, x, z, useCamera)')
    start = text.rfind('// clang-format off', 0, start)
    helper = text.find('/* MOD (partner walk):')
    if helper >= 0:
        start = helper
    return text[start:text.index('\nint32_t tickLookAtEntity(', start)]


def main():
    import struct
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('tree', type=Path)
    ap.add_argument('build', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--expect-fixed', action='store_true')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    data, _, records = species.read_archive(a.build / 'DIGI.DAT')
    rows = []
    definitions = {s['id']: s for p in (a.build / 'species').glob('*.json')
                   for s in [json.loads(p.read_text())]}
    native = {p.stem.upper(): p for p in (ROOT / 'extracted/CHDAT').rglob('*.MMD')}
    for r in records:
        if not r['flags'] & species.FLAG_PARTNER:
            continue
        nb = r['para']['boneCount']
        if r['modelSize']:
            off = r['modelSector'] * 2048
            raw = data[off:off + r['modelSize']]
            if coldsplit.is_split(raw):
                cold = off + ((r['modelSize'] + 2047) // 2048) * 2048
                raw = coldsplit.join(raw, data[cold:cold + coldsplit.cold_length(raw)], nb, coldsplit.table_length(raw))
        else:
            raw = native[r['modelName'].upper()].read_bytes()
        # Eight CHDAT replacements plus the three partner-only native files.
        # Raw extracted NPC models are not the models these partners load.
        spec = definitions.get(r['id'], {})
        model_file = spec.get('model', {}).get('partner_file') or spec.get('model', {}).get('file')
        override = a.build / 'models' / Path(model_file or '').name
        if model_file and override.is_file():
            raw = override.read_bytes()
        model = mmd.MMD.parse(raw, nb)
        if model.anims.table[4] is None:
            # startAnimation ignores a missing slot. From idle this has no travel.
            deltas = [0]
        else:
            frames, loop, _ = animsheet.slot_frames(model, nb, 4)
            roots = [f[0][8] for f in frames]
            deltas = [round(abs(roots[i] - roots[i-1])) for i in range(1, len(roots))] or [0]
        rows.append(dict(id=r['id'], name=r['para']['name'], radius=r['para']['radius'],
                         speed=sum(deltas)/len(deltas), peak=max(deltas), deltas=deltas,
                         toilet_clip=model.anims.table[10] is not None))
    targets = json.loads((ROOT / 'content/tables/toilets.json').read_text())['toilets']
    payload = struct.pack('<2i', len(rows), len(targets))
    payload += b''.join(struct.pack('<4h', *t) for t in targets)
    for r in rows:
        ds = r['deltas']
        payload += struct.pack('<2i', r['id'], len(ds)) + struct.pack(f'<{len(ds)}h', *ds)
    (a.out / 'models.bin').write_bytes(payload)
    (a.out / 'models.json').write_text(json.dumps(rows, indent=2) + '\n')
    source = a.out / 'walk.c'
    source.write_text(PREFIX + walk_source(a.tree) + MAIN)
    exe = a.out / 'walk'
    subprocess.run(['cc', '-std=gnu99', '-O2', str(source), '-lm', '-o', str(exe)], check=True)
    with (a.out / 'results.txt').open('w') as f:
        subprocess.run([str(exe), str(a.out / 'models.bin')] + (['fixed'] if a.expect_fixed else []), stdout=f, check=True)
    lines = (a.out / 'results.txt').read_text().splitlines()
    print(lines[-1])
    for label, key, reverse in [('slowest', 'speed', False), ('fastest', 'speed', True), ('largest', 'radius', True)]:
        r = sorted(rows, key=lambda r: r[key], reverse=reverse)[0]
        print(label, {k: v for k, v in r.items() if k != 'deltas'})


if __name__ == '__main__':
    main()
