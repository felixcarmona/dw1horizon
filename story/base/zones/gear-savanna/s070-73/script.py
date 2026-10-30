# The Python view of script 70 of DG.SCN: screen 73 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_73)
biyomon = savanna.npc(Species.Biyomon163, slot=0)
shimaunimon1 = savanna.npc(Species.ShimaUnimon, slot=1)
shimaunimon2 = savanna.npc(Species.ShimaUnimon, slot=2)
akatorimon = savanna.npc(Species.Akatorimon, slot=3)
shamamon4 = savanna.npc(Species.Shamamon, slot=4)
shamamon5 = savanna.npc(Species.Shamamon, slot=5)
tsukaimon = savanna.npc(Species.Tsukaimon, slot=6)
t10 = text.s070.sec10
t11 = text.s070.sec11
t51 = text.s070.sec51
t52 = text.s070.sec52
t53 = text.s070.sec53
t54 = text.s070.sec54
t6 = text.s070.sec6
t7 = text.s070.sec7
t8 = text.s070.sec8
t9 = text.s070.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(-1150, -2250))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(-350, -3150))
    roll = random.roll(99)
    if roll <= 18:
        spawn_item(Item.Digimushrm, at=(1050, -3350))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(1950, -2150))

@biyomon.on_talk
def talk():    # section 5
    dws(r"""
        if (gear_savanna.chase_stage >= 1) {
            say(biyomon, text("s070.sec5.u0"));
            gosub l1;
            sound(8, 6);
            say(biyomon, text("s070.sec5.u1"));
            face(tamer, biyomon);
            face(partner, biyomon);
            await tamer;
            await partner;
            animate(tamer, 16);
            say(tamer, text("s070.sec5.u2"));
            say(tamer, text("s070.sec5.u3"));
            gear_savanna.chase_stage = 2;
            biyomon_ambush_asked.spot0 = true;
            biyomon_ambush_asked.spot1 = true;
            biyomon_ambush_asked.spot2 = true;
            biyomon_ambush_asked.spot3 = true;
            return;
        }
        if (gear_savanna.chase_stage == 0) {
            say(biyomon, text("s070.sec5.u4"));
            say(biyomon, text("s070.sec5.u5"));
            run(biyomon, -240, -1076);
            wait(1s);
            sound(8, 6);
            say(biyomon, text("s070.sec5.u6"));
            face(tamer, biyomon);
            face(partner, biyomon);
            await tamer;
            await partner;
            animate(tamer, anim.command);
            say(tamer, text("s070.sec5.u7"));
            run(biyomon, -240, -1076);
            await biyomon;
            gear_savanna.chase_stage += 1;
            gear_savanna.hide_spot = 1;
            return;
        }
        return;
        l1:
        loop {
            store_random(random_roll, 3);
            if (random_roll == 0 && gear_savanna.hide_spot != 0) {
                run(biyomon, -1055, 2740);
                wait(1s);
                gear_savanna.hide_spot = 0;
                say(tamer, text("s070.sec5.u8"));
                face(tamer, biyomon);
                face(partner, biyomon);
                run(biyomon, -1025, 2740);
                await biyomon;
                jump_return();
            }
            if (random_roll == 1 && gear_savanna.hide_spot != 1) {
                run(biyomon, -566, -350);
                wait(1s);
                gear_savanna.hide_spot = 1;
                say(tamer, text("s070.sec5.u9"));
                face(tamer, biyomon);
                face(partner, biyomon);
                run(biyomon, -566, -320);
                await biyomon;
                jump_return();
            }
            if (random_roll == 2 && gear_savanna.hide_spot != 2) {
                run(biyomon, 1869, -939);
                wait(1s);
                gear_savanna.hide_spot = 2;
                say(tamer, text("s070.sec5.u10"));
                face(tamer, biyomon);
                face(partner, biyomon);
                run(biyomon, 1869, -939);
                await biyomon;
                jump_return();
            }
            if (random_roll == 3 && gear_savanna.hide_spot != 3) {
                run(biyomon, 1664, 3155);
                wait(1s);
                gear_savanna.hide_spot = 3;
                say(tamer, text("s070.sec5.u11"));
                face(tamer, biyomon);
                face(partner, biyomon);
                run(biyomon, 1664, 3125);
                await biyomon;
                jump_return();
            }
        }
    """)

