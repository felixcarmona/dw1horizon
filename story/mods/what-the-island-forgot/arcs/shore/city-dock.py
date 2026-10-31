# File City's dock (script 162, step trigger 4, screens 168-179): once Whamon has joined the city, the first time the
# tamer comes to the ferry Whamon tells what it felt when the island grew, and offers the one ride only it can give, to
# the old shore under Freezeland's cliffs (309, the Drowned Shore). Afterwards the ride is
# offered first, and "Somewhere else" opens the ferry's own menu.
#
# Before that, the first time at the dock after the beach cave, Whamon offers to chase WaruSeadramon off (§3.3): five
# days away (the ferry is closed), or let him go (sea-ambush.py at Factorial Town's dock). Hurt in that ambush, Whamon
# keeps the ferry closed ten days. Save both day and year so a delayed first visit cannot alias a later year.
# The waits come before the old shore's offer: they end the step while Whamon is away.
from dw import *
from dw.base.file_city_168 import city_168, whamon
from ...state import seadramon_chased, seadramon_let_go, whamon_left_day, whamon_left_year, whamon_hurt
shore_told = flag()
city_docks = screen(168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179)

def to_the_dock():
    tamer.run(2594, 630, wait=False)
    partner.run(2189, 545, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.turn(2128)
    partner.turn(2128)

@city_168.on_step(4, when=recruited(Species.Whamon) and not seadramon_chased and not seadramon_let_go)
def after_him():
    to_the_dock()
    whamon.say("WaruSeadramon is still out there, in my sea.", "I could chase him far away. It would take me five days.")
    if whamon.ask(yes="Go after him", no="Let him go"):
        whamon.say("Then wait for me. In five days the sea will be quiet.")
        seadramon_chased.set()
        whamon_left_day.set(clock.day)
        whamon_left_year.set(clock.year)
        whamon_left_year.add(1)
        whamon.leave()
        away()
    else:
        whamon.say("As you wish. But he will remember us.")
        seadramon_let_go.set()

def elapsed_days():
    # The VM compares u8 values to constants only. Subtract the saved year/day with
    # bounded countdowns in scratch pstats; no arithmetic extension or resident RAM.
    # p90-p92 are overwritten before use, and no dialogue/yield occurs inside these loops.
    pstat(91).set(255)
    if whamon_left_year >= 1 and whamon_left_year <= 100 and whamon_left_day < 30:
        pstat(90).set(clock.year)
        pstat(92).set(whamon_left_year)
        pstat(92).sub(1)          # saved years are 1-100; 0 means an undated old save
        while pstat(92) >= 1:
            if pstat(90) == 0:
                pstat(90).set(100)
            pstat(90).sub(1)
            pstat(92).sub(1)
        if pstat(90) == 0 or pstat(90) == 1:
            pstat(91).set(clock.day)
            if pstat(90) == 1:
                pstat(91).add(30)
            pstat(92).set(whamon_left_day)
            while pstat(92) >= 1:
                if pstat(91) == 0:
                    pstat(91).set(255)  # clock moved backwards within the year
                    break
                pstat(91).sub(1)
                pstat(92).sub(1)

# Presence cannot test the saved date. Remove him after setup on every square
# layout, using the same non-yielding calculation as the dock's closed-ferry line.
@city_docks.on_enter(when=recruited(Species.Whamon) and (seadramon_chased or whamon_hurt))
def city_ferry_presence():
    elapsed_days()
    if whamon_hurt:
        if pstat(91) < 10:
            whamon.leave()
    elif seadramon_chased:
        if pstat(91) < 5:
            whamon.leave()

@city_168.on_step(4, when=seadramon_chased and not whamon_hurt)
def chasing():
    elapsed_days()
    if pstat(91) < 5:
        away()
    whamon_left_day.set(255)

@city_168.on_step(4, when=whamon_hurt)
def resting():
    elapsed_days()
    if pstat(91) < 10:
        hurt()
    whamon_hurt.clear()
    whamon_left_day.set(255)

@city_168.on_step(4, when=recruited(Species.Whamon) and (seadramon_chased or seadramon_let_go) and not shore_told)
def the_old_shore():
    tamer.run(2594, 630, wait=False)
    partner.run(2189, 545, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.turn(2128)
    partner.turn(2128)
    whamon.say("Before you go... I have something to tell you.", "When I was young, the island grew.",
               "The sea pulled back, and my cave ended up under new ground.")
    whamon.say("The old shore is still there, under the cliffs of Freezeland.", "No one walks to it. I can swim you there.")
    shore_told.set()
    if whamon.ask(yes="Take me there", no="Maybe later"):
        warp(309, entry=0)

@city_168.on_step(4, when=recruited(Species.Whamon) and (seadramon_chased or seadramon_let_go) and shore_told)
def to_the_shore_again():
    tamer.run(2594, 630, wait=False)
    partner.run(2189, 545, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.turn(2128)
    partner.turn(2128)
    if whamon.ask(yes="To the old shore", no="Somewhere else"):
        warp(309, entry=0)

def away():
    tamer.say("Whamon's still out at sea, chasing WaruSeadramon. No ferry for now.")
    tamer.walk(1556, 348)
    dws("return;")                # no ferry: the game's own dock menu must not open

def hurt():
    tamer.say("Whamon is still resting from the fight with WaruSeadramon. No ferry for now.")
    tamer.walk(1556, 348)
    dws("return;")
