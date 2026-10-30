# The Python view of script 164 of DG.SCN: screen 204 File City.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

city = screen(Screen.file_city_204)
jijimon0 = city.npc(Species.Jijimon, slot=0)
tokomon1 = city.npc(Species.Tokomon, slot=1)
jijimon2 = city.npc(Species.Jijimon, slot=2)
jijimon3 = city.npc(Species.Jijimon, slot=3)
yuramon = city.npc(Species.Yuramon, slot=4)
tanemon = city.npc(Species.Tanemon, slot=6)
t11 = text.s164.sec11
t5 = text.s164.sec5
t6 = text.s164.sec6
t8 = text.s164.sec8
t9 = text.s164.sec9

@city.on_enter
def enter():    # section 254
    call(Routine.save_clock_speed, arg=0)
    objects[73].hide()
    objects[74].hide()
    objects[75].hide()
    objects[76].hide()
    objects[77].hide()
    objects[78].hide()
    objects[79].show()
    objects[80].show()
    objects[81].show()
    objects[82].show()
    objects[83].show()

@city.on_step(3)
def step3():    # section 54
    if debug_test_npcs:
        jump_to_script(193, 54)
    return step15()

@city.on_step(0)
def step0():    # section 51
    tamer.walk(250, -5000, wait=False)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=1)
                    return
                warp(Screen.file_city_191, entry=1)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=1)
                return
            warp(Screen.file_city_190, entry=1)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=1)
                return
            warp(Screen.file_city_194, entry=1)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=1)
            return
        warp(Screen.file_city_189, entry=1)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=1)
                    return
                warp(Screen.file_city_183, entry=1)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=1)
                return
            warp(Screen.file_city_182, entry=1)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=1)
                return
            warp(Screen.file_city_186, entry=1)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=1)
            return
        warp(Screen.file_city_181, entry=1)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=1)
                return
            warp(Screen.file_city_198, entry=1)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=1)
            return
        warp(Screen.file_city_197, entry=1)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=1)
            return
        warp(Screen.file_city_201, entry=1)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=1)
        return
    warp(Screen.file_city_180, entry=1)
    return

@city.on_step(1)
def step1():    # section 52
    tamer.walk(-3000, -2588, wait=False)
    warp(Screen.green_gym, entry=1)

@jijimon0.on_talk
def talk():    # section 5
    partner.set(tournaments_won=99)
    partner.set(tournament_wins=99)
    partner.set(tournaments_lost=99)
    say(t5.u0)
    raw.store_date(date_year)
    say(t5.u1)
    say(t5.u2)
    match choose(a=t5.m0.o0, b=t5.m0.o1, c=t5.m0.o2):
        case "a":
            match choose(a=t5.m1.o0, b=t5.m1.o1, c=t5.m1.o2):
                case "a":
                    warp(Screen.path_thru_mt_panorama_18, entry=0)
                    warp(Screen.tropical_jungle_12, entry=0)
                case "b":
                    warp(Screen.tropical_jungle_12, entry=0)
                case _:
                    return
            warp(Screen.drill_tunnel_24, entry=0)
            warp(Screen.gear_savanna_69, entry=0)
            warp(Screen.grey_lords_mansion_52, entry=0)
            warp(Screen.great_canyon_top_area_44, entry=0)
        case "b":
            match choose(a=t5.m2.o0, b=t5.m2.o1, c=t5.m2.o2):
                case "a":
                    warp(Screen.gear_savanna_69, entry=0)
                    warp(Screen.grey_lords_mansion_52, entry=0)
                case "b":
                    warp(Screen.grey_lords_mansion_52, entry=0)
                case _:
                    return
            warp(Screen.great_canyon_top_area_44, entry=0)
        case "c":
            match choose(a=t5.m3.o0, b=t5.m3.o1, c=t5.m3.o2):
                case "a":
                    warp(Screen.ancient_dino_region, entry=0)
                    warp(Screen.ancient_speedy_region_86, entry=0)
                case "b":
                    warp(Screen.ancient_speedy_region_86, entry=0)
                case _:
                    return
            match choose(a=t5.m4.o0, b=t5.m4.o1, c=t5.m4.o2):
                case "a":
                    warp(Screen.freezeland_134, entry=0)
                    warp(Screen.dragon_eye_lake_6, entry=0)
                case "b":
                    warp(Screen.dragon_eye_lake_6, entry=0)
                case _:
                    return
            warp(Screen.lava_cave_31, entry=0)
            return
        case _:
            return
    warp(Screen.ancient_dino_region, entry=0)
    warp(Screen.ancient_speedy_region_86, entry=0)
    match choose(a=t5.m4.o0, b=t5.m4.o1, c=t5.m4.o2):
        case "a":
            warp(Screen.freezeland_134, entry=0)
            warp(Screen.dragon_eye_lake_6, entry=0)
        case "b":
            warp(Screen.dragon_eye_lake_6, entry=0)
        case _:
            return
    warp(Screen.lava_cave_31, entry=0)

