#!/usr/bin/env bash
# care_rules.sh: patch 0125 in the emulator (disc build/full.cue with content/tables/care-rules.json: REUSE_MODELS=1 tools/build-full.sh int).
# Each care function is called with a hand-made partner state on a frame that is a multiple of its period, once with the table the
# build wrote and once with MOD_CARE wiped in RAM (what a build without the file holds): the first must do what the original did
# (sickness, food, poop, tiredness, sleep, sulking, the lifetime lost to unhappiness), the second must do nothing at all.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38116 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/c.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/c.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/c.state >/dev/null
python3 - <<'PY'
import subprocess, struct, sys
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def get(field):
    out = subprocess.run([sys.executable, 'tools/dev/game_state.py', 'show', field], capture_output=True, text=True).stdout.strip()
    return int(out.split()[-1], 0)
import os, time
def call(expr):
    # the emulator is paused while the state is made; the call runs on the first frame after the resume and pauses it again
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', expr], env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); p.communicate()    # emulator.py pause/resume do not stop/restart it
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:58s} got {got} expected {want}')
CARE = T['MOD_CARE']
def fresh(wiped, frame, **fields):
    emu('load', 'build/savedrop/c.state'); emu('lua', 'PCSX.pauseEmulator() return 1')    # emulator.py pause does not stop it
    if wiped:
        for i in range(150): poke(CARE + 2 * i, '<h', -1)
    poke(T['HAS_IMMORTAL_HOUR'], '<i', 0)       # a loaded game spares the partner from sickness and death for its first hour
    poke(T['CURRENT_FRAME'], '<H', frame); poke(T['LAST_HANDLED_FRAME'], '<H', frame - 1)     # the clock advanced one frame onto a multiple of every period
    base = {'partner.para.condition': 0, 'partner.para.happiness': 50, 'partner.para.discipline': 50, 'partner.para.tiredness': 10}
    base.update({f'partner.para.{k}': v for k, v in fields.items()})
    gs(**base)
def case(name, fn, fields, frame, reads, want, wiped_want, args=None):
    for wiped, w in ((0, want), (1, wiped_want)):
        fresh(wiped, frame, **fields); call(fn)
        ok(f'{name}{" (table wiped)" if wiped else ""}', tuple(get(f'partner.para.{r}') for r in reads), w)
F = 3600            # a multiple of 20, 100, 200, 300 and 1200
# sickness: 31 tries, tiredness 100 -> chance 155 %: always sick, one more sickness
case('sickness starts', 'tickSicknessMechanics()', dict(sicknessCounter=10, sicknessTries=30, tiredness=100),
     F, ('condition', 'happiness', 'timesBeingSick'), (0x40, 20, 1), (0, 50, 0))   # -20 at the onset, then -10 the same hour
# a sick partner: -10 happiness, -5 discipline, +5 tiredness, the sickness timer grows
case('a sick partner each hour', 'tickSicknessMechanics()', dict(condition=0x40, sicknessTimer=1),
     F, ('happiness', 'discipline', 'tiredness', 'sicknessTimer'), (40, 45, 15, 2), (50, 50, 10, 1))
case('an injury becomes a sickness (12 hours)', 'tickSicknessMechanics()', dict(condition=0x20, injuryTimer=11),
     F, ('condition', 'injuryTimer', 'sicknessTimer'), (0x40, 0, 1), (0x20, 11, 0))
# hunger: food level -1 every 20 frames; tired for 50 frames: -3 more every hour
case('food level drops, a tired partner hungrier', 'tickHungerMechanics()', dict(foodLevel=50, tirednessHungerTimer=50, energyLevel=900),
     F, ('foodLevel',), (46,), (50,))
case('food runs out: hungry with the starving timer', 'tickHungerMechanics()', dict(foodLevel=0, energyLevel=900),
     F, ('condition', 'starvationTimer'), (4, 180), (0, 0))   # wiped: no starving timer, so it ends at once
# poop level -1 every 200 frames
case('poop level drops', 'tickPoopingMechanic()', dict(poopLevel=5), F, ('poopLevel',), (4,), (5,))
case('poop level 0: holds (discipline + 20) x 12', 'tickPoopingMechanic()', dict(poopLevel=0, discipline=30),
     F, ('condition', 'poopingTimer'), (8, 600), (8, 0))
