#!/usr/bin/env python3
"""Exercise consecutive Bonus Try rounds using the actual overlay C functions.

Usage: python3 tools/dev/playtest/training_bonus_host.py build/decomp-int
No disc required. UI/sound are stubs; round initialization, input edges, reel
stopping, assistance, payout and session completion execute the supplied C.
The state-copy checks model restored RAM/input/RNG, not an emulator save file.
"""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def function(source, name):
    # Definitions start at column zero; calls and forward declarations do not
    # have a following body. Include old-style parameter declarations as well.
    match = re.search(r"^(?:void|int32_t|int16_t) " + name + r"\([^;\n]*\)\n(?:\t[^\n]+\n)*\{", source, re.M)
    if not match:
        raise ValueError(name)
    start = match.start()
    return source[start : source.index("\n}", match.end()) + 2]


def main():
    work = Path(sys.argv[1]).resolve()
    root = Path(__file__).resolve().parents[3]
    tables = json.loads((root / "content/tables/slot-machine.json").read_text())
    for prefix, reel, assist, session in (
        ("TRN", "TRN_D_8008F1AC", "TRN_D_8008F2CC", "MAIN_D_801353A0"),
        ("TRN2", "TRN2_D_8008DAA8", "TRN2_D_8008DBC8", "MAIN_D_801353E0"),
    ):
        source = (work / f"src/{prefix.lower()}/{prefix.lower()}_slots.c").read_text()
        hud = (work / f"src/{prefix.lower()}/{prefix.lower()}_hud.c").read_text()
        array = lambda value: json.dumps(value).replace("[", "{").replace("]", "}")
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <dw/training.h>
#define VERSION_IS(x) 1
#define CONFIRM_BUTTON 1
typedef struct {int16_t x,y,w,h;} RECT;
typedef struct {int16_t x,y,z,pad;} SVECTOR;
typedef void (*TickFunction)(int32_t);
typedef void (*RenderFunction)(int32_t);
enum {MOD_TR_PAY_JACKPOT,MOD_TR_PAY_MATCH,MOD_TR_PAY_TRIPLE,MOD_TR_PAY_MISS};
int MOD_TRAIN_RULES[]={100,40,20,5}, MOD_TRAIN2_RULES[]={100,40,20,5};
uint32_t POLLED_INPUT,POLLED_INPUT_PREVIOUS,rng;
int CURRENT_SCREEN,DRAWING_OFFSET_X,DRAWING_OFFSET_Y,removed;
struct {int state;} UI_BOX_DATA[4];
RECT SLOTS_UI_START,SLOTS_UI_END,MAIN_D_80134BD8;
RECT MAIN_D_80134BE8,MAIN_D_80134BF0,MAIN_D_80134BF8;
int rand(void){rng=rng*1664525u+1013904223u;return (rng>>1)&0x7fffffff;}
void playSound(int a,int b){}
void addObject(int a,int b,TickFunction c,RenderFunction d){}
void removeObject(int a,int b){removed++;}
void createAnimatedUIBox(int a,int b,int c,RECT*d,RECT*e,TickFunction f,RenderFunction g){UI_BOX_DATA[a].state=1;}
void removeAnimatedUIBox(int id,RECT*r){UI_BOX_DATA[id].state=0;}
void closeBox(int id){}
'''
        code += f"""
SlotMachine {prefix}_SLOT_MACHINE;
int16_t {session}[4];
int8_t {reel}[3][13]={array(tables['slotReels'])};
int8_t {assist}[10]={array(tables['slotAssist'])};
int32_t {prefix}_getTrainingSpotScreenPos(int32_t a,int32_t b,SVECTOR*c){{return -1;}}
void {prefix}_renderSlotMachine(int32_t a){{}}
void {prefix}_renderSlotSession(void){{}}
void {prefix}_tickSlotSession(void);
void {prefix}_chooseReelStop(int16_t i,SlotMachine*p);
"""
        for name in ("tickSlotMachine", "chooseReelStop", "startSlotSession",
                     "getSlotSessionResult", "createSlotMachineBox", "getSlotMachineResult",
                     "startSlotSpin"):
            code += function(source, prefix + "_" + name) + "\n"
        code += function(hud, prefix + "_tickSlotSession") + "\n"
        code += f"""
#define P {prefix}_SLOT_MACHINE
#define REELS {reel}
#define SESSION {session}
#define START {prefix}_startSlotSession
#define SESSION_TICK {prefix}_tickSlotSession
#define TICK {prefix}_tickSlotMachine
#define SPIN {prefix}_startSlotSpin
#define CHOOSE {prefix}_chooseReelStop
"""
        code += r'''