@tokomon1.on_talk
def talk():    # section 6
    partner.set(lives=3)
    jijimon0.say(t6.u0)
    say(t6.u1)
    match choose(a=t6.m0.o0, b=t6.m0.o1, c=t6.m0.o2):
        case "a":
            engine.arg.set(11)
            raw.call_digimon_routine(DigimonRoutine.forced_evolution)
            narrator.arrived()
            return
        case "b":
            engine.arg.set(39)
            raw.call_digimon_routine(DigimonRoutine.forced_evolution)
            narrator.arrived()
            return
        case "c":
            engine.arg.set(1)
            raw.call_digimon_routine(DigimonRoutine.forced_evolution)
            narrator.arrived()
            return
        case _:
            return

@jijimon2.on_talk
def talk():    # section 7
    jump_to_script(209, 5)

@city.on_step(15)
def step15():    # section 66
    if debug_city_entered or debug_mode:
        return
    debug_city_entered.set()
    return L98()

@jijimon3.on_talk
def talk():    # section 8
    match jijimon3.choose(a=t8.m0.o0, b=t8.m0.o1, c=t8.m0.o2):
        case "a":
            partner.set(hp=1)
            partner.set(lifetime=1)
            return
        case "b":
            return L98()
        case "c":
            return L99()
        case _:
            return

@tanemon.on_talk
def talk():    # section 11
    if not meat_farm_explained:
        say(t11.u0)
        tamer.say(t11.u1)
        say(t11.u2)
        tamer.say(t11.u3)
        say(t11.u4)
    else:
        roll = random.roll(3)    # Horizon: a big harvest 1 day in 4 (the original: roll(9), 1 in 10)
        if meat_farm_days >= 1 and roll <= 0:
            say(t11.u10)
        else:
            if meat_farm_days >= 1:
                say(t11.u17)
            else:
                say(t11.u24)
                return
            if has(Item.Meat, 99):
                say(t11.u18)
                return
            if has(Item.Meat, 97):
                say(t11.u19)
                narrator.say(t11.u20)
                give(Item.Meat, 3)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.Meat, 3)
            if engine.item_did_not_fit:
                say(t11.u21)
                return
            narrator.say(t11.u22)
            say(t11.u23)
            meat_farm_days.set(0)
            return
        if has(Item.Meat, 99):
            say(t11.u11)
            return
        if has(Item.Meat, 95):
            say(t11.u12)
            narrator.say(t11.u13)
            give(Item.Meat, 5)
            meat_farm_explained.set()
            meat_farm_days.set(0)
            return
        give(Item.Meat, 5)
        if engine.item_did_not_fit:
            say(t11.u14)
            return
        narrator.say(t11.u15)
        say(t11.u16)
        meat_farm_days.set(0)
        return
    give(Item.Meat, 3)
    if has(Item.Meat, 99):
        say(t11.u5)
        meat_farm_days.set(1)
        return
    if has(Item.Meat, 97):
        say(t11.u6)
        narrator.say(t11.u7)
        meat_farm_explained.set()
        meat_farm_days.set(0)
        return
    if engine.item_did_not_fit:
        say(t11.u8)
        return
    narrator.say(t11.u9)
    meat_farm_explained.set()
    meat_farm_days.set(0)
    return

@yuramon.on_talk
def talk():    # section 9
    say(t9.u0)

@city.on_step(2)
def step2():    # section 53
    tamer.walk(23, -842, wait=False)
    warp(Screen.jijimons_house, entry=0)
    return

def L98():    # shared code (the disc's label L98)
    debug_mode.set()
    debug_test_npcs.set()
    warp(Screen.file_city_238, entry=9)

def L99():    # shared code (the disc's label L99)
    match choose(a=t8.m1.o0, b=t8.m1.o1, c=t8.m1.o2):
        case "a":
            raw.store_date(date_year)
            raw.add_minutes_to_date_at(date_year, 60)
            raw.advance_to_date_at(date_year)
            return
        case "b":
            raw.store_date(date_year)
            raw.add_minutes_to_date_at(date_year, 360)
            raw.advance_to_date_at(date_year)
            return
        case "c":
            raw.store_date(date_year)
            raw.add_minutes_to_date_at(date_year, 14400)
            raw.advance_to_date_at(date_year)
            return
        case _:
            return

# the section table, in the order of the original header
sections(254, 54, 51, 52, 5, 6, 7, 66, 8, 11, 9, 53)