# tiredness: 80 or more -> exhausted, -2 happiness every 100 frames; under it the condition clears
case('exhausted', 'tickTirednessMechanics()', dict(tiredness=90), F, ('condition', 'happiness'), (2, 48), (0, 50))
case('not exhausted at 79', 'tickTirednessMechanics()', dict(tiredness=79, condition=2), F, ('condition', 'happiness'), (0, 50), (0, 50))
# sleep timer grows by tiredness x 30 / 100 every 20 frames
case('the sleep timer grows', 'tickSleepMechanics()', dict(tiredness=100, tirednessSleepTimer=0), F, ('tirednessSleepTimer',), (30,), (0,))
# sulking: +1 happiness every 15 frames
case('a sulking partner regains happiness', 'tickUnhappinessMechanics()', dict(condition=0x10, happiness=-20),
     F, ('happiness',), (-19,), (-20,))
# lifetime: below 80 happiness, every 4800 frames, -(1 + (80 - happiness) / 50)
case('unhappiness shortens the life', 'tickConditions()', dict(happiness=0, remainingLifetime=1000), 4800,
     ('remainingLifetime',), (998,), (1000,))
# patch 0130: scold and praise, feeding, toilet, wild poop, after a fight, the time a fight takes, the clamps
case('praise: discipline -5, happiness + discipline / 10 + 2', 'handlePraiseScold(3)', dict(discipline=50, happiness=50), F,
     ('happiness', 'discipline'), (57, 45), (50, 50))
case('an unjust scold: discipline +2, happiness -10', 'handlePraiseScold(4)', dict(discipline=50, happiness=50), F,
     ('happiness', 'discipline'), (40, 52), (50, 50))
case('fed when not hungry: happiness -3, discipline -2', 'partnerHandleFoodFeed(48)', dict(discipline=50, happiness=50), F,
     ('happiness', 'discipline'), (47, 48), (50, 50))
case('fed when hungry: happiness +5, discipline +1', 'partnerHandleFoodFeed(48)', dict(condition=4, energyLevel=500, discipline=50, happiness=50), F,
     ('happiness', 'discipline'), (55, 51), (50, 50))
case('the toilet: happiness +2, discipline +2', 'handleToilet()', dict(discipline=50, happiness=50), F, ('happiness', 'discipline'), (52, 52), (50, 50))
case('a wild poop: care mistake, happiness -10, discipline -5', 'handleWildPoop()', dict(discipline=50, happiness=50, careMistakes=0), F,
     ('happiness', 'discipline', 'careMistakes'), (40, 45, 1), (50, 50, 0))
case('after a fight: tiredness +5, food -15', 'handlePostBattleTiredness()', dict(tiredness=10, foodLevel=100), F, ('tiredness', 'foodLevel'), (15, 85), (10, 100))
case('the clamps (too high)', 'tickConditionBoundaries()', dict(happiness=500, discipline=500, tiredness=500, weight=500), F,
     ('happiness', 'discipline', 'tiredness', 'weight'), (100, 100, 100, 99), (500, 500, 500, 500))
case('the clamps (too low)', 'tickConditionBoundaries()', dict(happiness=-500, discipline=-500, tiredness=-500, weight=-500), F,
     ('happiness', 'discipline', 'tiredness', 'weight'), (-100, 0, 0, 1), (-500, -500, -500, -500))
def timecase(name, want, wiped_want):
    for wiped, w in ((0, want), (1, wiped_want)):
        fresh(wiped, F, foodLevel=100, poopLevel=10, condition=0); gs(minute=10); call('advanceBattleTime(0)')
        got = (get('minute'), get('partner.para.foodLevel'), get('partner.para.poopLevel'))
        ok(f'{name}{" (table wiped)" if wiped else ""}', got, w)
timecase('a fight: 20 minutes, food -20, poop -2', (30, 80, 8), (10, 100, 10))
def eatcase(size, name, want):
    for wiped, w in ((0, want), (1, 50)):
        fresh(wiped, F, weight=50); poke(T['POOP_TO_EAT'], 'B', 0); poke(T['WORLD_POOP'] + 3, 'B', size); call('handleEatingPoop()')
        ok(f'eating poop of size {size}: {name}{" (table wiped)" if wiped else ""}', get('partner.para.weight'), w)
eatcase(5, 'small, weight +1', 51); eatcase(12, 'medium, weight +3', 53); eatcase(20, 'large, weight +10', 60)
# per-species overrides (patch 0126): MOD_CARE_SPECIES rows {species, slot, value}, species -1 ends the list
OVR, SLOT_PERCENT, SLOT_PERIOD = T['MOD_CARE_SPECIES'], 1, 0          # sleep.tiredness.percent, sleep.tiredness.period
def override(rows):
    for i, r in enumerate(rows + [(-1, -1, -1)]): poke(OVR + 6 * i, '<3h', *r)
