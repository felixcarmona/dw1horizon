# The Python view of script 130 of DG.SCN: screen 135 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_135)
snowgoblimon = freezeland.npc(Species.SnowGoblimon, slot=0)
whamon = freezeland.npc(Species.Whamon146, slot=1)
icedevimon = freezeland.npc(Species.IceDevimon, slot=2)
t5 = text.s130.sec5
t7 = text.s130.sec7
t81 = text.s130.sec81

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(-1850, 4650))

@snowgoblimon.on_talk
def talk():    # section 5
    recruitable(snowgoblimon, line=t5.u0)

@icedevimon.on_talk
def talk():    # section 7
    recruitable(icedevimon, line=t7.u0)

@whamon.on_talk
def talk():    # section 6
    pass

@freezeland.on_use(1)
def use1():    # section 81
    if recruited(Species.Whamon) or not ogre_fortress_cleared:
        return
    tamer.face(whamon)
    partner.face(whamon)
    wait(250)
    camera.to(-2852, 2621, speed=30)
    camera.arrived()
    if whamon_met:
        whamon.say(t81.u0)
        dws(r"""
            choice(open) {
                text("s130.sec81.m0.o0") => {
                    say(whamon, text("s130.sec81.u10"));
                    camera_to(-3150, 3000, speed: 30);
                    animate(whamon, 28);
                    sound(8, 3);
                    wait(2s);
                    entity_set_rotation(whamon, 3459);
                    sound(8, 3);
                    entity_set_rotation(whamon, 3331);
                    wait(3);
                    entity_set_rotation(whamon, 3203);
                    wait(3);
                    entity_set_rotation(whamon, 3075);
                    wait(3);
                    entity_set_rotation(whamon, 2947);
                    wait(3);
                    entity_set_rotation(whamon, 2819);
                    wait(3);
                    entity_set_rotation(whamon, 2691);
                    wait(3);
                    entity_set_rotation(whamon, 2563);
                    sound(8, 3);
                    wait(10);
                    entity_set_rotation(whamon, 2435);
                    wait(3);
                    entity_set_rotation(whamon, 2307);
                    wait(3);
                    entity_set_rotation(whamon, 2179);
                    wait(3);
                    entity_set_rotation(whamon, 2051);
                    wait(3);
                    entity_set_rotation(whamon, 1923);
                    sound(8, 3);
                    wait(10);
                    entity_set_rotation(whamon, 1795);
                    wait(3);
                    entity_set_rotation(whamon, 1667);
                    wait(3);
                    entity_set_rotation(whamon, 1539);
                    wait(3);
                    entity_set_rotation(whamon, 1411);
                    wait(3);
                    entity_set_rotation(whamon, 1283);
                    wait(3);
                    walk(tamer, -2454, 2707);
                    await tamer;
                    walk(tamer, -3041, 3042);
                    walk(partner, -2454, 2707);
                    await partner;
                    walk(partner, -2771, 2915);
                    await tamer;
                    await partner;
                    wait(1s);
                    entity_set_rotation(tamer, 1283);
                    entity_set_rotation(partner, 1283);
                    wait(5);
                    say(tamer, text("s130.sec81.u11"));
                    sound(8, 3);
                    entity_move_to(tamer, -4053, 3680, 99, 0);
                    entity_move_to(partner, -4053, 3680, 99, 0);
                    entity_move_to(whamon, -4053, 3680, 99, 0);
                    move_object_to(0, 35, 1, 0, 350, 410);
                    move_object_to(1, 36, 1, 0, 438, 410);
                    move_object_to(2, 37, 1, 0, 412, 410);
                    move_object_to(3, 38, 1, 0, 366, 410);
                    move_object_to(4, 39, 1, 0, 350, 434);
                    move_object_to(5, 40, 1, 0, 350, 458);
                    move_object_to(6, 41, 1, 0, 366, 482);
                    move_object_to(7, 42, 1, 0, 390, 506);
                    wait(10);
                    sound(8, 3);
                    set_obj_visibility(35, 0);
                    set_obj_visibility(36, 0);
                    set_obj_visibility(37, 0);
                    set_obj_visibility(38, 0);
                    set_obj_visibility(39, 0);
                    set_obj_visibility(40, 0);
                    set_obj_visibility(41, 0);
                    set_obj_visibility(42, 0);
                    engine.object = 35;
                    engine.animation = 8;
                    call_routine(routine("reset_object_animation"));
                    wait(10);
                    move_object_to(0, 35, 1, 120, 0, 730);
                    move_object_to(1, 36, 1, 120, 88, 730);
                    move_object_to(2, 37, 1, 120, 64, 730);
                    move_object_to(3, 38, 1, 120, 16, 730);
                    move_object_to(4, 39, 1, 120, 0, 754);
                    move_object_to(5, 40, 1, 120, 0, 778);
                    move_object_to(6, 41, 1, 120, 16, 802);
                    move_object_to(7, 42, 1, 120, 40, 826);
                    wait(10);
                    entity_move_to(tamer, -4053, 3680, 99, 0);
                    entity_move_to(partner, -4053, 3680, 99, 0);
                    entity_move_to(whamon, -4053, 3680, 99, 0);
                    wait(30);
                    warp_to(142, 1, 60);
                    return;
                }
                text("s130.sec81.m0.o1") => {
                    say(whamon, text("s130.sec81.u9"));
                    camera_on(tamer, speed: 10);
                    await camera;
                    return;
                }
                cancel => {}
            }
        """)
    whamon_met.set()
    whamon.say(t81.u1)
    tamer.play(25)
    wait(750)
    tamer.say(t81.u2)
    tamer.play(anim.idle)
    whamon.say(t81.u3)
    raw.store_digimon_type(partner_type)
    tamer.say(t81.u4)
    whamon.say(t81.u5)
    whamon.say(t81.u6)
    tamer.play(16)
    wait(750)
    tamer.say(t81.u7)
    tamer.play(anim.idle)
    whamon.say(t81.u8)
    dws(r"""
        choice(open) {
            text("s130.sec81.m1.o0") => {
                say(whamon, text("s130.sec81.u10"));
                camera_to(-3150, 3000, speed: 30);
                animate(whamon, 28);
                sound(8, 3);
                wait(2s);
                entity_set_rotation(whamon, 3459);
                sound(8, 3);
                entity_set_rotation(whamon, 3331);
                wait(3);
                entity_set_rotation(whamon, 3203);
                wait(3);
                entity_set_rotation(whamon, 3075);
                wait(3);
                entity_set_rotation(whamon, 2947);
                wait(3);
                entity_set_rotation(whamon, 2819);
                wait(3);
                entity_set_rotation(whamon, 2691);
                wait(3);
                entity_set_rotation(whamon, 2563);
                sound(8, 3);
                wait(10);
                entity_set_rotation(whamon, 2435);
                wait(3);
                entity_set_rotation(whamon, 2307);
                wait(3);
                entity_set_rotation(whamon, 2179);
                wait(3);
                entity_set_rotation(whamon, 2051);
                wait(3);
                entity_set_rotation(whamon, 1923);
                sound(8, 3);
                wait(10);
                entity_set_rotation(whamon, 1795);
                wait(3);
                entity_set_rotation(whamon, 1667);
                wait(3);
                entity_set_rotation(whamon, 1539);
                wait(3);
                entity_set_rotation(whamon, 1411);
                wait(3);
                entity_set_rotation(whamon, 1283);
                wait(3);
                walk(tamer, -2454, 2707);
                await tamer;
                walk(tamer, -3041, 3042);
                walk(partner, -2454, 2707);
                await partner;
                walk(partner, -2771, 2915);
                await tamer;
                await partner;
                wait(1s);
                entity_set_rotation(tamer, 1283);
                entity_set_rotation(partner, 1283);
                wait(5);
                say(tamer, text("s130.sec81.u11"));
                sound(8, 3);
                entity_move_to(tamer, -4053, 3680, 99, 0);
                entity_move_to(partner, -4053, 3680, 99, 0);
                entity_move_to(whamon, -4053, 3680, 99, 0);
                move_object_to(0, 35, 1, 0, 350, 410);
                move_object_to(1, 36, 1, 0, 438, 410);
                move_object_to(2, 37, 1, 0, 412, 410);
                move_object_to(3, 38, 1, 0, 366, 410);
                move_object_to(4, 39, 1, 0, 350, 434);
                move_object_to(5, 40, 1, 0, 350, 458);
                move_object_to(6, 41, 1, 0, 366, 482);
                move_object_to(7, 42, 1, 0, 390, 506);
                wait(10);
                sound(8, 3);
                set_obj_visibility(35, 0);
                set_obj_visibility(36, 0);
                set_obj_visibility(37, 0);
                set_obj_visibility(38, 0);
                set_obj_visibility(39, 0);
                set_obj_visibility(40, 0);
                set_obj_visibility(41, 0);
                set_obj_visibility(42, 0);
                engine.object = 35;
                engine.animation = 8;
                call_routine(routine("reset_object_animation"));
                wait(10);
                move_object_to(0, 35, 1, 120, 0, 730);
                move_object_to(1, 36, 1, 120, 88, 730);
                move_object_to(2, 37, 1, 120, 64, 730);
                move_object_to(3, 38, 1, 120, 16, 730);
                move_object_to(4, 39, 1, 120, 0, 754);
                move_object_to(5, 40, 1, 120, 0, 778);
                move_object_to(6, 41, 1, 120, 16, 802);
                move_object_to(7, 42, 1, 120, 40, 826);
                wait(10);
                entity_move_to(tamer, -4053, 3680, 99, 0);
                entity_move_to(partner, -4053, 3680, 99, 0);
                entity_move_to(whamon, -4053, 3680, 99, 0);
                wait(30);
                warp_to(142, 1, 60);
            }
            text("s130.sec81.m1.o1") or cancel => {
                say(whamon, text("s130.sec81.u9"));
                camera_on(tamer, speed: 10);
                await camera;
            }
        }
    """)

@freezeland.on_step(0)
def step0():    # section 51
    if not partner.sick or digivolve_scene_seen:
        return
    if partner.species in (Species.Agumon, Species.Greymon, Species.Tyrannomon, Species.Meramon, Species.Monochromon):
        jump_to_script(203, 51)
    if partner_type in (19, 32, 51, 1, 2):
        jump_to_script(203, 51)
    if partner_type in (15, 16, 29, 30, 43):
        jump_to_script(203, 51)
    if partner_type in (44, 21):
        jump_to_script(203, 51)
    return

# the section table, in the order of the original header
sections(254, 5, 7, 6, 81, 51)
