# The Python view of script 35 of DG.SCN: screen 35 Overdell Cemetery.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

cemetery = screen(Screen.overdell_cemetery)
bakemon = cemetery.npc(Species.Bakemon157, slot=0)
tsukaimon1 = cemetery.npc(Species.Tsukaimon, slot=1)
tsukaimon2 = cemetery.npc(Species.Tsukaimon, slot=2)
tsukaimon3 = cemetery.npc(Species.Tsukaimon, slot=3)
soulmon4 = cemetery.npc(Species.Soulmon, slot=4)
soulmon5 = cemetery.npc(Species.Soulmon, slot=5)
soulmon6 = cemetery.npc(Species.Soulmon, slot=6)
t10 = text.s035.sec10
t11 = text.s035.sec11
t5 = text.s035.sec5
t51 = text.s035.sec51
t6 = text.s035.sec6
t7 = text.s035.sec7
t8 = text.s035.sec8
t9 = text.s035.sec9

@cemetery.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(650, -2850))
    roll = random.roll(99)
    if roll <= 19:
        spawn_item(Item.Digimushrm, at=(-2550, 550))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.SuperVeggy, at=(-1350, 2550))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(2950, 4350))
    if mansion_fridge_memo_found and not myotismon_freed:
        spawn_item(Item.Steak, at=(-150, 1750))

@tsukaimon1.on_talk
def talk():    # section 6
    recruitable(tsukaimon1, line=t6.u0)

@tsukaimon2.on_talk
def talk():    # section 7
    recruitable(tsukaimon2, line=t7.u0)

@tsukaimon3.on_talk
def talk():    # section 8
    recruitable(tsukaimon3, line=t8.u0)

@soulmon4.on_talk
def talk():    # section 9
    recruitable(soulmon4, line=t9.u0)

@soulmon5.on_talk
def talk():    # section 10
    recruitable(soulmon5, line=t10.u0)

@soulmon6.on_talk
def talk():    # section 11
    recruitable(soulmon6, line=t11.u0)

@bakemon.on_talk
def talk():    # section 5
    play(11)
    wait(2500)
    play(anim.idle)
    say(t5.u0)
    tamer.play(16)
    tamer.say(t5.u1)
    engine.no_cancel.set()
    dws(r"""
        choice(open) {
            text("s035.sec5.m0.o0") => {
                animate(bakemon, 11);
                wait(45);
                animate(bakemon, anim.idle);
                say(bakemon, text("s035.sec5.u2"));
                choice(open) {
                    text("s035.sec5.m1.o0") => {
                        animate(bakemon, 12);
                        wait(58);
                        animate(bakemon, anim.idle);
                        animate(tamer, 15);
                        say(bakemon, text("s035.sec5.u3"));
                        animate(tamer, 16);
                        choice(open) {
                            text("s035.sec5.m2.o0") => {}
                            text("s035.sec5.m2.o1") or cancel => {
                                animate(bakemon, 13);
                                wait(34);
                                animate(bakemon, 13);
                                say(bakemon, text("s035.sec5.u4"));
                                loop {
                                    engine.no_cancel = false;
                                    run(bakemon, 1299, -1074);
                                    unless (glances < 10) break;
                                    glances += 1;
                                    wait(5);
                                    face(tamer, bakemon);
                                    face(partner, bakemon);
                                }
                                await bakemon;
                                remove(bakemon);
                                glances = 0;
                                sound(8, 11);
                                say(narrator, text("s035.sec5.u5"));
                                animate(tamer, 16);
                                say(tamer, text("s035.sec5.u6"));
                                recruit(species("Bakemon"));
                                engine.prosperity += 2;
                                return;
                            }
                        }
                    }
                    text("s035.sec5.m1.o1") => {}
                }
            }
            text("s035.sec5.m0.o1") => {}
        }
    """)
    engine.no_cancel.clear()
    play(29)
    sound(8, 0)
    wait(2000)
    arrived()
    leave()
    tamer.say(t5.u7)

@cemetery.on_step(0)
def step0():    # section 51
    if back_dimension_portal == 2:
        tamer.walk(-140, 4669, wait=False)
        warp(Screen.back_dimension_226, entry=0, then=60)
    raw.store_digimon_type(partner_type)
    raw.store_digimon_value(partner_type, partner_attribute)
    if partner_attribute == 3:
        tamer.walk(0, 5000, wait=False)
        partner.walk(0, 5000, wait=False)
        sound(8, 1)
        warp(Screen.grey_lords_mansion_52, entry=0)
        return
    narrator.say(t51.u0)
    hide_hud()
    tamer.run(-200, 3658, camera=True, wait=False)
    partner.run(100, 3658, wait=False)
    tamer.arrived()
    partner.arrived()
    wait(500)
    tamer.turn(3100)
    wait(500)
    tamer.turn(2076)
    tamer.say(t51.u1)
    return

# the section table, in the order of the original header
sections(254, 6, 7, 8, 9, 10, 11, 5, 51)
