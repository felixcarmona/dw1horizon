# The Python view of script 167 of DG.SCN: screen 207 Birdra Transport.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

transport = screen(Screen.birdra_transport)
birdramon = transport.npc(Species.Birdramon143, slot=0)
leomon = transport.npc(Species.Leomon166, slot=1)
t6 = text.s167.sec6
t81 = text.s167.sec81

@transport.on_enter
def enter():    # section 254
    birdramon.play(30)

@transport.on_use(1)
def use1():    # section 81
    tamer.face(birdramon)
    wait(250)
    if not birdra_transport_intro_seen:
        birdra_transport_intro_seen.set()
        birdramon.say(t81.u0)
    call(Routine.birdramon_taxi, arg=5)

@birdramon.on_talk(scene=True)
def talk():    # section 5
    return use1()

@leomon.on_talk
def talk():    # section 6
    say(t6.u0)
    say(t6.u1)
    say(t6.u2)

@transport.on_step(0)
def step0():    # section 51
    tamer.walk(2200, -3000, wait=False)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=4)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=4)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=4)
            warp(Screen.file_city_168, entry=4)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=4)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=4)
        warp(Screen.file_city_171, entry=4)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=4)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=4)
        warp(Screen.file_city_174, entry=4)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=4)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=4)
    warp(Screen.file_city_177, entry=4)

# the section table, in the order of the original header
sections(254, 81, 5, 6, 51)
