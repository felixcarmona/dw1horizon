# The Python view of script 175 of DG.SCN: screen 215 Restaurant.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

restaurant = screen(Screen.restaurant_215)
cook = restaurant.npc(None, slot=0)    # the .MAP has Meramon133 here; the script spawns what stands here
giromon = restaurant.npc(Species.Giromon161, slot=6)
t6 = text.s175.sec6
t81 = text.s175.sec81

@restaurant.on_enter
def enter():    # section 254
    pass

@restaurant.on_use(1)
def use1():    # section 81
    tamer.face(cook)
    cook.face(tamer)
    if restaurant_chef_met.meramon or restaurant_chef_met.tyrannomon or restaurant_chef_met.garurumon or restaurant_chef_met.frigimon:
        pass
    elif recruited(Species.Meramon) and not restaurant_chef_met.meramon and restaurant_chef == 0:
        cook.say(t81.u0)
        restaurant_chef_met.meramon.set()
        return
    elif recruited(Species.Tyrannomon) and not restaurant_chef_met.tyrannomon and restaurant_chef == 1:
        cook.say(t81.u1)
        restaurant_chef_met.tyrannomon.set()
        return
    elif recruited(Species.Garurumon) and not restaurant_chef_met.garurumon and restaurant_chef == 2:
        cook.say(t81.u2)
        restaurant_chef_met.garurumon.set()
        return
    elif recruited(Species.Frigimon) and not restaurant_chef_met.frigimon and restaurant_chef == 3:
        cook.say(t81.u3)
        restaurant_chef_met.frigimon.set()
        return
    if recruited(Species.Meramon) and not restaurant_chef_met.meramon and restaurant_chef == 0:
        cook.say(t81.u4)
        restaurant_chef_met.meramon.set()
        return
    if recruited(Species.Tyrannomon) and not restaurant_chef_met.tyrannomon and restaurant_chef == 1:
        cook.say(t81.u5)
        restaurant_chef_met.tyrannomon.set()
        return
    if recruited(Species.Garurumon) and not restaurant_chef_met.garurumon and restaurant_chef == 2:
        cook.say(t81.u6)
        restaurant_chef_met.garurumon.set()
        return
    if recruited(Species.Frigimon) and not restaurant_chef_met.frigimon and restaurant_chef == 3:
        cook.say(t81.u7)
        restaurant_chef_met.frigimon.set()
        return
    if restaurant_chef in (0, 1, 2):
        jump_to_script(217, 51)
    if restaurant_chef in (3, 4, 5):
        pass
    else:
        return giromon.talk()
    jump_to_script(218, 51)

@giromon.on_talk
def talk():    # section 6
    if not jukebox_intro_seen:
        say(t6.u0)
        jukebox_intro_seen.set()
    call(Routine.jukebox, arg=6)

@restaurant.on_step(0)
def step0():    # section 51
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=4)
                    return
                warp(Screen.file_city_191, entry=4)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=4)
                return
            warp(Screen.file_city_190, entry=4)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=4)
                return
            warp(Screen.file_city_194, entry=4)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=4)
            return
        warp(Screen.file_city_189, entry=4)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=4)
                    return
                warp(Screen.file_city_183, entry=4)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=4)
                return
            warp(Screen.file_city_182, entry=4)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=4)
                return
            warp(Screen.file_city_186, entry=4)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=4)
            return
        warp(Screen.file_city_181, entry=4)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=4)
                return
            warp(Screen.file_city_198, entry=4)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=4)
            return
        warp(Screen.file_city_197, entry=4)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=4)
            return
        warp(Screen.file_city_201, entry=4)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=4)
        return
    warp(Screen.file_city_180, entry=4)
    return

# the section table, in the order of the original header
sections(254, 81, 6, 51)
