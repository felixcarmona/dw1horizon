#!/usr/bin/env python3
"""Host regression checks for imported quadruped follow changes (patch0232)."""
from pathlib import Path
import re,subprocess,json
import argparse,tempfile,hashlib
parser=argparse.ArgumentParser(description='Compile the real partner follow consumer in a host harness and check reviewed189/201 step changes without SDK assets.')
parser.add_argument('--source',type=Path,required=True,help='Patched decompilation worktree')
parser.add_argument('--baseline',type=Path,help='Optional original decompilation worktree for the same cases')
parser.add_argument('--out',type=Path,help='Retain generated C harnesses and proof JSON here')
args=parser.parse_args();temporary=tempfile.TemporaryDirectory(prefix='dw-field-follow-');p=args.out or Path(temporary.name);p.mkdir(parents=True,exist_ok=True)
def function(s,name):
 m=re.search(r'(?:static )?(?:void|int32_t) '+name+r'\([^;]*?\)\s*\{',s);assert m,name
 start=m.start();at=s.index('{',m.start());depth=1;end=at+1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[start:end]+'\n'
def source(folder,private):
 s=(Path(folder)/'src/main/partner.c').read_text();s=re.sub(r'^#include[^\n]*','',s,flags=re.M);s=subprocess.check_output(['cc','-E','-P','-x','c','-'],input=preamble+s,text=True);names=['setPartnerIdle','setPartnerSlowWalking','updateConditionAnimation']
 if 'partnerReviewedWalkCycleEnd' in s:names+=['partnerReviewedIdleMayWalk','partnerReviewedWalkCycleEnd']
 if private:names+=['partnerAuthoredGaitHasPostlude','partnerAuthoredGaitCycleEnd','partnerNativeIdleMayWalk']
 names+=['partnerTickWalking'];return '\n'.join(function(s,n)for n in names)
