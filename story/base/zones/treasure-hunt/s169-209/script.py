# The Python view of script 169 of DG.SCN: screen 209 Treasure Hunt.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered to DWS); mods import `dw.base`.
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
    if drimogemon_job_days < 1 and treasure_hunt.cheap_ordered:
        raw.entity_move_to(drimogemon, 169, 2232, 5, 0)
        drimogemon.arrived()
    if drimogemon_job_days < 3 and treasure_hunt.pricey_ordered:
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
    dws(r"""
        if (treasure_hunt.cheap_ordered || treasure_hunt.pricey_ordered) {
            if (drimogemon_job_days >= 1 && treasure_hunt.cheap_ordered) goto l61;
            if (drimogemon_job_days >= 3 && treasure_hunt.pricey_ordered) goto l61;
            run(drimogemon, 180, 840);
            await drimogemon;
            say(drimogemon, text("s169.sec81.u8"));
            run(drimogemon, 169, 2232);
            await drimogemon;
            camera_on(tamer, speed: 10);
            await camera;
            return;
            l61:
            say(drimogemon, text("s169.sec81.u9"));
            l60:
            if (treasure_hunt.pricey_ordered) {
                if (is_recruited(species("Gabumon"))) {
                    if (treasure_hunt.pricey_roll <= 9) {
                        give_item(item("Restore"), 1);
                        random_roll = 11;
                    } else if (treasure_hunt.pricey_roll <= 19) {
                        give_item(item("Flamingwing"), 1);
                        random_roll = 73;
                    } else if (treasure_hunt.pricey_roll <= 29) {
                        give_item(item("Torn tatter"), 1);
                        random_roll = 82;
                    } else if (treasure_hunt.pricey_roll <= 39) {
                        give_item(item("Koga laws"), 1);
                        random_roll = 90;
                    } else if (treasure_hunt.pricey_roll <= 49) {
                        give_item(item("HP Chip"), 1);
                        random_roll = 27;
                    } else if (treasure_hunt.pricey_roll <= 59) {
                        give_item(item("MP Chip"), 1);
                        random_roll = 28;
                    } else if (treasure_hunt.pricey_roll <= 69) {
                        give_item(item("Off. Chip"), 1);
                        random_roll = 23;
                    } else if (treasure_hunt.pricey_roll <= 79) {
                        give_item(item("Def. Chip"), 1);
                        random_roll = 24;
                    } else if (treasure_hunt.pricey_roll <= 89) {
                        give_item(item("Quick Chip"), 1);
                        random_roll = 26;
                    } else if (treasure_hunt.pricey_roll <= 99) {
                        give_item(item("Brain Chip"), 1);
                        random_roll = 25;
                    }
                } else {
                    if (treasure_hunt.pricey_roll <= 9) {
                        give_item(item("Restore"), 1);
                        random_roll = 11;
                    } else if (treasure_hunt.pricey_roll <= 29) {
                        give_item(item("Flamingwing"), 1);
                        random_roll = 73;
                    } else if (treasure_hunt.pricey_roll <= 49) {
                        give_item(item("Torn tatter"), 1);
                        random_roll = 82;
                    } else if (treasure_hunt.pricey_roll <= 69) {
                        give_item(item("Koga laws"), 1);
                        random_roll = 90;
                    } else if (treasure_hunt.pricey_roll <= 74) {
                        give_item(item("HP Chip"), 1);
                        random_roll = 27;
                    } else if (treasure_hunt.pricey_roll <= 79) {
                        give_item(item("MP Chip"), 1);
                        random_roll = 28;
                    } else if (treasure_hunt.pricey_roll <= 84) {
                        give_item(item("Off. Chip"), 1);
                        random_roll = 23;
                    } else if (treasure_hunt.pricey_roll <= 89) {
                        give_item(item("Def. Chip"), 1);
                        random_roll = 24;
                    } else if (treasure_hunt.pricey_roll <= 94) {
                        give_item(item("Quick Chip"), 1);
                        random_roll = 26;
                    } else if (treasure_hunt.pricey_roll <= 99) {
                        give_item(item("Brain Chip"), 1);
                        random_roll = 25;
                    }
                }
            } else if (is_recruited(species("Gabumon"))) {
                if (treasure_hunt.cheap_roll <= 14) {
                    give_item(item("Omnipotent"), 1);
                    random_roll = 9;
                } else if (treasure_hunt.cheap_roll <= 29) {
                    give_item(item("Omni Disk"), 1);
                    random_roll = 18;
                } else if (treasure_hunt.cheap_roll <= 44) {
                    give_item(item("Protection"), 1);
                    random_roll = 10;
                } else if (treasure_hunt.cheap_roll <= 54) {
                    give_item(item("S.Off.disk"), 1);
                    random_roll = 19;
                } else if (treasure_hunt.cheap_roll <= 64) {
                    give_item(item("S.Def.disk"), 1);
                    random_roll = 20;
                } else if (treasure_hunt.cheap_roll <= 74) {
                    give_item(item("S.speed.disk"), 1);
                    random_roll = 21;
                } else if (treasure_hunt.cheap_roll <= 84) {
                    give_item(item("Restore"), 1);
                    random_roll = 11;
                } else if (treasure_hunt.cheap_roll <= 89) {
                    give_item(item("Flamingwing"), 1);
                    random_roll = 73;
                } else if (treasure_hunt.cheap_roll <= 94) {
                    give_item(item("Torn tatter"), 1);
                    random_roll = 82;
                } else if (treasure_hunt.cheap_roll <= 99) {
                    give_item(item("Koga laws"), 1);
                    random_roll = 90;
                }
            } else {
                if (treasure_hunt.cheap_roll <= 19) {
                    give_item(item("Omnipotent"), 1);
                    random_roll = 9;
                } else if (treasure_hunt.cheap_roll <= 39) {
                    give_item(item("Protection"), 1);
                    random_roll = 10;
                } else if (treasure_hunt.cheap_roll <= 49) {
                    give_item(item("Omni Disk"), 1);
                    random_roll = 18;
                } else if (treasure_hunt.cheap_roll <= 59) {
                    give_item(item("S.Off.disk"), 1);
                    random_roll = 19;
                } else if (treasure_hunt.cheap_roll <= 69) {
                    give_item(item("S.Def.disk"), 1);
                    random_roll = 20;
                } else if (treasure_hunt.cheap_roll <= 79) {
                    give_item(item("S.speed.disk"), 1);
                    random_roll = 21;
                } else if (treasure_hunt.cheap_roll <= 84) {
                    give_item(item("Restore"), 1);
                    random_roll = 11;
                } else if (treasure_hunt.cheap_roll <= 89) {
                    give_item(item("Flamingwing"), 1);
                    random_roll = 73;
                } else if (treasure_hunt.cheap_roll <= 94) {
                    give_item(item("Torn tatter"), 1);
                    random_roll = 82;
                } else if (treasure_hunt.cheap_roll <= 99) {
                    give_item(item("Koga laws"), 1);
                    random_roll = 90;
                }
            }
            if (engine.item_did_not_fit) {
                say(drimogemon, text("s169.sec81.u10"));
                camera_on(tamer, speed: 10);
                await camera;
                return;
            }
            say(narrator, text("s169.sec81.u11"));
            store_random(random_roll, 99);
            if (random_roll <= 4 && is_recruited(species("Gabumon"))) {
                store_random(treasure_hunt.cheap_roll, 99);
                store_random(treasure_hunt.pricey_roll, 99);
                goto l60;
            }
            treasure_hunt.cheap_ordered = false;
            treasure_hunt.pricey_ordered = false;
            say(drimogemon, text("s169.sec81.u12"));
            camera_on(tamer, speed: 10);
            await camera;
            return;
        }
    """)
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
            if bits < 2000:
                drimogemon.say(t81.u7)
                camera.on(tamer, speed=10)
                camera.arrived()
                return
            take(bits=2000)
            treasure_hunt.cheap_ordered.set()
            drimogemon_job_days.set(0)
            drimogemon.say(t81.u5)
            raw.store_random(treasure_hunt.cheap_roll, 99)
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
            raw.store_random(treasure_hunt.pricey_roll, 99)
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