@savanna.on_step(0)
def step0():    # section 51
    if gear_savanna.chase_stage < 2 or gear_savanna.hide_spot == 0 or biyomon_ambush_asked.spot0 or recruited(Species.Biyomon):
        return
    biyomon_ambush_asked.spot0.set()
    tamer.play(16)
    tamer.say(t51.u0)
    match choose(a=t51.m0.o0, b=t51.m0.o1):
        case "a":
            raw.entity_walk_to_entity(partner, 1, tamer)
            partner.arrived()
            partner.face(tamer)
            tamer.face(partner)
            partner.arrived()
            tamer.arrived()
            tamer.play(8)
            tamer.say(t51.u1)
            partner.play(22)
            wait(1000)
            tamer.run(-1282, 3173, wait=False)
            raw.entity_walk_to_entity(partner, 1, biyomon)
            partner.arrived()
            tamer.face(biyomon)
            L12()
            if gear_savanna.hide_spot == 0:
                raw.entity_walk_to_entity(partner, 1, biyomon)
                partner.arrived()
                return L34()
            tamer.play(16)
            tamer.say(t51.u2)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "b":
            return L21()
        case _:
            return

@savanna.on_step(1)
def step1():    # section 52
    if gear_savanna.chase_stage < 2 or gear_savanna.hide_spot == 1 or biyomon_ambush_asked.spot1 or recruited(Species.Biyomon):
        return
    biyomon_ambush_asked.spot1.set()
    tamer.play(16)
    tamer.say(t52.u0)
    match choose(a=t52.m0.o0, b=t52.m0.o1):
        case "a":
            raw.entity_walk_to_entity(partner, 1, tamer)
            partner.arrived()
            partner.face(tamer)
            tamer.face(partner)
            partner.arrived()
            tamer.arrived()
            tamer.play(8)
            tamer.say(t52.u1)
            partner.play(22)
            wait(1000)
            tamer.run(-268, -1362, wait=False)
            raw.entity_walk_to_entity(partner, 1, biyomon)
            partner.arrived()
            tamer.face(biyomon)
            L12()
            if gear_savanna.hide_spot == 1:
                raw.entity_walk_to_entity(partner, 1, biyomon)
                partner.arrived()
                return L34()
            tamer.play(16)
            tamer.say(t52.u2)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "b":
            return L21()
        case _:
            return

@savanna.on_step(2)
def step2():    # section 53
    if gear_savanna.chase_stage < 2 or gear_savanna.hide_spot == 2 or biyomon_ambush_asked.spot2 or recruited(Species.Biyomon):
        return
    biyomon_ambush_asked.spot2.set()
    tamer.play(16)
    tamer.say(t53.u0)
    match choose(a=t53.m0.o0, b=t53.m0.o1):
        case "a":
            raw.entity_walk_to_entity(partner, 1, tamer)
            partner.arrived()
            partner.face(tamer)
            tamer.face(partner)
            partner.arrived()
            tamer.arrived()
            tamer.play(8)
            tamer.say(t53.u1)
            partner.play(22)
            wait(1000)
            tamer.run(2143, -1254, wait=False)
            raw.entity_walk_to_entity(partner, 1, biyomon)
            partner.arrived()
            tamer.face(biyomon)
            L12()
            if gear_savanna.hide_spot == 2:
                raw.entity_walk_to_entity(partner, 1, biyomon)
                partner.arrived()
                return L34()
            tamer.play(16)
            tamer.say(t53.u2)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "b":
            return L21()
        case _:
            return

@savanna.on_step(3)
def step3():    # section 54
    if gear_savanna.chase_stage < 2 or gear_savanna.hide_spot == 3 or biyomon_ambush_asked.spot3 or recruited(Species.Biyomon):
        return
    biyomon_ambush_asked.spot3.set()
    tamer.play(16)
    tamer.say(t54.u0)
    match choose(a=t54.m0.o0, b=t54.m0.o1):
        case "a":
            raw.entity_walk_to_entity(partner, 1, tamer)
            partner.arrived()
            partner.face(tamer)
            tamer.face(partner)
            partner.arrived()
            tamer.arrived()
            raw.set_dialog_owner(tamer)
            tamer.play(8)
            tamer.say(t54.u1)
            partner.play(22)
            wait(1000)
            tamer.run(1753, 3341, wait=False)
            raw.entity_walk_to_entity(partner, 1, biyomon)
            partner.arrived()
            tamer.face(biyomon)
            L12()
            if gear_savanna.hide_spot == 3:
                raw.entity_walk_to_entity(partner, 1, biyomon)
                partner.arrived()
                return L34()
            tamer.play(16)
            tamer.say(t54.u2)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "b":
            return L21()
        case _:
            return

