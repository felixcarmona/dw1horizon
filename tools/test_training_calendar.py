#!/usr/bin/env python3
"""Run both actual gym time-advance functions against the 30-day game calendar.

Usage: python3 tools/test_training_calendar.py build/decomp-bug-systems
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def function(source, name):
    start = re.search(r'^void ' + name + r'\([^;]*?\)\n\{', source, re.M)
    assert start, name
    return source[start.start():source.index('\n}', start.end()) + 2]


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-bug-systems')
    definitions = (work / 'include/dw/mod_rules.h').read_text()
    code = '#include <stdint.h>\n#include <assert.h>\n#include <stdio.h>\n'
    code += '\n'.join(re.findall(r'^#define MOD_TR_\w+\s+\d+.*$', definitions, re.M))
    code += r'''
struct {
 int16_t tiredness, energyLevel, happiness, discipline, age, remainingLifetime;
 int16_t sicknessCounter, missedSleepHours, starvationTimer, careMistakes;
 int16_t foodLevel, poopingTimer, poopLevel, evoTimer, injuryTimer, sicknessTimer;
 uint32_t condition;
} PARTNER_PARA;
struct { struct { struct { int type; } entity; } digimonEntity; } PARTNER_ENTITY;
struct { int energyThreshold, energyUsage; } raise;
#define RAISE_ROW(type) raise
int16_t HOUR, MINUTE, DAY;
uint8_t YEAR;
uint16_t CURRENT_FRAME, TRN_CURRENT_FRAME, MAIN_D_801353CE;
int16_t TRN_CURRENT_HOUR, MAIN_D_801353D0;
int16_t MOD_TRAIN2_RULES[64];
int daily;
int TRN_rule(int slot) { return -1; }
int TRN_amt(int slot) { return 0; }
void dailyPStatTrigger(void) { daily++; }
void updateMinuteHand(int h, int m) { assert(h >= 0 && h < 24); }
void initializeDaytimeTransition(int t) { }
void tickConditionBoundaries(void) { }
'''
    for name, path in [('TRN_advanceTrainingTime', 'src/trn/trn_reward.c'),
                       ('TRN2_advanceTrainingTime', 'src/trn2/trn2_hud.c')]:
        code += '\n' + function((work / path).read_text(), name)
    code += r'''
int main(void) {
 void (*gyms[])(int16_t,int16_t,int16_t) = {TRN_advanceTrainingTime, TRN2_advanceTrainingTime};
 for (int gym=0; gym<2; gym++) {
  for (int year=0; year<100; year++) {
   for (int day=0; day<30; day++) {
    for (int hour=0; hour<24; hour++) {
     for (int minute=0; minute<60; minute+=59) {
      HOUR=TRN_CURRENT_HOUR=MAIN_D_801353D0=hour;
      MINUTE=minute; DAY=day; YEAR=year; daily=0;
      CURRENT_FRAME=TRN_CURRENT_FRAME=MAIN_D_801353CE=hour*1200+minute*20;
      PARTNER_PARA.age=7; PARTNER_PARA.evoTimer=10;
      PARTNER_PARA.remainingLifetime=100;
      gyms[gym](0,0,0);
      int midnight=hour==23;
      int wantDay=(day+midnight)%30;
      int wantYear=(year+(midnight && day==29))%100;
      if (DAY!=wantDay || YEAR!=wantYear) {
       fprintf(stderr,"gym %d: %d:%d %02d:%02d -> %d:%d, expected %d:%d\n",
               gym,year,day,hour,minute,YEAR,DAY,wantYear,wantDay);
       return 1;
      }
      assert(HOUR==(hour+1)%24 && MINUTE==minute);
      assert(CURRENT_FRAME==HOUR*1200+minute*20);
      assert(daily==midnight && PARTNER_PARA.age==7+midnight);
      assert(PARTNER_PARA.evoTimer==11);
     }
    }
   }
  }
 }
 puts("PASS: both gyms, every year/day/hour, minute 0/59; one daily reset and age increment at midnight");
}
'''
    with tempfile.TemporaryDirectory(prefix='dw-training-calendar-') as tmp:
        source = Path(tmp) / 'check.c'
        binary = Path(tmp) / 'check'
        source.write_text(code)
        subprocess.run(['cc', '-std=c99', '-fsanitize=undefined', str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