void tick(int button){POLLED_INPUT_PREVIOUS=POLLED_INPUT;POLLED_INPUT=button;TICK(3);}
void finish(int delay){
 for(int i=0;i<3;i++){
  for(int j=0;j<delay;j++)tick(0);
  tick(1);tick(0);
 }
 for(int n=0;n<100 && P.result<0;n++)tick(0);
 assert(P.result==5 || P.result==20 || P.result==40 || P.result==100);
 SESSION_TICK();SESSION_TICK();
 assert(SESSION[0]==P.result && UI_BOX_DATA[3].state==0);
}
struct Snapshot {SlotMachine slot;int16_t session[4];uint32_t rng,input,previous;};
struct Snapshot save(void){
 struct Snapshot s={0};s.slot=P;memcpy(s.session,SESSION,sizeof s.session);
 s.rng=rng;s.input=POLLED_INPUT;s.previous=POLLED_INPUT_PREVIOUS;return s;
}
void load(struct Snapshot s){
 P=s.slot;memcpy(SESSION,s.session,sizeof s.session);rng=s.rng;
 POLLED_INPUT=s.input;POLLED_INPUT_PREVIOUS=s.previous;UI_BOX_DATA[3].state=1;
}
int main(void){
 assert(sizeof(SlotMachine)==44);
 for(int mode=0;mode<3;mode++)for(int delay=1;delay<=39;delay++){
  // Run a first and a second round with no reset/reload of overlay storage.
  memset(&P,0xa5,sizeof P);rng=12345+delay;POLLED_INPUT=POLLED_INPUT_PREVIOUS=0;
  for(int attempt=0;attempt<2;attempt++){
   START(attempt);SESSION_TICK();P.assist=mode;
   assert(P.result==-1 && P.state==0 && P.autoStart==-1);
   // Restore a pre-spin checkpoint and compare with uninterrupted completion.
   struct Snapshot before=save();
   SPIN();tick(0);
   assert(P.stopSteps[0]==0 && P.stopSteps[1]==0 && P.stopSteps[2]==0);
   struct Snapshot spinning=save();finish(delay);struct Snapshot expected=save();
   load(spinning);finish(delay);struct Snapshot replay=save();
   assert(memcmp(&expected,&replay,sizeof replay)==0);
   load(before);SPIN();tick(0);finish(delay);replay=save();
   assert(memcmp(&expected,&replay,sizeof replay)==0);
  }
 }
 // The reported extra symbol is reachable without any stale round state:
 // unassisted triple sevens deliberately slip on reel three.
 memset(&P,0,sizeof P);P.assist=0;P.targetSymbol[0]=P.targetSymbol[1]=7;
 for(int i=0;i<13;i++)if(REELS[2][i]==7)P.reelPos[2]=(i+1)%13;
 CHOOSE(2,&P);assert(P.stopSteps[2]==1 || P.stopSteps[2]==2);
 printf("PASS: 234 consecutive rounds; pre-spin/spinning state replay; forced miss slips %d symbols\n",P.stopSteps[2]);
 // Once stopped, all original triples (including 777) still pay correctly.
 for(int stat=0;stat<6;stat++)for(int symbol=1;symbol<=7;symbol++){
  memset(&P,0,sizeof P);P.state=5;P.stat=stat;
  for(int reel=0;reel<3;reel++)for(int pos=0;pos<13;pos++)
   if(REELS[reel][pos]==symbol){P.reelPos[reel]=pos;break;}
  tick(0);assert(P.payout==(symbol==7?100:symbol==stat+1?40:20));
 }
 // A held button stops one reel; the next reel requires a fresh edge.
 START(0);SESSION_TICK();SPIN();tick(0);tick(1);
 for(int i=0;i<10;i++)tick(1);
 assert(P.state==2);tick(0);tick(1);assert(P.state==3);
 puts("PASS: 42 triple payouts including 777; held confirm stops only one reel");
}
'''
        with tempfile.TemporaryDirectory(dir=root / "build", prefix="bonus-host-") as tmp:
            src, binary = Path(tmp) / "check.c", Path(tmp) / "check"
            src.write_text(code)
            subprocess.run(["cc", "-std=gnu99", "-fsanitize=undefined", "-I", str(work / "include"),
                            str(src), "-o", str(binary)], check=True)
            print(prefix, flush=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
