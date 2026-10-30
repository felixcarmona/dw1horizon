# The Python view of script 139 of DG.SCN: screen 145 Costume House.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

house = screen(Screen.costume_house)
monzaemon = house.npc(Species.Monzaemon138, slot=0)
t81 = text.s139.sec81

@house.on_enter
def enter():    # section 254
    monzaemon_costume_tried.clear()
    if partner.species == Species.Monzaemon or recruited(Species.Monzaemon):
        return
    monzaemon.play(31)
    wait(250)

@monzaemon.on_talk
def talk():    # section 5
    return use1()

@house.on_use(1)
def use1():    # section 81
    engine.cutscene.set()
    if recruited(Species.WaruMonzaemon) or partner.species == Species.Monzaemon:
        return
    tamer.play(16)
    wait(750)
    tamer.say(t81.u0)
    hide_hud()
    tamer.play(anim.idle)
    if monzaemon_costume_tried:
        return
    monzaemon_costume_tried.set()
    monzaemon.play(28)
    tamer.play(15)
    wait(2000)
    tamer.walk(1079, -180)
    tamer.face(monzaemon)
    wait(500)
    tamer.say(t81.u1)
    hide_hud()
    if partner_type == 11:
        raw.entity_walk_to_entity(partner, 0, monzaemon)
        partner.arrived()
        tamer.face(partner)
        wait(250)
        tamer.say(t81.u2)
        hide_hud()
        wait(500)
        monzaemon.arrived()
        monzaemon.leave()
        engine.arg.set(14)
        raw.call_digimon_routine(DigimonRoutine.forced_evolution)
        narrator.arrived()
        wait(500)
        tamer.say(t81.u3)
        return
    tamer.say(t81.u4)
    tamer.face(partner)
    partner.walk(900, 90)
    partner.play(25)
    wait(1000)
    partner.play(anim.refuse)
    wait(1500)
    tamer.say(t81.u5)
    return

# the section table, in the order of the original header
sections(254, 5, 81)
