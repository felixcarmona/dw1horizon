#!/usr/bin/env python3
"""Run the actual MP gym state machines with a deterministic slow return walk.

Usage: python3 tools/dev/playtest/training_mp_host.py build/decomp-dev
The first session is already awarded; movement remains pending for longer than
four ordinary inter-session waits. Stats may finish while walking, but field
control must wait for both movement and the tally. Uses UBSan; no disc required.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

work = Path(sys.argv[1])
parts = []
for pre, path in [('TRN','src/trn/trn_mp.c'),('TRN2','src/trn2/trn2_mp.c')]:
    text = (work / path).read_text()
    start = text.index('void ' + pre + '_tickMpTraining(')
    end = text.index('\n}', start) + 2
    parts.append(text[start:end])
# Compile the real complete state machines with deterministic movement and awards.
code=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef struct { int vx,vy,vz; } VECTOR;
typedef VECTOR SVECTOR;
typedef void (*RenderFunction)(int);
struct Pos {VECTOR location, rotation;};
struct Entity {struct Pos *posData;int type;struct{int animFrame,frameCount;}anim;};
struct Pos pos;
struct {struct {struct Entity entity;}digimonEntity;}PARTNER_ENTITY={{{&pos}}};
struct {struct Entity entity;}TAMER_ENTITY={{&pos}};
struct {int height;}dummy;
#define DIGI_PARA(x) dummy
#define TRN_SESSION_OF(x) 1200
#define CANCEL_BUTTON 16
int POLLED_INPUT,TRAINING_STATE,TRAINING_COMPLETE,TRN_MOD_QUIET,TRN2_MOD_QUIET;
int MAIN_D_8013536C, MAIN_D_8013536E, MAIN_D_80135370, MAIN_D_80135372,MAIN_D_80135374,MAIN_D_80135376,MAIN_D_80135378,MAIN_D_8013537A,MAIN_D_8013537C,MAIN_D_80135384;
int MAIN_D_801353BC,MAIN_D_801353BD,MAIN_D_801353C2,MAIN_D_801353C4;
int MOD_TRAIN_RULES[64],MOD_TRAIN2_RULES[64];
VECTOR TRN_D_8008F320,TRN_D_8008F330,TRN_D_8008F368[1],TRN_D_8008F388[1];
VECTOR TRN2_D_8008DC1C,TRN2_D_8008DC2C;
int tick,awards,countdown,opened,walking,zero,closed,closes,mode;
void storeMapObjectPosition(){} void loadMapObjectPosition(){}
void tamerSetState(int v){if(v==0)closes++;} void partnerSetState(){}
void startAnimation(){} void createCameraMovement(){} void playSound(){}
int tickEntityWalkTo(){return !walking;} void setMapObjectsFlag(){}
void getDrawPosition(){} void moveMapObjects(){} int playSound2(){return 0;}
void thunkStopSoundMask(){} void removeObject(){}
void TRN_renderCareHUD(){}
#define DEFINE(P) \
 void P##_startSlotSessionIfEnabled(){} void P##_startSlotSpin(){} \
 int P##_getSlotSessionResult(){return 10;} \
 void P##_modBlockBegin(){} void P##_saveTrainingStartTime(){} \
 void P##_awardMpTrainingGains(){awards++;assert(awards<=5);} \
 int P##_modBlockNext(){if(awards==5){P##_MOD_QUIET=0;opened=tick;}else countdown=20;return 0;} \
 int P##_modBlockWait(){if(countdown){countdown--;return 1;}return 0;} \
 int P##_statGainsAreZero(){return zero;} void P##_applyBaseStats(){} \
 void P##_closeUIBox(){closed++;}
DEFINE(TRN) DEFINE(TRN2)
'''
code+='\n'.join(parts)
code+=r'''
int main(){
 for(int gym=0;gym<2;gym++){
  // A long return walk must not postpone the remaining four session awards.
  awards=1;countdown=20;opened=closed=closes=zero=0;walking=1;
  TRN_MOD_QUIET=TRN2_MOD_QUIET=1;TRAINING_STATE=MAIN_D_801353BD=4;
  for(tick=1;tick<=84;tick++){
   if(gym)TRN2_tickMpTraining(0);else TRN_tickMpTraining(0);
   assert(closed==0 && closes==0);
  }
  if(awards!=5){fprintf(stderr,"gym %d: only %d awards while returning\n",gym,awards);return 1;}
  assert(opened==84);
  assert((gym?MAIN_D_801353BD:TRAINING_STATE)==4);
  // Even a completed/skipped tally cannot close training before the walk ends.
  zero=1;
  for(int n=0;n<40;n++){if(gym)TRN2_tickMpTraining(0);else TRN_tickMpTraining(0);}
  assert(closed==0 && closes==0);
  walking=0;
  for(int n=0;n<22;n++){if(gym)TRN2_tickMpTraining(0);else TRN_tickMpTraining(0);}
  assert(closed==1 && closes==1);
 }
 puts("PASS: both MP gyms award during return; table at tick 84; field cleanup waits for walk and tally");
}
'''
with tempfile.TemporaryDirectory(dir='build',prefix='mp-host-') as tmp:
 src=Path(tmp)/'check.c';binary=Path(tmp)/'check';src.write_text(code)
 subprocess.run(['cc','-std=gnu99','-fsanitize=undefined',str(src),'-o',str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
