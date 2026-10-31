# 152, Factorial Town's dock (§3.3, "Let him go"): the first crossing after Giromon has joined, WaruSeadramon is waiting
# where Whamon comes ashore. A battle with no running. Whamon is marked hurt before it and cleared after a win: a lost
# battle wakes the tamer in Jijimon's house (no code runs after it), and Whamon stays hurt, the ferry closed ten days
# (city-dock.py). After a win, Whamon is back when the screen loads again; during recovery he stays off both docks.
from dw import *
from ...state import seadramon_chased, seadramon_let_go, sea_ambush_fought, whamon_hurt, whamon_left_day, whamon_left_year
from dw.base.factorial_town_152 import town, whamon

waruseadramon = town.npc(Species.WaruSeadramon, at=(-1250, -1850), range=0, autotalk=True,
                         when=seadramon_let_go and recruited(Species.Giromon) and not sea_ambush_fought)

# Story functions belong to one script; keep this calculation identical to
# city-dock.py's elapsed_days() (the calendar regression checks both copies).
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

@town.on_enter(when=seadramon_chased or whamon_hurt)
def factory_ferry_presence():
    elapsed_days()
    if whamon_hurt:
        if pstat(91) < 10:
            whamon.leave()
    elif seadramon_chased:
        if pstat(91) < 5:
            whamon.leave()

# The dock's use tile still works without an NPC. Keep it from addressing the
# absent Whamon or offering his base ferry menu while the same wait is active.
@town.on_use(1, when=seadramon_chased or whamon_hurt)
def factory_ferry_closed():
    elapsed_days()
    if whamon_hurt:
        if pstat(91) < 10:
            tamer.say("Whamon is still resting from the fight with WaruSeadramon. No ferry for now.")
            dws("return;")
    elif seadramon_chased:
        if pstat(91) < 5:
            tamer.say("Whamon's still out at sea, chasing WaruSeadramon. No ferry for now.")
            dws("return;")

@waruseadramon.on_talk(scene=True)
def the_ambush():
    face(tamer)
    tamer.face(waruseadramon)
    partner.face(waruseadramon)
    say("Remember me? You let me go. That was your mistake.")
    sea_ambush_fought.set()
    whamon_hurt.set()
    whamon_left_day.set(clock.day)
    whamon_left_year.set(clock.year)
    whamon_left_year.add(1)
    # Whamon dives: a battle starts only once every bystander on screen has walked off it (BTL_handleBattleIntro), and
    # Whamon, in the water, cannot walk; with it there the battle never got past its "BATTLE" text
    sound(8, 3)
    whamon.leave()
    if fight(waruseadramon, escape=False) != "won":
        return
    whamon_hurt.clear()
    say("Grrr... This sea is not big enough for me anymore...")
    sound(8, 3)
    wait(1000)
    leave()
