# The Python view of script 82 of DG.SCN: screen 86 Ancient Speedy Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

region = screen(Screen.ancient_speedy_region_86)
meteormon = region.npc(Species.Meteormon, slot=0)
nanimon = region.npc(Species.Nanimon171, slot=1)
t5 = text.s082.sec5
t6 = text.s082.sec6

@region.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.SageFruit, at=(1050, -350))
    if not meteormon_checked:
        wait(250)
        meteormon.play(28)

@meteormon.on_talk(scene=True)
def talk():    # section 5
    tamer.say(t5.u0)
    dws(r"""
        choice(open) {
            text("s082.sec5.m0.o0") => {
                animate(tamer, anim.offer_item);
                wait(1s);
                say(tamer, text("s082.sec5.u1"));
                animate(tamer, 16);
                wait(5);
                say(tamer, text("s082.sec5.u2"));
                say(narrator, text("s082.sec5.u3"));
            }
            text("s082.sec5.m0.o1") => {
                say(tamer, text("s082.sec5.u21"));
                entity_walk_to_entity(partner, 0, meteormon);
                await partner;
                animate(partner, 46);
                wait(1s);
                say(narrator, text("s082.sec5.u22"));
                animate(meteormon, 29);
                wait(1s);
                face(meteormon, tamer);
                face(tamer, meteormon);
                wait(5);
            }
        }
    """)
    play(29)
    wait(500)
    tamer.say(t5.u4)
    tamer.say(t5.u5)
    face(tamer)
    tamer.face(meteormon)
    wait(250)
    narrator.say(t5.u6)
    tamer.say(t5.u7)
    say(t5.u8)
    tamer.say(t5.u9)
    say(t5.u10)
    tamer.say(t5.u11)
    fight(meteormon, escape=False)
    tamer.face(meteormon)
    face(tamer)
    partner.face(meteormon)
    say(t5.u12)
    tamer.say(t5.u13)
    tamer.play(19)
    wait(250)
    say(t5.u14)
    tamer.say(t5.u15)
    tamer.play(anim.idle)
    wait(250)
    say(t5.u16)
    say(t5.u17)
    tamer.say(t5.u18)
    say(t5.u19)
    play(30)
    wait(500)
    while True:
        raw.entity_move_to(meteormon, 1, -1050, 40, 0)
        if glances >= 3:
            break
        glances.add(1)
        wait(1000)
        sound(8, 5)
        tamer.face(meteormon)
        partner.face(meteormon)
    arrived()
    leave()
    glances.set(0)
    tamer.say(t5.u20)
    engine.no_escape.clear()
    meteormon_checked.set()
    camera.on(tamer, speed=15)
    camera.arrived()

@nanimon.on_talk
def talk():    # section 6
    wait(500)
    play(28)
    wait(500)
    tamer.say(t6.u0)
    say(t6.u1)
    turn(1276)
    wait(250)
    turn(2300)
    wait(250)
    turn(3324)
    wait(250)
    turn(252)
    wait(250)
    turn(1276)
    wait(250)
    turn(2300)
    wait(250)
    turn(3324)
    wait(250)
    turn(252)
    wait(250)
    run(182, -571)
    leave()
    if key_chains == 0:
        objects[3].hide()
        tamer.run(150, -138)
        tamer.play(12)
        wait(500)
        objects[3].show()
        sound(0, 7)
        narrator.say(t6.u2)
        sound(0, 7)
        raw.set_inventory_size(20)
        inventory_expanded.to_20.set()
    if key_chains == 4:
        objects[2].hide()
        tamer.run(150, -138)
        tamer.play(12)
        wait(500)
        objects[2].show()
        sound(0, 7)
        narrator.say(t6.u3)
        raw.set_inventory_size(30)
        inventory_expanded.to_30.set()
        recruit(Species.Nanimon)
        engine.prosperity.add(1)
    camera.on(tamer, speed=15)
    camera.arrived()
    key_chains.add(1)
    key_chain_found.speedy_region.set()
    return

# the section table, in the order of the original header
sections(254, 5, 6)
