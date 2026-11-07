#!/usr/bin/env python3
"""Exercise the actual flatten-recovery C state transition with host sanitizers.

flat_recovery_host.py TREE OUT [--baseline]
Checks healthy, low-HP and poisoned stances, the scaled native model, and
preservation of active attacks, knockback, stun and confusion.
"""
from pathlib import Path
import subprocess,re
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('tree', type=Path)
parser.add_argument('out', type=Path)
parser.add_argument('--baseline', action='store_true', help='require the pre-fix stale tired idle')
args = parser.parse_args()
tree, out = args.tree.resolve(), args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
battle = (tree / 'src/btl/battle_main.c').read_text()
main = (tree / 'src/main/btl.c').read_text()
def body(source,name):
 start=re.search(r'\nvoid '+name+r'\([^;{}]*\)\n\{',source).start()+1;end=source.index('\n}\n',start)+3
 return source[start:end]
flags='\n'.join(x for x in (tree/'include/dw/combat.h').read_text().splitlines() if x.startswith('#define FIGHTER_FLAG_'))
prefix=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef struct { int vx,vy,vz; } VECTOR;
typedef struct { VECTOR scale; } PositionData;
typedef struct { int animId,animFlag; } Animation;
typedef struct { int type; PositionData *posData; Animation anim; int flatSprite; } Entity;
typedef struct { struct {int hp;} base; struct {int currentHP,isHit;} current; } Stats;
typedef struct { Entity entity; Stats stats; } DigimonEntity;
typedef struct { int flags,poisonTimer,confusionTimer,stunTimer,flatTimer,hpDamageBuffer,moveRange; } FighterData;
typedef struct { int unused; } PlayerDataSub;
typedef struct { struct {PlayerDataSub unk1[8];int entityIds[8];} player;FighterData fighter[8];} CombatData;
CombatData data,*COMBAT_DATA_PTR=&data;
Entity *ENTITY_TABLE[10];
int ENEMY_COUNT=0,NO_AI_FLAG=0;
#define BM(x) 100
#define BMS(x) 100
#define MOD_DIFF_DAMAGE(a,b,c,d) (d)
#define CAPS_ADD_DAMAGE(a,b) ((a)+(b))
static int calls=0;
int randomLimit(int v) {(void)v;return 0;}
void addEntityText(Entity *e,int i,int a,int d,int z) {(void)e;(void)i;(void)a;(void)d;(void)z;}
void BTL_addStatusEffectVisual(DigimonEntity *e,FighterData *f,int k) {(void)e;(void)f;(void)k;}
void BTL_resetFighterAction(FighterData *f) {(void)f;}
void BTL_clearConfusion(DigimonEntity *e,FighterData *f) {(void)e;f->flags &= ~FIGHTER_FLAG_CONFUSED;}
void BTL_clearStun(DigimonEntity *e,FighterData *f) {(void)e;f->flags &= ~FIGHTER_FLAG_STUNNED;}
int modModelScale(int t) {return t==113?6144:4096;}
void BTL_applyFlattenScale(VECTOR *s,int t) {if(t==0)s->vx=s->vy=s->vz=4096;}
void startAnimation(Entity *e,uint8_t slot) {e->anim.animId=slot;calls++;}
'''
tests=r'''
int main(void) {
 PositionData position={0};DigimonEntity d={0};
 ENTITY_TABLE[1]=&d.entity;data.player.entityIds[0]=1;d.entity.posData=&position;
 for(int type=0;type<2;type++)for(int health=0;health<2;health++)for(int poisoned=0;poisoned<2;poisoned++) {
  d.entity.type=type?113:314;d.entity.anim.animId=0x22;d.entity.flatSprite=-1;
  d.stats.base.hp=1000;d.stats.current.currentHP=health?100:900;d.stats.current.isHit=1;
  FighterData *f=&data.fighter[0];*f=(FighterData){0};
  f->flags=FIGHTER_FLAG_FLATTENED|FIGHTER_FLAG_TRANSFORMING|(poisoned?FIGHTER_FLAG_POISONED:0);
  f->poisonTimer=999;f->flatTimer=1;calls=0;
  BTL_tickStatusEffects();
  assert(f->flatTimer==0 && !(f->flags&(FIGHTER_FLAG_FLATTENED|FIGHTER_FLAG_TRANSFORMING)));
  assert(d.entity.flatSprite==-1 && d.stats.current.isHit==0);
  assert(position.scale.vx==modModelScale(d.entity.type));
#ifdef EXPECT_FIXED
  assert(calls==1);assert(d.entity.anim.animId==(health||poisoned?0x22:0x21));
#else
  assert(calls==0);assert(d.entity.anim.animId==0x22);
#endif
 }
 int active[]={FIGHTER_FLAG_ATTACKING,FIGHTER_FLAG_KNOCKED_BACK,FIGHTER_FLAG_STUNNED,FIGHTER_FLAG_CONFUSED};
 NO_AI_FLAG=1;
 for(int i=0;i<4;i++)for(int clip=0;clip<2;clip++) {
  FighterData *f=&data.fighter[0];*f=(FighterData){0};f->flags=FIGHTER_FLAG_FLATTENED|active[i];
  f->flatTimer=1;f->stunTimer=f->confusionTimer=999;d.entity.anim.animId=clip?0x2e:0x22;calls=0;
  BTL_tickStatusEffects();assert(calls==0);assert(d.entity.anim.animId==(clip?0x2e:0x22));
 }
 puts("flat recovery: health, poison, model scale and active reactions verified");
}
'''
# Compile the actual game functions; only external services and unused branches are stubbed.
name = 'baseline' if args.baseline else 'fixed'
path = out / (name + '.c')
path.write_text('#include <stdint.h>\n' + flags + '\n' + prefix +
                body(main, 'startBattleIdleAnimation') + body(battle, 'BTL_tickStatusEffects') + tests)
exe = out / name
subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                *([] if args.baseline else ['-DEXPECT_FIXED']), str(path), '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)
