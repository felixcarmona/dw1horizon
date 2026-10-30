# The Python view of script 169 of DG.SCN: screen 209 Treasure Hunt.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

hunt = screen(Screen.treasure_hunt)
drimogemon = hunt.npc(Species.Drimogemon158, slot=0)
gabumon = hunt.npc(Species.Gabumon139, slot=1)
t6 = text.s169.sec6
t81 = text.s169.sec81

@hunt.on_enter
def enter():    # section 254
    if drimogemon_job_days < 3 and treasure_hunt.cheap_ordered:
        raw.entity_move_to(drimogemon, 169, 2232, 5, 0)
        drimogemon.arrived()
    if drimogemon_job_days < 10 and treasure_hunt.pricey_ordered:
        raw.entity_move_to(drimogemon, 169, 2232, 5, 0)
        drimogemon.arrived()
        return

@hunt.on_use(1)
def use1():    # section 81
    drimogemon.face(tamer)
    tamer.face(drimogemon)
    wait(250)
    camera.to(184, 686, speed=10)
    camera.arrived()
    if not treasure_hunt_intro_seen:
        treasure_hunt_intro_seen.set()
        drimogemon.say(t81.u0)
        return
    if treasure_hunt.cheap_ordered or treasure_hunt.pricey_ordered:
        if drimogemon_job_days < 3 and treasure_hunt.cheap_ordered:
            pass
        elif drimogemon_job_days >= 10 or not treasure_hunt.pricey_ordered:
            drimogemon.say(t81.u9)
            if treasure_hunt.cheap_ordered:
                pass
            elif treasure_hunt.pricey_ordered:
                treasure_hunt.pricey_ordered.clear()
                if not recruited(Species.Gabumon):
                    if treasure_hunt.pricey_roll <= 0:
                        give(Item.OffChip)
                        random_roll.set(23)
                    elif treasure_hunt.pricey_roll <= 1:
                        give(Item.HPChip)
                        random_roll.set(27)
                    elif treasure_hunt.pricey_roll <= 2:
                        give(Item.BrainChip)
                        random_roll.set(25)
                    elif treasure_hunt.pricey_roll <= 3:
                        give(Item.DefChip)
                        random_roll.set(24)
                    elif treasure_hunt.pricey_roll <= 4:
                        give(Item.MPChip)
                        random_roll.set(28)
                    elif treasure_hunt.pricey_roll <= 5:
                        give(Item.QuickChip)
                        random_roll.set(26)
                    elif treasure_hunt.pricey_roll <= 6:
                        give(Item.KogaLaws)
                        random_roll.set(90)
                    elif treasure_hunt.pricey_roll <= 7:
                        give(Item.Flamingwing)
                        random_roll.set(73)
                    elif treasure_hunt.pricey_roll <= 8:
                        give(Item.TornTatter)
                        random_roll.set(82)
                    elif treasure_hunt.pricey_roll <= 20:
                        give(Item.SupRecovery)
                        random_roll.set(3)
                    elif treasure_hunt.pricey_roll <= 29:
                        give(Item.Restore)
                        random_roll.set(11)
                    elif treasure_hunt.pricey_roll <= 49:
                        give(Item.Omnipotent)
                        random_roll.set(9)
                    elif treasure_hunt.pricey_roll <= 1:
                        give(Item.OffChip)
                        random_roll.set(23)
                    elif treasure_hunt.pricey_roll <= 3:
                        give(Item.HPChip)
                        random_roll.set(27)
                    elif treasure_hunt.pricey_roll <= 5:
                        give(Item.BrainChip)
                        random_roll.set(25)
                    elif treasure_hunt.pricey_roll <= 7:
                        give(Item.DefChip)
                        random_roll.set(24)
                    elif treasure_hunt.pricey_roll <= 9:
                        give(Item.MPChip)
                        random_roll.set(28)
                    elif treasure_hunt.pricey_roll <= 11:
                        give(Item.QuickChip)
                        random_roll.set(26)
                    elif treasure_hunt.pricey_roll <= 13:
                        give(Item.KogaLaws)
                        random_roll.set(90)
                    elif treasure_hunt.pricey_roll <= 15:
                        give(Item.Flamingwing)
                        random_roll.set(73)
                    elif treasure_hunt.pricey_roll <= 17:
                        give(Item.TornTatter)
                        random_roll.set(82)
                    elif treasure_hunt.pricey_roll <= 21:
                        give(Item.SupRestore)
                        random_roll.set(12)
                    elif treasure_hunt.pricey_roll <= 33:
                        give(Item.Restore)
                        random_roll.set(11)
                    else:
                        if treasure_hunt.pricey_roll <= 49:
                            give(Item.Omnipotent)
                            random_roll.set(9)
                            if engine.item_did_not_fit:
                                drimogemon.say(t81.u10)
                                camera.on(tamer, speed=10)
                                camera.arrived()
                                return
                            narrator.say(t81.u11)
                            treasure_hunt.cheap_ordered.clear()
                            treasure_hunt.pricey_ordered.clear()
                        drimogemon.say(t81.u12)
                        camera.on(tamer, speed=10)
                        camera.arrived()
                        return
                    if engine.item_did_not_fit:
                        drimogemon.say(t81.u10)
                        camera.on(tamer, speed=10)
                        camera.arrived()
                        return
                    narrator.say(t81.u11)
                    treasure_hunt.cheap_ordered.clear()
                    treasure_hunt.pricey_ordered.clear()
                    drimogemon.say(t81.u12)
                    camera.on(tamer, speed=10)
                    camera.arrived()
                    return
                if treasure_hunt.pricey_roll <= 1:
                    give(Item.OffChip)
                    random_roll.set(23)
                elif treasure_hunt.pricey_roll <= 3:
                    give(Item.HPChip)
                    random_roll.set(27)
                elif treasure_hunt.pricey_roll <= 5:
                    give(Item.BrainChip)
                    random_roll.set(25)
                elif treasure_hunt.pricey_roll <= 7:
                    give(Item.DefChip)
                    random_roll.set(24)
                elif treasure_hunt.pricey_roll <= 9:
                    give(Item.MPChip)
                    random_roll.set(28)
                elif treasure_hunt.pricey_roll <= 11:
                    give(Item.QuickChip)
                    random_roll.set(26)
                elif treasure_hunt.pricey_roll <= 13:
                    give(Item.KogaLaws)
                    random_roll.set(90)
                elif treasure_hunt.pricey_roll <= 15:
                    give(Item.Flamingwing)
                    random_roll.set(73)
                elif treasure_hunt.pricey_roll <= 17:
                    give(Item.TornTatter)
                    random_roll.set(82)
                elif treasure_hunt.pricey_roll <= 21:
                    give(Item.SupRestore)
                    random_roll.set(12)
                elif treasure_hunt.pricey_roll <= 33:
                    give(Item.Restore)
                    random_roll.set(11)
                else:
                    if treasure_hunt.pricey_roll <= 49:
                        give(Item.Omnipotent)
                        random_roll.set(9)
                        if engine.item_did_not_fit:
                            drimogemon.say(t81.u10)
                            camera.on(tamer, speed=10)
                            camera.arrived()
                            return
                        narrator.say(t81.u11)
                        treasure_hunt.cheap_ordered.clear()
                        treasure_hunt.pricey_ordered.clear()
                    drimogemon.say(t81.u12)
                    camera.on(tamer, speed=10)
                    camera.arrived()
                    return
                if engine.item_did_not_fit:
                    drimogemon.say(t81.u10)
                    camera.on(tamer, speed=10)
                    camera.arrived()
                    return
                narrator.say(t81.u11)
                treasure_hunt.cheap_ordered.clear()
                treasure_hunt.pricey_ordered.clear()
                drimogemon.say(t81.u12)
                camera.on(tamer, speed=10)
                camera.arrived()
                return
            if recruited(Species.Gabumon):
                if treasure_hunt.cheap_roll <= 0:
                    give(Item.KogaLaws)
                    random_roll.set(90)
                elif treasure_hunt.cheap_roll <= 2:
                    give(Item.Flamingwing)
                    random_roll.set(73)
                elif treasure_hunt.cheap_roll <= 4:
                    give(Item.TornTatter)
                    random_roll.set(82)
                elif treasure_hunt.cheap_roll <= 12:
                    give(Item.SupRecovery)
                    random_roll.set(3)
                elif treasure_hunt.cheap_roll <= 15:
                    give(Item.Restore)
                    random_roll.set(11)
                elif treasure_hunt.cheap_roll <= 19:
                    give(Item.Omnipotent)
                    random_roll.set(9)
                elif treasure_hunt.cheap_roll <= 23:
                    give(Item.Protection)
                    random_roll.set(10)
                elif treasure_hunt.cheap_roll <= 33:
                    give(Item.LargeMP)
                    random_roll.set(6)
                elif treasure_hunt.cheap_roll <= 37:
                    give(Item.SOffDisk)
                    random_roll.set(19)
                elif treasure_hunt.cheap_roll <= 41:
                    give(Item.SDefDisk)
                    random_roll.set(20)
                elif treasure_hunt.cheap_roll <= 45:
                    give(Item.SSpeedDisk)
                    random_roll.set(21)
                elif treasure_hunt.cheap_roll <= 49:
                    give(Item.OmniDisk)
                    random_roll.set(18)
            elif treasure_hunt.cheap_roll <= 0:
                give(Item.KogaLaws)
                random_roll.set(90)
            elif treasure_hunt.cheap_roll <= 1:
                give(Item.Flamingwing)
                random_roll.set(73)
            elif treasure_hunt.cheap_roll <= 2:
                give(Item.TornTatter)
                random_roll.set(82)
            elif treasure_hunt.cheap_roll <= 12:
                give(Item.SupRecovery)
                random_roll.set(3)
            elif treasure_hunt.cheap_roll <= 15:
                give(Item.Restore)
                random_roll.set(11)
            elif treasure_hunt.cheap_roll <= 19:
                give(Item.Omnipotent)
                random_roll.set(9)
            elif treasure_hunt.cheap_roll <= 23:
                give(Item.Protection)
                random_roll.set(10)
            elif treasure_hunt.cheap_roll <= 33:
                give(Item.LargeMP)
                random_roll.set(6)
            elif treasure_hunt.cheap_roll <= 37:
                give(Item.SOffDisk)
                random_roll.set(19)
            elif treasure_hunt.cheap_roll <= 41:
                give(Item.SDefDisk)
                random_roll.set(20)
            elif treasure_hunt.cheap_roll <= 45:
                give(Item.SSpeedDisk)
                random_roll.set(21)
            elif treasure_hunt.cheap_roll <= 49:
                give(Item.OmniDisk)
                random_roll.set(18)
            elif treasure_hunt.cheap_roll <= 0:
                give(Item.KogaLaws)
                random_roll.set(90)
            elif treasure_hunt.cheap_roll <= 2:
                give(Item.Flamingwing)
                random_roll.set(73)
            elif treasure_hunt.cheap_roll <= 4:
                give(Item.TornTatter)
                random_roll.set(82)
            elif treasure_hunt.cheap_roll <= 12:
                give(Item.SupRecovery)
                random_roll.set(3)
            elif treasure_hunt.cheap_roll <= 15:
                give(Item.Restore)
                random_roll.set(11)
            elif treasure_hunt.cheap_roll <= 19:
                give(Item.Omnipotent)
                random_roll.set(9)
            elif treasure_hunt.cheap_roll <= 23:
                give(Item.Protection)
                random_roll.set(10)
            elif treasure_hunt.cheap_roll <= 33:
                give(Item.LargeMP)
                random_roll.set(6)
            elif treasure_hunt.cheap_roll <= 37:
                give(Item.SOffDisk)
                random_roll.set(19)
            elif treasure_hunt.cheap_roll <= 41:
                give(Item.SDefDisk)
                random_roll.set(20)
            elif treasure_hunt.cheap_roll <= 45:
                give(Item.SSpeedDisk)
                random_roll.set(21)
            elif treasure_hunt.cheap_roll <= 49:
                give(Item.OmniDisk)
                random_roll.set(18)
            if engine.item_did_not_fit:
                drimogemon.say(t81.u10)
                camera.on(tamer, speed=10)
                camera.arrived()
                return
            narrator.say(t81.u11)
            treasure_hunt.cheap_ordered.clear()
            treasure_hunt.pricey_ordered.clear()
            drimogemon.say(t81.u12)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        drimogemon.run(180, 840)
        drimogemon.say(t81.u8)
        drimogemon.run(169, 2232)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    drimogemon.say(t81.u1)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            while True:
                drimogemon.say(t81.u2)
                match drimogemon.choose(a=t81.m1.o0, b=t81.m1.o1, c=t81.m1.o2):
                    case "a":
                        break
                    case "c" | _:
                        drimogemon.say(t81.u4)
                        camera.on(tamer, speed=10)
                        camera.arrived()
                        return
        case "c" | _:
            drimogemon.say(t81.u4)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
    drimogemon.say(t81.u3)
    match choose(a=t81.m2.o0, b=t81.m2.o1, c=t81.m2.o2):
        case "a":
            if bits < 1000:
                drimogemon.say(t81.u7)
                camera.on(tamer, speed=10)
                camera.arrived()
                return
            take(bits=1000)
            treasure_hunt.cheap_ordered.set()
            drimogemon_job_days.set(0)
            drimogemon.say(t81.u5)
            raw.store_random(treasure_hunt.cheap_roll, 49)
            drimogemon.run(169, 2232)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "b":
            if bits < 5000:
                drimogemon.say(t81.u7)
                camera.on(tamer, speed=10)
                camera.arrived()
                return
            take(bits=5000)
            treasure_hunt.pricey_ordered.set()
            drimogemon_job_days.set(0)
            drimogemon.say(t81.u6)
            raw.store_random(treasure_hunt.pricey_roll, 49)
            drimogemon.run(169, 2232)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "c" | _:
            pass
    drimogemon.say(t81.u4)
    camera.on(tamer, speed=10)
    camera.arrived()

@gabumon.on_talk
def talk():    # section 6
    say(t6.u0)

@hunt.on_step(0)
def step0():    # section 51
    tamer.walk(2200, -3000, wait=False)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=5)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=5)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=5)
            warp(Screen.file_city_168, entry=5)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=5)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=5)
        warp(Screen.file_city_171, entry=5)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=5)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=5)
        warp(Screen.file_city_174, entry=5)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=5)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=5)
    warp(Screen.file_city_177, entry=5)

# the section table, in the order of the original header
sections(254, 81, 6, 51)
