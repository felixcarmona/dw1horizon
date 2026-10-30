# The Python view of script 105 of DG.SCN: screen 109 Native Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

forest = screen(Screen.native_forest_109)
dokunemon0 = forest.npc(Species.Dokunemon, slot=0)
agumon = forest.npc(Species.Agumon, slot=2)
modokibetamon3 = forest.npc(Species.ModokiBetamon, slot=3)
dokunemon1 = forest.npc(Species.Dokunemon, slot=1)
modokibetamon4 = forest.npc(Species.ModokiBetamon, slot=4)
t5 = text.s105.sec5
t52 = text.s105.sec52
t6 = text.s105.sec6
t7 = text.s105.sec7
t8 = text.s105.sec8
t9 = text.s105.sec9

@forest.on_enter
def enter():    # section 254
    if engine.prosperity < 10:
        objects[18].hide()
        objects[23].show()
    else:
        objects[18].show()
        objects[23].hide()
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(1150, -1450))
    roll = random.roll(99)
    if roll <= 29:
        spawn_item(Item.Digimushrm, at=(550, -2150))
    roll = random.roll(99)
    if roll <= 39:
        spawn_item(Item.Digimushrm, at=(-1350, 550))
    if engine.prosperity >= 25:
        objects[28].hide()
        objects[29].hide()
        objects[30].hide()
        objects[31].hide()
        objects[32].hide()
        objects[33].hide()

@dokunemon0.on_talk
def talk():    # section 5
    recruitable(dokunemon0, line=t5.u0)

@agumon.on_talk
def talk():    # section 6
    tamer.say(t6.u0)
    tamer.play(15)
    wait(1000)
    tamer.play(anim.idle)
    say(t6.u1)
    tamer.say(t6.u2)
    fight(agumon, escape=False)
    face(tamer)
    tamer.face(agumon)
    partner.face(agumon)
    tamer.arrived()
    partner.arrived()
    say(t6.u3)
    play(18)
    tamer.say(t6.u4)
    tamer.play(25)
    tamer.say(t6.u5)
    tamer.play(19)
    tamer.say(t6.u6)
    tamer.play(anim.idle)
    play(anim.idle)
    say(t6.u7)
    play(19)
    say(t6.u8)
    hide_hud()
    play(22, wait=True)
    play(22)
    say(t6.u9)
    hide_hud()
    walk_away(2400, 1663, looks=3)
    send_to_city(line=t6.u10, camera=False)
    camera.on(tamer, speed=10)
    camera.arrived()
    tamer.say(t6.u11)
    tamer.play(anim.tamer_victory)
    wait(1000)
    tamer.play(anim.idle)

@modokibetamon3.on_talk
def talk():    # section 7
    recruitable(modokibetamon3, line=t7.u0)

@dokunemon1.on_talk
def talk():    # section 8
    recruitable(dokunemon1, line=t8.u0)

@modokibetamon4.on_talk
def talk():    # section 9
    recruitable(modokibetamon4, line=t9.u0)

@forest.on_step(0)
def step0():    # section 51
    tamer.walk(2300, 1600, wait=False)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=0)
                    return
                warp(Screen.file_city_191, entry=0)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=0)
                return
            warp(Screen.file_city_190, entry=0)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=0)
                return
            warp(Screen.file_city_194, entry=0)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=0)
            return
        warp(Screen.file_city_189, entry=0)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=0)
                    return
                warp(Screen.file_city_183, entry=0)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=0)
                return
            warp(Screen.file_city_182, entry=0)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=0)
                return
            warp(Screen.file_city_186, entry=0)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=0)
            return
        warp(Screen.file_city_181, entry=0)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=0)
                return
            warp(Screen.file_city_198, entry=0)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=0)
            return
        warp(Screen.file_city_197, entry=0)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=0)
            return
        warp(Screen.file_city_201, entry=0)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=0)
        return
    warp(Screen.file_city_180, entry=0)
    return

@forest.on_step(1)
def step1():    # section 52
    if not recruited(Species.Agumon):
        tamer.say(t52.u0)
        tamer.run(-1115, -1503)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if native_forest_rockslide_cleared:
        tamer.walk(-2000, -1725, wait=False)
        warp(Screen.native_forest_111, entry=0)
    tamer.walk(-2000, -1725, wait=False)
    warp(Screen.native_forest_110, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 51, 52)