def ocase(name, rows, want):
    fresh(0, F, tiredness=100, tirednessSleepTimer=0)
    mine = get('partner.type'); override([(mine if sp == 'me' else mine + 1, slot, v) for sp, slot, v in rows]); call('tickSleepMechanics()')
    ok(name, get('partner.para.tirednessSleepTimer'), want)
ocase('no override: the global 30 %', [], 30)
ocase('this species: 50 % instead of 30', [('me', SLOT_PERCENT, 50)], 50)
ocase('this species: 0 % (a value of 0 is a value)', [('me', SLOT_PERCENT, 0)], 0)
ocase('this species: the period off (-1): the rule does not exist', [('me', SLOT_PERIOD, -1)], 0)
ocase('another species overrides: this one keeps 30', [('other', SLOT_PERCENT, 50)], 30)
ocase('a row after another species\' row is found', [('other', SLOT_PERCENT, 10), ('me', SLOT_PERCENT, 70)], 70)
ocase('another slot of this species does not change it', [('me', 13, 5)], 30)   # sleep.missed.period
# patch 0140: sub-tiredness gain and its cap, skipHours' lifetime, a sulking partner's gain (above)
case('a full sub-tiredness counter adds 1 tiredness', 'tickTirednessMechanics()', dict(tiredness=40, subTiredness=60), F, ('tiredness', 'subTiredness'), (41, 0), (40, 60))
case('... capped by limit.tiredness.max', 'tickTirednessMechanics()', dict(tiredness=100, subTiredness=60), F, ('tiredness',), (100,), (100,))
def skiplife(wiped):
    fresh(wiped, F, happiness=0, remainingLifetime=1000); gs(hour=0); call('skipHours(4)')
    ok(f'skipping 4 hours from midnight, unhappy: lifetime -4 -2{" (table wiped)" if wiped else ""}', get('partner.para.remainingLifetime'), 996 if wiped else 994)
skiplife(0); skiplife(1)
# patch 0130, the rest of the sleep: skipHours, handleSleeping, sleepRegen and the refusal of an item
case('skipping 3 hours: food -3 x 60, poop -3 x 6', 'skipHours(3)', dict(foodLevel=500, poopLevel=50), F, ('foodLevel', 'poopLevel'), (320, 32), (500, 50))
case('skipping 3 hours hungry: the starving timer -3 x 120', 'skipHours(3)', dict(condition=4, starvationTimer=500, energyLevel=900), F, ('starvationTimer',), (140,), (500,))
case('sleeping while sick: happiness -20, discipline -10, tiredness +10', 'handleSleeping()',
     dict(condition=0x40, wakeupHour=6, sleepyHour=22, hoursAsleepDefault=8, hoursAwakeDefault=10, happiness=50, discipline=50, tiredness=10), F,
     ('happiness', 'discipline', 'tiredness'), (30, 40, 20), (50, 50, 10))
case('sleeping while injured: happiness -10, discipline -5, tiredness +5', 'handleSleeping()',
     dict(condition=0x20, wakeupHour=6, sleepyHour=22, hoursAsleepDefault=8, hoursAwakeDefault=10, happiness=50, discipline=50, tiredness=10), F,
     ('happiness', 'discipline', 'tiredness'), (40, 45, 15), (50, 50, 10))
def regencase():
    for wiped in (0, 1):
        fresh(wiped, F, weight=60, wakeupHour=6, sleepyHour=22, hoursAsleepDefault=8, tiredness=0); gs(hour=22, minute=0)
        ty = get('partner.type'); dw = struct.unpack('B', bytes.fromhex(emu('peek', hex(T['RAISE_DATA'] + 28 * ty + 21), '1').strip().split('\n')[-1].split('  ', 1)[1].replace(' ', '')))[0]
        call('sleepRegen()')
        ok(f'sleeping through the night: weight -default/10{" (table wiped)" if wiped else ""}', get('partner.para.weight'), 60 if wiped else 60 - dw // 10)
regencase()
def refusecase(name, disc, want, wiped_want):
    for wiped, w in ((0, want), (1, wiped_want)):
        fresh(wiped, F, discipline=disc, condition=0); poke(T['TAMER_ITEM'] + 8, '<i', 0); poke(T['ITEM_SCOLD_FLAG'], 'b', 0); call('partnerWillRefuseItem()')
        flag = struct.unpack('b', bytes.fromhex(emu('peek', hex(T['ITEM_SCOLD_FLAG']), '1').strip().split('\n')[-1].split('  ', 1)[1].replace(' ', '')))[0]
        ok(f'{name}{" (table wiped)" if wiped else ""}', flag, w)
refusecase('a partner with no discipline refuses (scold flag 1)', -100, 1, 0)
refusecase('a disciplined partner accepts', 100, 0, 0)
PY
tools/dev/emulator.py stop >/dev/null
