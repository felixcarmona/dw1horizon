# The Python view of script 132 of DG.SCN: screen 137 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_137)
frigimon = freezeland.npc(Species.Frigimon145, slot=0)
t5 = text.s132.sec5
t51 = text.s132.sec51

@freezeland.on_enter
def enter():    # section 254
    pass

@freezeland.on_step(0)
def step0():    # section 51
    raw.remove_condition(32)
    raw.remove_condition(64)
    frigimon.face(tamer)
    partner.face(tamer)
    tamer.play(24)
    wait(750)
    tamer.say(t51.u0)
    tamer.play(anim.idle)
    tamer.turn(1050)
    wait(1000)
    tamer.turn(1561)
    wait(1000)
    tamer.face(frigimon)
    tamer.play(15)
    wait(750)
    tamer.say(t51.u1)
    tamer.play(anim.idle)
    tamer.turn(1050)
    wait(250)
    tamer.face(frigimon)
    frigimon.say(t51.u2)
    tamer.turn(25)
    wait(250)
    tamer.face(partner)
    tamer.say(t51.u3)
    frigimon.say(t51.u4)
    tamer.face(frigimon)
    tamer.play(25)
    wait(750)
    tamer.say(t51.u5)
    tamer.play(anim.idle)
    wait(1500)
    tamer.face(partner)
    tamer.play(7)
    wait(750)
    tamer.say(t51.u6)
    tamer.play(anim.idle)
    raw.store_digimon_type(partner_type)
    frigimon.say(t51.u7)
    tamer.face(frigimon)
    wait(1000)
    tamer.face(partner)
    tamer.play(19)
    wait(750)
    tamer.say(t51.u8)
    tamer.play(anim.idle)
    tamer.face(frigimon)
    tamer.say(t51.u9)
    frigimon.say(t51.u10)
    tamer.say(t51.u11)
    tamer.run(93, -1700, wait=False)
    wait(1000)
    partner.run(93, -1700, wait=False)
    wait(1000)
    frigimon.face(tamer)
    tamer.arrived()
    partner.arrived()
    frigimon.say(t51.u12)
    digivolve_scene_seen.set()
    warp(Screen.freezeland_94, entry=2)

@frigimon.on_talk
def talk():    # section 5
    if partner.species in (Species.Agumon, Species.Greymon, Species.Tyrannomon, Species.Meramon, Species.Monochromon):
        pass
    elif partner.species in (Species.Kabuterimon, Species.Kunemon, Species.Kuwagamon, Species.Botamon, Species.Koromon):
        pass
    elif partner.species in (Species.Punimon, Species.Tsunomon, Species.Poyomon, Species.Tokomon, Species.Yuramon):
        pass
    elif partner.species != Species.Tanemon and partner.species != Species.Birdramon:
        tamer.say(t5.u0)
        say(t5.u1)
        tamer.say(t5.u2)
        face(partner)
        say(t5.u3)
        face(tamer)
        tamer.say(t5.u4)
        say(t5.u5)
        tamer.play(19)
        wait(750)
        tamer.say(t5.u6)
        tamer.play(anim.idle)
        play(11)
        wait(250)
        say(t5.u7)
        tamer.say(t5.u8)
        say(t5.u9)
        run(-540, -336)
        walk_away(93, -1700, looks=3)
        send_to_city(line=t5.u10, species=Species.Frigimon, prosperity=2, camera=False)
        return
    say(t5.u11)
    tamer.play(15)
    wait(750)
    tamer.say(t5.u12)
    tamer.play(anim.idle)

# the section table, in the order of the original header
sections(254, 51, 5)
