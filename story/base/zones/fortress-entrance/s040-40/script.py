# The Python view of script 40 of DG.SCN: screen 40 Fortress Entrance.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.names import *

entrance = screen(Screen.fortress_entrance)
agumon = entrance.npc(Species.Agumon, slot=0)

@entrance.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(2650, -2850))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(-1850, -1850))
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Pricklypear, at=(1650, -1850))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(-2750, -2550))
    swing_door(0)
    wait(1000)

@agumon.on_talk
def talk():    # section 5
    dws(r"""
        unless (fortress_guard_met || canyon_bandits_beaten) goto l1;
        unless (fortress_guard_met || !canyon_bandits_beaten) goto l4;
        unless (!fortress_guard_met || !canyon_bandits_beaten) goto l5;
        goto l6;
        l1:
        fortress_guard_met = true;
        say(agumon, text("s040.sec5.u0"));
        animate(tamer, 24);
        wait(15);
        say(tamer, text("s040.sec5.u1"));
        animate(tamer, anim.idle);
        say(agumon, text("s040.sec5.u2"));
        say(tamer, text("s040.sec5.u3"));
        say(agumon, text("s040.sec5.u4"));
        choice {
            text("s040.sec5.m0.o0") => {
                l2:
                battle(foes: [agumon]);
                say(agumon, text("s040.sec5.u5"));
                run(agumon, -356, -1058);
                wait(2s);
                run(tamer, -349, -1355);
                run(partner, -345, -1751);
                await tamer;
                await partner;
                face(tamer, agumon);
                face(partner, agumon);
                run(agumon, -250, -950);
                await agumon;
                remove(agumon);
                sound(8, 2);
                rotate_3d_object(0, 0, 255);
                wait(2s);
                sound(8, 3);
                wait(10);
                run(tamer, -350, -1145);
                run(partner, -359, -1355);
                say(tamer, text("s040.sec5.u6"));
                say(narrator, text("s040.sec5.u7"));
                say(tamer, text("s040.sec5.u8"));
                say(narrator, text("s040.sec5.u9"));
                say(tamer, text("s040.sec5.u10"));
                camera_on(tamer, speed: 10);
                await camera;
                return;
            }
            text("s040.sec5.m0.o1") => {}
        }
        l3:
        loop {
            say(tamer, text("s040.sec5.u11"));
            return;
            l4:
            say(tamer, text("s040.sec5.u12"));
            say(agumon, text("s040.sec5.u13"));
            animate(tamer, 7);
            wait(15);
            say(tamer, text("s040.sec5.u14"));
            animate(tamer, anim.idle);
            loop {
                say(agumon, text("s040.sec5.u15"));
                run(agumon, -356, -1058);
                wait(2s);
                run(tamer, -349, -1375);
                run(partner, -355, -1761);
                await tamer;
                await partner;
                face(tamer, agumon);
                face(partner, agumon);
                run(agumon, -250, -930);
                await agumon;
                remove(agumon);
                run(tamer, -250, -930);
                await tamer;
                run(partner, -250, -930);
                await partner;
                recruit(species("main character"));
                warp_to(45, 0, 255);
                l5:
                say(tamer, text("s040.sec5.u16"));
                say(agumon, text("s040.sec5.u17"));
                animate(tamer, 7);
                wait(15);
                say(tamer, text("s040.sec5.u18"));
                animate(tamer, anim.idle);
            }
            l6:
            say(tamer, text("s040.sec5.u19"));
            say(agumon, text("s040.sec5.u20"));
            set_dialog_owner(tamer);
            set_selection(l2, l3, text("s040.sec5.m1.o0"), text("s040.sec5.m1.o1"));
            end_selection();
        }
    """)

@entrance.on_step(0)
def step0():    # section 51
    if back_dimension_portal == 3:
        tamer.walk(-250, -250, wait=False)
        warp(Screen.back_dimension_226, entry=0, then=60)
    if recruited(Species.MainCharacter):
        tamer.walk(-250, -250, wait=False)
        warp(Screen.ogre_fortress_45, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 51)