preamble='''#include <stdint.h>
#include <string.h>
#include <assert.h>
#define NUM_ORIGINAL_DIGIMON 180
#define VERSION_US 1
#define VERSION_JP 0
#define VERSION_IS(x) VERSION_##x
#define VERSION_EQUAL_OR_NEWER(x) 1
typedef struct { int animId,frameCount,loopCount,animFrame,animFlag; } EntityAnim;
typedef struct { EntityAnim anim; int type; } Entity;
typedef struct { Entity entity;struct {struct {int hp,mp;}base;struct{int currentHP,currentMP;}current;}stats;}Digimon;
struct {int condition,happiness;} PARTNER_PARA;
struct {Digimon digimonEntity;}PARTNER_ENTITY;
struct {Entity entity;}TAMER_ENTITY;
Entity*ENTITY_TABLE[10];
int PARTNER_ANIMATION,IS_STANDING_STILL,EMOTION_ANIM_TIMEOUT,STOP_DISTANCE_TIMER,HEALTH_SHOE_FRAMES;
int HOST_BAND,HOST_COLLISION,HOST_STARTS;
int getPartnerTamerCloseness(void){return HOST_BAND;}
int entityCheckCollision(void*a,Entity*b,int c,int d){(void)a;(void)b;(void)c;(void)d;return HOST_COLLISION;}
int randomLimit(int n){(void)n;return 1;}
int getItemCount(int n){(void)n;return 0;}
void startAnimation(Entity*e,uint8_t id){e->anim.animId=id;e->anim.animFrame=2;e->anim.loopCount=255;e->anim.animFlag=1;HOST_STARTS++;}
void setPartnerIdle(void);void setPartnerSlowWalking(void);void updateConditionAnimation(void);
'''
tests='''
static void reset(int type,int anim,int need,int band,int frame){
 memset(&PARTNER_ENTITY,0,sizeof(PARTNER_ENTITY));memset(&TAMER_ENTITY,0,sizeof(TAMER_ENTITY));PARTNER_ENTITY.digimonEntity.entity.type=type;
 EntityAnim*a=&PARTNER_ENTITY.digimonEntity.entity.anim;a->animId=anim;a->frameCount=73;a->animFrame=frame;a->loopCount=255;a->animFlag=1;
 ENTITY_TABLE[1]=&PARTNER_ENTITY.digimonEntity.entity;PARTNER_PARA.condition=need;PARTNER_PARA.happiness=0;PARTNER_ANIMATION=anim;HOST_BAND=band;HOST_COLLISION=1;HOST_STARTS=0;IS_STANDING_STILL=2;EMOTION_ANIM_TIMEOUT=1;STOP_DISTANCE_TIMER=0;
}
#define ID PARTNER_ENTITY.digimonEntity.entity.anim.animId
int main(void){
#if NEW_ENGINE
 for(int type=0;type<1024;++type){reset(type,2,0,0,26);assert(!!partnerReviewedWalkCycleEnd(&PARTNER_ENTITY.digimonEntity.entity.anim)==(type==189||type==201));reset(type,0,0,1,5);assert(!!partnerReviewedIdleMayWalk(&PARTNER_ENTITY.digimonEntity.entity.anim)==(type==189||type==201));}
#endif
 for(int band=1;band<=2;++band){
  reset(189,17,0,band,5);partnerTickWalking();assert(ID==17);
  reset(189,17,1,band,5);partnerTickWalking();assert(ID==17);
  reset(3,17,0,band,5);partnerTickWalking();assert(ID==17);
 }
 for(int i=0;i<2;++i){int type=i==0?189:201;
  reset(type,0,0,1,5);partnerTickWalking();assert(ID==(NEW_ENGINE?2:0));
  reset(type,0,0,2,5);partnerTickWalking();assert(ID==0&&HOST_STARTS==0);
  reset(type,2,0,0,2);partnerTickWalking();assert(ID==2);
#if NEW_ENGINE
  for(int frame=1;frame<=74;++frame){
   reset(type,2,0,0,frame);
   assert(!!partnerReviewedWalkCycleEnd(&PARTNER_ENTITY.digimonEntity.entity.anim)==(frame==26||frame==50||frame==74));
   PARTNER_ENTITY.digimonEntity.entity.anim.loopCount=0;
   assert(!partnerReviewedWalkCycleEnd(&PARTNER_ENTITY.digimonEntity.entity.anim));
  }
#endif
  reset(type,2,0,0,26);partnerTickWalking();assert(ID==(NEW_ENGINE?4:2));
  reset(type,2,0,2,26);partnerTickWalking();assert(ID==(NEW_ENGINE?0:2));
  reset(type,2,2,1,26);partnerTickWalking();assert(ID==(NEW_ENGINE?3:2));
  reset(type,2,0,1,26);partnerTickWalking();assert(ID==2&&HOST_STARTS==0);
  reset(type,2,2,1,25);partnerTickWalking();assert(ID==2);
  reset(type,2,0,0,25);partnerTickWalking();assert(ID==2);
  reset(type,2,0,0,26);PARTNER_ENTITY.digimonEntity.entity.anim.frameCount=72;partnerTickWalking();assert(ID==2);
 }
 return 0;
}
'''
rows=[]
cases=[('patched',args.source,True)]
if args.baseline:cases.append(('baseline',args.baseline,False))
for label,folder,new in cases:
 text=(folder/'src/main/partner.c').read_text();private='partnerAuthoredGaitCycleEnd' in text
 assert ('partnerReviewedWalkCycleEnd' in text)==new,'Source does not match the requested patched/baseline role'

 c=p/(label+'-consumer.c');c.write_text(preamble+'\n#define NEW_ENGINE '+str(int(new))+'\n'+source(folder,private)+tests);exe=p/(label+'-consumer-test');subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-error=parentheses','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True);rows.append(dict(case=label,actual_consumer_functions_compiled=True,existing_needs_gestures_unchanged=True,normal_slow_clip_not_restarted_at_step_boundary=True,reviewed_boundary_navigation_and_needs_switches=True,unrelated_original_and_header_guards=True,reviewed_type_guard_checked_ids_0_through_1023=new,all_reviewed_walk_frame_boundaries_checked=new,source_partner_sha256=hashlib.sha256(text.encode()).hexdigest(),asan_ubsan_clean=True));print(label,'PASS',flush=True)
(p/'consumer-host-proof.json').write_text(json.dumps(rows,indent=2)+'\n')
temporary.cleanup()
