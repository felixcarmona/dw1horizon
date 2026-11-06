#!/usr/bin/env python3
"""Exercise the actual shared gym block code, including cancellation and HUD state.

Run against a prepared patch tree: python3 tools/dev/playtest/training_care_hud_host.py TREE
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    tree = Path(sys.argv[1])
    shared = (tree / 'src/trn/trn_block.h').read_text()
    shared = re.sub(r'^#include .*$', '', shared, flags=re.M)
    shared = re.sub(r'^static (TRN_BLOCK_\w+)_TEXT$', r'static char \1[] = "Done 0";', shared, flags=re.M)
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef struct { int x,y,w,h; } RECT;
typedef struct { int state; } Box;
Box UI_BOX_DATA[4];
int16_t INITIAL_COMBAT_STATS[1][6], STATS_GAINS[6], STATUS_UI_OFFSET_X;
int8_t IS_GAMETIME_RUNNING;
uint32_t CHANGED_INPUT;
#define CANCEL_BUTTON 16
#define MOD_COUNT_ROW_H 17
#define MOD_TR_TIRED_AT 0
#define CAP_OF_STAT_INDEX(i) 999
#define setRECT(p,a,b,c,d) (*(p)=(RECT){a,b,c,d})
enum { MOD_TB_GO, MOD_TB_HUNGRY, MOD_TB_TOILET, MOD_TB_SLEEPY, MOD_TB_TIRED,
       MOD_TB_UNWELL, MOD_TB_EVOLVE, MOD_TB_LIFE, MOD_TB_LEARNED };
int slot, started, stopReason, opened, drawn, awardCount, hours, learned;
int16_t rules[1]={50};
int32_t modTrainStopReason(int32_t t0,int32_t tiredAt) { return stopReason; }
void clearTextArea(void) { }
void clearTextSubArea(RECT *r) { }
void removeAnimatedUIBox(int id,void *p) { UI_BOX_DATA[id].state=0; }
void createMenuBox(int a,int b,int c,int d,int e,int f,void (*tick)(void),void (*render)(void)) { if(a==2) assert(b==-118); UI_BOX_DATA[a].state=1; }
void renderString(int a,int b,int c,int d,int e,int f,int g,int h,int i) { }
void setTextColor(int v) { }
void drawString(char *s,int x,int y) { }
void renderStatusBars(int32_t state) { assert(STATUS_UI_OFFSET_X==75); assert(state==1); drawn++; }
#define TB_SLOT slot
#define TB_RULES rules
#define TB_START_MIN started
'''
    for pre in ('TRN', 'TRN2'):
        code += f'''
void {pre}_saveTrainingStartTime(void);
void {pre}_saveBaseStats(void) {{ }}
void {pre}_applyBaseStats(void) {{ }}
void {pre}_modOpenStatsBox(void) {{ opened++; }}
int32_t {pre}_statGainsAreZero(void) {{ return 0; }}
#define TB(name) {pre}_##name
'''
        # Both headers normally live in separate translation units. Rename their file-local symbols here.
        local = shared
        for name in set(re.findall(r'\bTB_\w+\b', local)) - {'TB_SLOT', 'TB_RULES', 'TB_START_MIN'}:
            local = re.sub(r'\b' + name + r'\b', pre + '_' + name, local)
        for name in set(re.findall(r'\bTRN_BLOCK_\w+\b', local)):
            local = re.sub(r'\b' + name + r'\b', pre + '_' + name, local)
        code += local
        code += f'''
void {pre}_saveTrainingStartTime(void) {{ started=hours*60; {pre}_modBlockArm(); }}
static void {pre}_award(void) {{
 assert(opened==0); awardCount++; hours++;
 for(int i=0;i<6;i++) STATS_GAINS[i]=11;
 if(learned && awardCount==learned) UI_BOX_DATA[2].state=1;
}}
static void {pre}_test(void) {{
 for(int cancel=0;cancel<5;cancel++) for(int reason=0;reason<=8;reason++) {{
  memset(UI_BOX_DATA,0,sizeof(UI_BOX_DATA));
  memset(STATS_GAINS,0,sizeof(STATS_GAINS));
  for(int i=0;i<6;i++) INITIAL_COMBAT_STATS[0][i]=980;
  slot=2; started=0; stopReason=0; opened=awardCount=hours=0;
  CHANGED_INPUT=0; learned=reason==8 ? 2 : 0;
  {pre}_MOD_QUIET=0; {pre}_modBlockArm(); {pre}_modBlockBegin();
  {pre}_award(); {pre}_modBlockNext();
  int ticks=0;
  while({pre}_MOD_QUIET) {{
   if(cancel && awardCount==cancel) CHANGED_INPUT=CANCEL_BUTTON;
   if(!{pre}_modBlockWait()) {{
    assert(ticks>=20); ticks=0;
    {pre}_saveTrainingStartTime();
    if(awardCount==1 && reason<8) stopReason=reason;
    {pre}_award(); {pre}_modBlockNext();
   }} else ticks++;
   assert(ticks<30);
  }}
  int want=cancel ? cancel : reason ? 2 : 5;
  if(reason && want>2) want=2;
  assert(awardCount==want && hours==want && opened==1);
  for(int i=0;i<6;i++) {{
   assert(INITIAL_COMBAT_STATS[0][i]==980);
   assert(STATS_GAINS[i]==(want==1 ? 11 : 19));
  }}
 }}
 // A single session must not enter the repeated-session accounting path.
 slot=0; {pre}_MOD_QUIET=0; {pre}_modBlockArm(); {pre}_modBlockBegin();
 assert(!{pre}_MOD_QUIET); assert({pre}_modBlockNext()==0);
 // The render wrapper restores the slide state and respects game time.
 for(int running=0;running<2;running++) {{
  IS_GAMETIME_RUNNING=running; STATUS_UI_OFFSET_X=240; drawn=0;
  {pre}_renderCareHUD(0);
  assert(drawn==!running); assert(STATUS_UI_OFFSET_X==240);
 }}
}}
#undef TB
'''
    code += 'int main(void) { TRN_test(); TRN2_test(); puts("PASS: both overlays, five sessions, cancel boundaries, native stops, capped totals, single sessions, HUD/slide state"); }\n'
    with tempfile.TemporaryDirectory(prefix='training-care-hud-') as tmp:
        source = Path(tmp) / 'check.c'
        binary = Path(tmp) / 'check'
        source.write_text(code)
        subprocess.run(['cc', '-std=c99', '-fsanitize=undefined', str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
