#!/usr/bin/env python3
"""Exercise the compiled care collector and threshold without an emulator."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def function(source, signature):
    a=source.index(signature); start=source.index('{',a); depth=1; end=start+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[a:end]


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else 'build/decomp-int')
    feed=(root/'src/main/mod_feed.c').read_text()
    partner=(root/'include/dw/partner.h').read_text()
    bubble=(root/'src/main/bubble.c').read_text()
    defines='\n'.join(line for line in feed.splitlines() if re.match(r'#define (RANK_|FEED_(SCOLD|SLEEP)|SCOLD_PENDING|PORT_POTTY)',line))
    prefix=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef int ItemId;
typedef void (*ItemFunction)(void);
#define ITEM_NONE -1
#define CONDITION_HUNGRY 4
#define CONDITION_POOPY 8
#define CONDITION_SLEEPY 1
#define CONDITION_INJURED 32
#define CONDITION_SICK 64
#define MOD_FX(fx,i) ((fx)[i])
#define MOD_FX_HEAL_HP 0
#define MOD_FX_HEAL_MP 1
#define MOD_FX_CURE_INJURY 2
#define MOD_FX_CURE_SICK 3
#define MOD_CARE_MEDICINE_INJURY_DIE 0
#define MOD_CARE_MEDICINE_SICK_DIE 0
static void handleFood(void) {}
static void handleStatusItems(void) {}
static void handleHPHealingItem(void) {}
static void handleMPHealingItem(void) {}
static void handleRestore(void) {}
static void handleDoubleFloppy(void) {}
static ItemFunction ITEM_FUNCTIONS[64];
static struct {int itemColor;} ITEM_PARA[64];
static int16_t effects[64][4];
static const int16_t *itemFx(int type) {return effects[type];}
static int careDie(int type) {(void)type; return 100;}
static int isFavourite(int type) {return type==10;}
static struct {unsigned condition;} PARTNER_PARA;
static struct {struct {struct {struct {uint16_t currentHP,currentMP;} current;
struct {uint16_t hp,mp;} base;} stats;} digimonEntity;} PARTNER_ENTITY;
static struct {struct {int array[30];} types,amounts;int size;} INVENTORY;
static int ITEM_SCOLD_FLAG;
static uint8_t feedSlots[32];
static int feedRanks[32],feedCount;
#define RING_STEP_TICKS 10
#define RING_SIZE 205
#define RING_COL 22
#define RING_ROW 18
#define RING_NONE 0x10000
#define RING_TAIL 0x20000
static const uint8_t RING_BIT[9]={4,8,1,2,64,32,0,0,0};
static int IS_IN_MENU,MOD_RING_CLOCK,MOD_RING_T=-1,MOD_RING_STEPS;
static int MOD_RING_FROM[9],MOD_RING_TO[9],MOD_RING_BADGE,MOD_FEED_HINT;
#define RING_BADGE_TICKS 4

'''
    tests=r'''
int main(void) {
    PARTNER_ENTITY.digimonEntity.stats.base.hp=1000;
    PARTNER_ENTITY.digimonEntity.stats.base.mp=1000;
    ITEM_FUNCTIONS[0]=handleHPHealingItem;
    ITEM_FUNCTIONS[4]=handleMPHealingItem;
    ITEM_FUNCTIONS[7]=handleDoubleFloppy;effects[7][0]=effects[7][1]=100;
    ITEM_FUNCTIONS[10]=handleFood;
    INVENTORY.size=3;
    INVENTORY.types.array[0]=0;INVENTORY.types.array[1]=4;INVENTORY.types.array[2]=7;
    for(int i=0;i<3;i++)INVENTORY.amounts.array[i]=1;
    for(int current=290;current<=310;current+=10) {
        PARTNER_ENTITY.digimonEntity.stats.current.currentHP=current;
        PARTNER_ENTITY.digimonEntity.stats.current.currentMP=1000;
        assert(modResourceNeed(current,1000)==(current==290));
        assert(needRank(0)==(current==290?RANK_HEAL:RANK_RECOVERY)*256);
        assert(feedCollect(1)==(current==290?2:0));
        assert(feedCollect(0)==2); /* HP floppy and double, even without a badge. */
        PARTNER_ENTITY.digimonEntity.stats.current.currentHP=1000;
        PARTNER_ENTITY.digimonEntity.stats.current.currentMP=current;
        assert(needRank(4)==(current==290?RANK_HEAL:RANK_RECOVERY)*256);
        assert(feedCollect(1)==(current==290?2:0));assert(feedCollect(0)==2);
    }
    PARTNER_ENTITY.digimonEntity.stats.current.currentHP=290;
    PARTNER_ENTITY.digimonEntity.stats.current.currentMP=310;
    PARTNER_PARA.condition=CONDITION_SLEEPY;
    assert(feedCollect(0)==4);
    assert(feedRanks[0]==RANK_HEAL*256 && feedRanks[1]==RANK_HEAL*256);
    assert(feedSlots[2]==FEED_SLEEP && feedSlots[3]==1); /* optional MP after real needs */
    assert(feedCollect(1)==3);
    INVENTORY.size=0;PARTNER_PARA.condition=0;
    assert(feedCollect(1)==0 && feedCollect(0)==0);
    assert(modResourceNeed(290,1000)); /* no inventory dependency in the bubble predicate */
    PARTNER_ENTITY.digimonEntity.stats.current.currentHP=1000;
    PARTNER_ENTITY.digimonEntity.stats.current.currentMP=1000;
    INVENTORY.size=3;assert(feedCollect(0)==0);
    assert(!modResourceNeed(0,0));assert(!modResourceNeed(1,0));
    assert(modResourceNeed(19005,65535));assert(!modResourceNeed(20315,65535));
    assert(modResourceNeed(19660,65535));assert(!modResourceNeed(19661,65535));
    assert(modResourceNeed(0,1));assert(!modResourceNeed(1,1));
    ITEM_PARA[0].itemColor=1;
    PARTNER_ENTITY.digimonEntity.stats.current.currentHP=290;
    assert(needRank(0)==0); /* battle-only recovery cannot light the field badge */
    INVENTORY.size=0;PARTNER_PARA.condition=0;
    for(int flag=0;flag<=3;flag++) {
        ITEM_SCOLD_FLAG=flag;
        assert(modScoldAvailable(flag)==(flag==1));
        assert(feedCollect(1)==(flag==1));
        assert(feedCollect(0)==(flag==1));
        if(flag==1)assert(feedSlots[0]==FEED_SCOLD);
    }
    for(int flag=0;flag<=3;flag++)for(int needs=0;needs<2;needs++) {
        ITEM_SCOLD_FLAG=flag;PARTNER_PARA.condition=needs?111:0;
        PARTNER_ENTITY.digimonEntity.stats.current.currentHP=needs?290:1000;
        PARTNER_ENTITY.digimonEntity.stats.current.currentMP=needs?290:1000;
        MOD_RING_T=-1;
        for(int i=0;i<9;i++)MOD_RING_FROM[i]=MOD_RING_TO[i]=RING_NONE;
        for(int t=0;t<25;t++) {
            MOD_FEED_HINT=modScoldAvailable(flag);tickConditionRingObject(0);
        }
        assert((MOD_RING_FROM[8]!=RING_NONE)==(flag==1));
        for(int i=0;i<8;i++)assert((MOD_RING_FROM[i]!=RING_NONE)==needs);
        if(needs && flag==1) {
            /* Five bubbles above four, with Scold last in the lower row. */
            assert(MOD_RING_FROM[0]==((84<<8)|110));
            assert(MOD_RING_FROM[4]==((172<<8)|110));
            assert(MOD_RING_FROM[8]==((161<<8)|128));
        }
    }
    puts("Scold collector/slot membership, all nine needs, plus HP/MP 29/30/31%, full/zero/unsigned maxima, empty bag and menu urgency passed");
}
'''
    source=prefix+defines+'\n'+function(partner,'static inline int32_t modResourceNeed')+'\n'+function(partner,'static inline int32_t modScoldAvailable')+'\n'
    for signature in ('static int32_t needRank','static void feedAdd','static int32_t feedCollect'):
        source+=function(feed,signature)+'\n'
    source+=function(bubble,'void tickConditionRingObject(int32_t instanceId)\n{').replace('{','{\n (void)instanceId;',1)+'\n'
    with tempfile.TemporaryDirectory(prefix='hpmp-care-') as tmp:
        c=Path(tmp)/'care.c';exe=Path(tmp)/'care';c.write_text(source+tests)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)


if __name__=='__main__':main()
