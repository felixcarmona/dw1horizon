#!/usr/bin/env python3
"""Check the actual encounter selector with passive NPCs, wild groups and explicit opponents.

Usage: python3 tools/dev/playtest/passive_encounters_host.py PREPARED_DECOMP/src/main/btl.c [--before]"""
from pathlib import Path
import sys
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path.insert(0, str(ROOT))
import re, subprocess, tempfile, sys
before='--before' in sys.argv[2:]
source=Path(sys.argv[1]).read_text()
a=source.index('int32_t handleBattleStart(id)');b=source.index('\nvoid loadBattleData',a)
func=source[a:b]
# The quick-battle loader's helpers follow this function in patched sources.
func=func[:func.index('\nextern int8_t MOD_LOAD_PUMP')] if '\nextern int8_t MOD_LOAD_PUMP' in func else func
h=r'''
#define VERSION_IS(x) 0
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
typedef struct {int type,isOnMap,isOnScreen;} Entity;
typedef struct {Entity entity;} Digimon;
typedef struct {Digimon digimonEntity; unsigned char autotalk;} NPC;
Entity ents[10],*ENTITY_TABLE[10]; NPC NPC_ENTITIES[8];
struct {Digimon digimonEntity;} PARTNER_ENTITY;
struct {struct {unsigned char entityIds[4];int unk4;} player;} combat,*COMBAT_DATA_PTR=&combat;
struct {int size;struct{unsigned char array[30];}types;} INVENTORY;
struct {int type;} params[512];
#define DIGI_PARA(x) params[x]
#define DIGIMON_DATA params
int FLEE_DISABLED[1],IS_PREDEFINED_BATTLE,predefined,escape;
unsigned char ps[256];int bubbles[10];int FLEE_CHANCES[9]={100,100,100,100,100,100,100,100,100};
int isTriggerSet(int n){return escape;}
int readPStat(int n){return ps[n];}
void setFleeBubble(int n,int value){bubbles[n]=value;}
int isInvisible(Entity *e){return !e||!e->isOnMap;}
int isScreenConcave(void){return 0;}
void getEntityTile(Entity *e,int8_t*x,int8_t*y){*x=*y=0;}
int isLinearPathBlocked(int a,int b,int c,int d){return 0;}
int randomLimit(int n){return 0;}
'''
t=r'''
static void reset(void){
 for(int i=0;i<10;i++){ENTITY_TABLE[i]=&ents[i];ents[i]=(Entity){1,1,1};bubbles[i]=-1;}
 for(int i=0;i<512;i++)params[i].type=1;
 for(int i=0;i<8;i++)NPC_ENTITIES[i]=(NPC){{{1,1,1}},1};
 for(int i=0;i<256;i++)ps[i]=0;
 PARTNER_ENTITY.digimonEntity.entity.type=1;escape=0;
}
int main(void){
 reset();NPC_ENTITIES[1].autotalk=0;
 assert(handleBattleStart(2)==3);
 assert(combat.player.entityIds[1]==2);
 if(BEFORE){assert(combat.player.entityIds[2]==3);assert(combat.player.entityIds[3]==4);}
 else{assert(combat.player.entityIds[2]==4);assert(combat.player.entityIds[3]==5);assert(bubbles[3]==1);}
 reset();for(int i=1;i<8;i++)NPC_ENTITIES[i].autotalk=0;
 assert(handleBattleStart(2)==(BEFORE?3:1));
 reset();NPC_ENTITIES[0].autotalk=0;
 assert(handleBattleStart(2)==3&&combat.player.entityIds[1]==2);
 reset();ps[250]=1;ps[251]=3;ps[252]=4;ps[253]=255;NPC_ENTITIES[1].autotalk=0;
 assert(handleBattleStart(2)==2&&combat.player.entityIds[1]==3&&combat.player.entityIds[2]==4);
 reset();ents[3].isOnMap=0;
 assert(handleBattleStart(2)==3&&combat.player.entityIds[2]==4);
}
'''
(ROOT/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
 p=Path(d);(p/'test.c').write_text('#define BEFORE '+str(int(before))+'\n'+h+func+t)
 subprocess.run(['cc','-std=c99','-Wno-implicit-function-declaration',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('pass: wild groups, passive bystanders, primary opponent, explicit groups, absent entities')
