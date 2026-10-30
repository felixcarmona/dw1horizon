# The Python view of script 134 of DG.SCN: screen 139 Geko Swamp.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

swamp = screen(Screen.geko_swamp_139)
yanmamon0 = swamp.npc(Species.Yanmamon, slot=0)
yanmamon1 = swamp.npc(Species.Yanmamon, slot=1)
gekomon2 = swamp.npc(Species.Gekomon, slot=2)
gekomon3 = swamp.npc(Species.Gekomon, slot=3)
otamamon = swamp.npc(Species.Otamamon, slot=4)
slot5 = swamp.npc(None, slot=5)    # the .MAP has Gekomon here; the script spawns what stands here
slot6 = swamp.npc(None, slot=6)    # the .MAP has Gekomon here; the script spawns what stands here
slot7 = swamp.npc(None, slot=7)    # the .MAP has Gekomon here; the script spawns what stands here
t5 = text.s134.sec5
t6 = text.s134.sec6
t7 = text.s134.sec7
t8 = text.s134.sec8
t9 = text.s134.sec9

@swamp.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 11:
        spawn_item(Item.Digimushrm, at=(950, -50))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-1650, 750))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(-1250, -1150))
    if shogun_gekomon_met:
        objects[24].show()
        objects[25].show()
        objects[26].show()
        objects[27].show()
    else:
        raw.set_rect_impassable(0, 32, 39, 9, 8)
        raw.set_rect_impassable(0, 35, 34, 8, 8)

@yanmamon0.on_talk
def talk():    # section 5
    recruitable(yanmamon0, line=t5.u0)

@yanmamon1.on_talk
def talk():    # section 6
    recruitable(yanmamon1, line=t6.u0)

@gekomon2.on_talk
def talk():    # section 7
    say(t7.u0)
    fight()

@gekomon3.on_talk
def talk():    # section 8
    say(t8.u0)
    fight()

@otamamon.on_talk
def talk():    # section 9
    say(t9.u0)
    say(t9.u1)
    say(t9.u2)
    say(t9.u3)
    say(t9.u4)
    say(t9.u5)
    tamer.say(t9.u6)
    dws(r"""
        choice(open) {
            text("s134.sec9.m0.o0") => {
                battle(foes: [otamamon]);
                face(tamer, otamamon);
                face(otamamon, tamer);
                face(partner, otamamon);
                say(otamamon, text("s134.sec9.u7"));
                animate(tamer, 15);
                wait(1s);
                recruit(species("Otamamon"));
                walk_away(otamamon, -174, -388, looks: 3);
                remove(otamamon);
                glances = 0;
                camera_on(tamer, speed: 10);
                await camera;
                say(tamer, text("s134.sec9.u8"));
                load_digimon(species("Gekomon"));
                set_digimon(species("Gekomon"), 3, 0);
                set_digimon(species("Gekomon"), 5, 0);
                set_digimon(species("Gekomon"), 6, 0);
                set_digimon(species("Gekomon"), 7, 0);
                wait(2s);
                animate(tamer, 24);
                wait(1s);
                say(tamer, text("s134.sec9.u9"));
                entity_walk_to_entity(gekomon3, 1, tamer);
                entity_walk_to_entity(slot5, 1, tamer);
                entity_walk_to_entity(slot6, 1, tamer);
                entity_walk_to_entity(slot7, 1, tamer);
                wait(2s);
                say(gekomon3, text("s134.sec9.u10"));
                animate(tamer, 25);
                wait(1s);
                say(tamer, text("s134.sec9.u11"));
                warp_to(141, 0, 5);
            }
            text("s134.sec9.m0.o1") => {}
        }
    """)
    tamer.play(25)
    wait(1000)
    tamer.say(t9.u12)

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9)