@savanna.on_step(10)
def step10():    # section 61
    biyomon_ambush_asked.spot0.clear()

@savanna.on_step(11)
def step11():    # section 62
    biyomon_ambush_asked.spot1.clear()

@savanna.on_step(12)
def step12():    # section 63
    biyomon_ambush_asked.spot2.clear()

@savanna.on_step(13)
def step13():    # section 64
    biyomon_ambush_asked.spot3.clear()

@shimaunimon1.on_talk
def talk():    # section 6
    recruitable(shimaunimon1, line=t6.u0)

@shimaunimon2.on_talk
def talk():    # section 7
    recruitable(shimaunimon2, line=t7.u0)

@akatorimon.on_talk
def talk():    # section 8
    recruitable(akatorimon, line=t8.u0)

@shamamon4.on_talk
def talk():    # section 9
    recruitable(shamamon4, line=t9.u0)

@shamamon5.on_talk
def talk():    # section 10
    recruitable(shamamon5, line=t10.u0)

@tsukaimon.on_talk
def talk():    # section 11
    recruitable(tsukaimon, line=t11.u0)
    return

def L12():    # shared code (the disc's label L12)
    while True:
        roll = random.roll(3)
        if roll == 0 and gear_savanna.hide_spot != 0:
            biyomon.run(-1025, 2740, wait=False)
            wait(1000)
            gear_savanna.hide_spot.set(0)
            tamer.face(biyomon)
            partner.face(biyomon)
            biyomon.run(-1025, 2740)
            raw.jump_return()
        if roll == 1 and gear_savanna.hide_spot != 1:
            biyomon.run(-566, -320, wait=False)
            wait(1000)
            gear_savanna.hide_spot.set(1)
            tamer.face(biyomon)
            partner.face(biyomon)
            biyomon.run(-566, -320)
            raw.jump_return()
        if roll == 2 and gear_savanna.hide_spot != 2:
            biyomon.run(1869, -939, wait=False)
            wait(1000)
            gear_savanna.hide_spot.set(2)
            tamer.face(biyomon)
            partner.face(biyomon)
            biyomon.run(1869, -939)
            raw.jump_return()
        if roll == 3 and gear_savanna.hide_spot != 3:
            biyomon.run(1664, 3125, wait=False)
            wait(1000)
            gear_savanna.hide_spot.set(3)
            tamer.face(biyomon)
            partner.face(biyomon)
            biyomon.run(1664, 3125)
            raw.jump_return()

def L21():    # shared code (the disc's label L21)
    pass

def L34():    # shared code (the disc's label L34)
    tamer.play(anim.tamer_victory)
    wait(500)
    tamer.face(biyomon)
    partner.face(biyomon)
    biyomon.face(tamer)
    tamer.arrived()
    partner.arrived()
    biyomon.arrived()
    tamer.say(t54.u3)
    sound(8, 6)
    biyomon.say(t54.u4)
    tamer.play(19)
    tamer.say(t54.u5)
    biyomon.play(28)
    wait(1000)
    biyomon.say(t54.u6)
    tamer.play(16)
    tamer.say(t54.u7)
    biyomon.play(19)
    wait(2000)
    tamer.play(19)
    narrator.say(t54.u8)
    biyomon.play(anim.idle)
    biyomon.say(t54.u9)
    biyomon.say(t54.u10)
    while True:
        biyomon.run(-1232, 4250, wait=False)
        if glances < 6 and gear_savanna.hide_spot != 0:
            glances.add(1)
            wait(500)
            tamer.face(biyomon)
            partner.face(biyomon)
            continue
        if glances >= 4 or gear_savanna.hide_spot != 0:
            break
        glances.add(1)
        wait(250)
        tamer.face(biyomon)
        partner.face(biyomon)
    biyomon.arrived()
    biyomon.send_to_city(line=t54.u11, species=Species.Biyomon, sound=(8, 5), camera=False)
    camera.on(tamer, speed=10)
    camera.arrived()

# the section table, in the order of the original header
sections(254, 5, 51, 52, 53, 54, 61, 62, 63, 64, 6, 7, 8, 9, 10, 11)
