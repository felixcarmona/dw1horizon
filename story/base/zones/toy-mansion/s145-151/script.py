# The Python view of script 145 of DG.SCN: screen 151 Toy Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.toy_mansion_151)
slot0 = mansion.npc(None, slot=0)    # the .MAP has WaruMonzaemon here; the script spawns what stands here
nanimon = mansion.npc(Species.Nanimon171, slot=1)
slot2 = mansion.npc(None, slot=2)    # the .MAP has Hagurumon here; the script spawns what stands here
t5 = text.s145.sec5
t6 = text.s145.sec6

@mansion.on_enter
def enter():    # section 254
    spawn_chest(Item.HPChip, at=(-857, 483), opened=trigger(668))
    call(Routine.spawn_toytown_boxes)
    if not recruited(Species.WaruMonzaemon):
        return slot0.talk()

@mansion.on_step(0)
def step0():    # section 51
    tamer.walk(24, -2500, wait=False)
    warp(Screen.toy_mansion_150, entry=2)

@slot0.on_talk
def talk():    # section 5
    if recruited(Species.WaruMonzaemon):
        tamer.play(20)
        tamer.say(t5.u0)
        say(t5.u1)
        return
    wait(3000)
    tamer.say(t5.u2)
    tamer.walk(14, -754, wait=False)
    camera.to(73, 181, speed=20)
    camera.arrived()
    tamer.walk(-205, -608, wait=False)
    partner.walk(195, -608, wait=False)
    wait(2000)
    tamer.turn(2048)
    partner.turn(2048)
    wait(250)
    narrator.say(t5.u3)
    tamer.turn(2560)
    wait(1000)
    tamer.turn(1536)
    wait(1000)
    tamer.turn(2048)
    wait(250)
    tamer.say(t5.u4)
    dws(r"""
        choice(open) {
            text("s145.sec5.m0.o0") => {
                engine.arg = 1;
                call_routine(routine("open_toytown_box"));
                wait(10);
                set_obj_visibility(0, 0);
                set_obj_visibility(1, 0);
                engine.object = 0;
                engine.animation = 2;
                call_routine(routine("reset_object_animation"));
                move_object_to(0, 0, 1, 1, 260, 117);
                move_object_to(1, 1, 1, 1, 255, 130);
                wait(10);
                sound(8, 14);
                move_object_to(0, 0, 1, 8, 260, 27);
                move_object_to(1, 1, 1, 8, 255, 40);
                wait(9);
                move_object_to(0, 0, 1, 13, 165, 27);
                move_object_to(1, 1, 1, 13, 160, 40);
                wait(14);
                sound(8, 14);
                move_object_to(0, 0, 1, 12, 165, 177);
                move_object_to(1, 1, 1, 12, 160, 190);
                wait(13);
                say(tamer, text("s145.sec5.u5"));
                set_obj_visibility(0, 1);
                set_obj_visibility(1, 1);
                set_obj_visibility(13, 0);
                set_obj_visibility(14, 0);
                set_obj_visibility(15, 0);
                set_obj_visibility(16, 0);
                set_obj_visibility(17, 0);
                set_obj_visibility(18, 0);
                set_obj_visibility(19, 0);
                set_obj_visibility(20, 0);
                set_obj_visibility(21, 0);
                set_obj_visibility(22, 0);
                set_obj_visibility(23, 0);
                set_obj_visibility(24, 0);
                set_obj_visibility(25, 0);
                set_obj_visibility(26, 0);
                set_obj_visibility(27, 0);
                set_obj_visibility(28, 0);
                set_obj_visibility(29, 0);
                set_obj_visibility(30, 0);
                set_obj_visibility(31, 0);
                set_obj_visibility(32, 0);
                set_obj_visibility(33, 0);
                set_obj_visibility(34, 0);
                set_obj_visibility(35, 0);
                set_obj_visibility(36, 0);
                set_obj_visibility(37, 0);
                set_obj_visibility(38, 0);
                set_obj_visibility(39, 0);
                set_obj_visibility(40, 0);
                set_obj_visibility(41, 0);
                set_obj_visibility(42, 0);
                set_obj_visibility(43, 0);
                set_obj_visibility(44, 0);
                set_obj_visibility(45, 0);
                set_obj_visibility(46, 0);
                set_obj_visibility(47, 0);
                set_obj_visibility(48, 0);
                set_obj_visibility(49, 0);
                set_obj_visibility(50, 0);
                engine.object = 13;
                engine.animation = 38;
                call_routine(routine("reset_object_animation"));
                sound(8, 15);
                animate(tamer, 15);
                wait(1s);
                set_obj_visibility(13, 1);
                set_obj_visibility(14, 1);
                set_obj_visibility(15, 1);
                set_obj_visibility(16, 1);
                set_obj_visibility(17, 1);
                set_obj_visibility(18, 1);
                set_obj_visibility(19, 1);
                set_obj_visibility(20, 1);
                set_obj_visibility(21, 1);
                set_obj_visibility(22, 1);
                set_obj_visibility(23, 1);
                set_obj_visibility(24, 1);
                set_obj_visibility(25, 1);
                set_obj_visibility(26, 1);
                set_obj_visibility(27, 1);
                set_obj_visibility(28, 1);
                set_obj_visibility(29, 1);
                set_obj_visibility(30, 1);
                set_obj_visibility(31, 1);
                set_obj_visibility(32, 1);
                set_obj_visibility(33, 1);
                set_obj_visibility(34, 1);
                set_obj_visibility(35, 1);
                set_obj_visibility(36, 1);
                set_obj_visibility(37, 1);
                set_obj_visibility(38, 1);
                set_obj_visibility(39, 1);
                set_obj_visibility(40, 1);
                set_obj_visibility(41, 1);
                set_obj_visibility(42, 1);
                set_obj_visibility(43, 1);
                set_obj_visibility(44, 1);
                set_obj_visibility(45, 1);
                set_obj_visibility(46, 1);
                set_obj_visibility(47, 1);
                set_obj_visibility(48, 1);
                set_obj_visibility(49, 1);
                set_obj_visibility(50, 1);
                wait(1s);
                engine.arg = 2;
                call_routine(routine("open_toytown_box"));
                set_digimon(species("WaruMonzaemon"), 0, 0);
                entity_move_to_axis(slot0, -2000, 1, 10);
                wait(1s);
                entity_move_to(slot0, -5, 41, 2, 0);
                wait(10);
                entity_move_to_axis(slot0, 0, 1, 10);
                wait(1s);
                say(slot0, text("s145.sec5.u6"));
                walk(slot0, -5, 41);
                await slot0;
                entity_set_rotation(slot0, 0);
                wait(5);
            }
            text("s145.sec5.m0.o1") => {
                engine.arg = 2;
                call_routine(routine("open_toytown_box"));
                wait(2s);
                set_digimon(species("WaruMonzaemon"), 0, 0);
                entity_move_to_axis(slot0, -2000, 1, 10);
                wait(1s);
                entity_move_to(slot0, -5, 41, 2, 0);
                wait(10);
                entity_move_to_axis(slot0, 0, 1, 10);
                wait(1s);
                say(slot0, text("s145.sec5.u7"));
                walk(slot0, -5, 41);
                await slot0;
                entity_set_rotation(slot0, 0);
                wait(5);
            }
        }
    """)
    tamer.say(t5.u8)
    say(t5.u9)
    tamer.play(20)
    wait(250)
    tamer.say(t5.u10)
    say(t5.u11)
    tamer.play(anim.idle)
    tamer.say(t5.u12)
    say(t5.u13)
    tamer.play(anim.battle_ready)
    tamer.say(t5.u14)
    say(t5.u15)
    fight(slot0, escape=False)
    tamer.face(slot0)
    face(tamer)
    partner.face(slot0)
    tamer.arrived()
    partner.arrived()
    arrived()
    tamer.play(19)
    wait(250)
    tamer.say(t5.u16)
    walk(-5, 41)
    turn(0)
    say(t5.u17)
    tamer.walk(-205, -608, wait=False)
    partner.walk(195, -608, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.face(slot0)
    partner.face(slot0)
    tamer.arrived()
    partner.arrived()
    tamer.play(20)
    wait(250)
    tamer.say(t5.u18)
    say(t5.u19)
    tamer.play(anim.idle)
    sound(8, 6)
    objects[0].hide()
    objects[1].hide()
    objects[0].animate(2)
    raw.move_object_to(0, 0, 1, 0, 205, 147)
    raw.move_object_to(1, 1, 1, 0, 200, 160)
    wait(2000)
    sound(8, 14)
    raw.move_object_to(0, 0, 1, 10, 205, 27)
    raw.move_object_to(1, 1, 1, 10, 200, 40)
    wait(550)
    raw.move_object_to(0, 0, 1, 13, 165, 27)
    raw.move_object_to(1, 1, 1, 13, 160, 40)
    wait(700)
    sound(8, 14)
    raw.move_object_to(0, 0, 1, 12, 165, 177)
    raw.move_object_to(1, 1, 1, 12, 160, 190)
    wait(650)
    tamer.say(t5.u20)
    objects[0].show()
    objects[1].show()
    objects[13].hide()
    objects[14].hide()
    objects[15].hide()
    objects[16].hide()
    objects[17].hide()
    objects[18].hide()
    objects[19].hide()
    objects[20].hide()
    objects[21].hide()
    objects[22].hide()
    objects[23].hide()
    objects[24].hide()
    objects[25].hide()
    objects[26].hide()
    objects[27].hide()
    objects[28].hide()
    objects[29].hide()
    objects[30].hide()
    objects[31].hide()
    objects[32].hide()
    objects[33].hide()
    objects[34].hide()
    objects[35].hide()
    objects[36].hide()
    objects[37].hide()
    objects[38].hide()
    objects[39].hide()
    objects[40].hide()
    objects[41].hide()
    objects[42].hide()
    objects[43].hide()
    objects[44].hide()
    objects[45].hide()
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[49].hide()
    objects[50].hide()
    objects[13].animate(38)
    sound(8, 15)
    tamer.play(15)
    wait(1000)
    objects[13].show()
    objects[14].show()
    objects[15].show()
    objects[16].show()
    objects[17].show()
    objects[18].show()
    objects[19].show()
    objects[20].show()
    objects[21].show()
    objects[22].show()
    objects[23].show()
    objects[24].show()
    objects[25].show()
    objects[26].show()
    objects[27].show()
    objects[28].show()
    objects[29].show()
    objects[30].show()
    objects[31].show()
    objects[32].show()
    objects[33].show()
    objects[34].show()
    objects[35].show()
    objects[36].show()
    objects[37].show()
    objects[38].show()
    objects[39].show()
    objects[40].show()
    objects[41].show()
    objects[42].show()
    objects[43].show()
    objects[44].show()
    objects[45].show()
    objects[46].show()
    objects[47].show()
    objects[48].show()
    objects[49].show()
    objects[50].show()
    tamer.say(t5.u21)
    tamer.play(7)
    wait(1000)
    say(t5.u22)
    sound(8, 6)
    wait(1000)
    spawn(Species.Hagurumon, slot=2)
    wait(500)
    tamer.say(t5.u23)
    say(t5.u24)
    tamer.play(16)
    wait(1000)
    tamer.say(t5.u25)
    say(t5.u26)
    tamer.say(t5.u27)
    tamer.play(12)
    wait(1000)
    slot2.leave()
    tamer.play(20)
    wait(250)
    tamer.say(t5.u28)
    say(t5.u29)
    tamer.play(anim.battle_ready)
    tamer.say(t5.u30)
    give(Item.Gear)
    if engine.item_did_not_fit:
        engine.picker_mode.clear()
        tamer.say(t5.u31)
        call(Routine.choose_item)
        take_picked(all=True)
        give(Item.Gear)
    narrator.say(t5.u32)
    recruit(Species.WaruMonzaemon)

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
    run(20, -1041)
    leave()
    if key_chains == 0:
        objects[54].hide()
        tamer.run(-126, -518)
        tamer.play(12)
        wait(500)
        objects[54].show()
        sound(0, 7)
        narrator.say(t6.u2)
        sound(0, 7)
        raw.set_inventory_size(20)
        inventory_expanded.to_20.set()
    if key_chains == 4:
        objects[53].hide()
        tamer.run(-126, -518)
        tamer.play(12)
        wait(500)
        objects[53].show()
        sound(0, 7)
        narrator.say(t6.u3)
        raw.set_inventory_size(30)
        inventory_expanded.to_30.set()
        recruit(Species.Nanimon)
        engine.prosperity.add(1)
    key_chains.add(1)
    key_chain_found.toy_mansion.set()
    return

# the section table, in the order of the original header
sections(254, 51, 5, 6)
