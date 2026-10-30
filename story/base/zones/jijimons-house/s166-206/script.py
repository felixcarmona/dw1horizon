# The Python view of script 166 of DG.SCN: screen 206 Jijimon's house.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

house = screen(Screen.jijimons_house_206)
botamon = house.npc(Species.Botamon, slot=0)
monzaemon = house.npc(Species.Monzaemon138, slot=1)
airdramon = house.npc(Species.Airdramon131, slot=2)
slot3 = house.npc(None, slot=3)    # the .MAP has Jijimon here; the script spawns what stands here
t5 = text.s166.sec5
t6 = text.s166.sec6
t60 = text.s166.sec60
t7 = text.s166.sec7

@house.on_enter
def enter():    # section 254
    if airdramon_ambush_fought and not engine.game_beaten:
        airdramon.play(30)
    if recruited(Species.Monzaemon):
        monzaemon.play(30)

@house.on_step(9)
def step9():    # section 60
    botamon.leave()
    raw.unload_digimon(Species.Botamon)
    load(Species.Jijimon)
    spawn(Species.Jijimon, slot=3)
    slot3.face(tamer)
    wait(1000)
    slot3.say(t60.u0)
    tamer.say(t60.u1)
    slot3.say(t60.u2)
    tamer.say(t60.u3)
    wait(2000)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=2)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=2)
            warp(Screen.file_city_168, entry=2)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=2)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=2)
        warp(Screen.file_city_171, entry=2)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=2)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=2)
        warp(Screen.file_city_174, entry=2)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=2)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=2)
    warp(Screen.file_city_177, entry=2)

@botamon.on_talk
def talk():    # section 5
    say(t5.u0)

@monzaemon.on_talk(scene=True)
def talk():    # section 6
    tamer.say(t6.u0)

@airdramon.on_talk(scene=True)
def talk():    # section 7
    narrator.say(t7.u0)
    return

# the section table, in the order of the original header
sections(254, 60, 5, 6, 7)
