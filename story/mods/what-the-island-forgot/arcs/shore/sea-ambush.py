# 152, Factorial Town's dock (§3.3, "Let him go"): the first crossing after Giromon has joined, WaruSeadramon is waiting
# where Whamon comes ashore. A battle with no running. Whamon is marked hurt before it and cleared after a win: a lost
# battle wakes the tamer in Jijimon's house (no code runs after it), and Whamon stays hurt, the ferry closed ten days
# (city-dock.py). Whamon is back when the screen loads again.
from dw import *
from ...state import seadramon_let_go, sea_ambush_fought, whamon_hurt, whamon_left_day, whamon_left_year
from dw.base.factorial_town_152 import town, whamon

waruseadramon = town.npc(Species.WaruSeadramon, at=(-1250, -1850), range=0, autotalk=True,
                         when=seadramon_let_go and recruited(Species.Giromon) and not sea_ambush_fought)

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
