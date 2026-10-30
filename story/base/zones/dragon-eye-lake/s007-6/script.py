# The Python view of script 7 of DG.SCN: screen 6 Dragon Eye Lake.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lake = screen(Screen.dragon_eye_lake_6)
slot0 = lake.npc(None, slot=0)    # the .MAP has Seadramon134 here; the script spawns what stands here
t81 = text.s007.sec81

@lake.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(750, -3350))

@lake.on_use(1)
def use1():    # section 81
    if not has(Item.BlueFlute):
        return
    tamer.say(t81.u0)
    narrator.say(t81.u1)
    match choose(a=t81.m0.o0, b=t81.m0.o1):
        case "a":
            sound(8, 13)
            wait(3000)
            camera.on(tamer, speed=10)
            camera.arrived()
            tamer.run(445, -1448, camera=True, wait=False)
            partner.run(743, -2280, wait=False)
            tamer.arrived()
            partner.arrived()
            tamer.turn(1536)
            partner.turn(1536)
            camera.to(242, -1810, speed=10)
            camera.arrived()
            load(Species.Seadramon134)
            spawn(Species.Seadramon134, slot=0)
            slot0.play(28)
            objects[38].hide()
            objects[39].hide()
            objects[40].hide()
            objects[41].hide()
            objects[42].hide()
            objects[43].hide()
            objects[44].hide()
            objects[40].animate(5)
            tamer.play(15)
            slot0.arrived()
            sound(8, 12)
            wait(3000)
            objects[40].show()
            objects[41].show()
            objects[42].show()
            objects[43].show()
            objects[44].show()
            objects[45].hide()
            slot0.play(32)
            sound(8, 7)
            slot0.say(t81.u2)
            tamer.play(19)
            wait(750)
            tamer.say(t81.u3)
            tamer.play(anim.idle)
            slot0.say(t81.u4)
            slot0.play(29)
            objects[45].show()
            objects[46].hide()
            objects[47].hide()
            objects[46].animate(2)
            wait(1000)
            objects[46].show()
            objects[47].show()
            slot0.play(30)
            wait(500)
            camera.to(-310, -1980, speed=15)
            camera.arrived()
            raw.entity_move_to_axis(tamer, -200, 1, 2)
            wait(250)
            tamer.play(21)
            raw.entity_move_to(tamer, -194, -1810, 50, 0)
            partner.run(50, -2538)
            raw.entity_move_to(slot0, -791, 74, 30, 0)
            raw.entity_move_to(tamer, -791, 74, 30, 0)
            raw.entity_move_to(partner, -791, 74, 30, 0)
            wait(1000)
            warp(Screen.beetle_land_105, entry=0)
            return
        case "b":
            return
        case _:
            return

@lake.on_use(2)
def use2():    # section 82
    dws(r"""
        run(tamer, 445, -1448, camera: true);
        run(partner, 743, -2280);
        await tamer;
        await partner;
        entity_set_rotation(tamer, 1536);
        entity_set_rotation(partner, 1536);
        camera_to(242, -1810, speed: 10);
        await camera;
        if (seadramon_met) {
            seadramon_met = true;
            set_obj_visibility(38, 0);
            set_obj_visibility(39, 0);
            load_digimon(species(134));
            set_digimon(species(134), 0, 0);
            animate(slot0, 28);
            set_obj_visibility(40, 0);
            set_obj_visibility(41, 0);
            set_obj_visibility(42, 0);
            set_obj_visibility(43, 0);
            set_obj_visibility(44, 0);
            engine.object = 40;
            engine.animation = 5;
            call_routine(routine("reset_object_animation"));
            animate(tamer, 15);
            await slot0;
            sound(8, 12);
            wait(3s);
            set_obj_visibility(40, 1);
            set_obj_visibility(41, 1);
            set_obj_visibility(42, 1);
            set_obj_visibility(43, 1);
            set_obj_visibility(44, 1);
            set_obj_visibility(45, 0);
            animate(slot0, 32);
            sound(8, 7);
            say(tamer, text("s007.sec82.u0"));
            say(slot0, text("s007.sec82.u1"));
        } else {
            goto l2;
        }
        loop {
            engine.no_cancel = true;
            set_dialog_owner(tamer);
            set_selection(l1, l4, l5, text("s007.sec82.m0.o0"), text("s007.sec82.m0.o1"), text("s007.sec82.m0.o2"));
            l1:
            engine.no_cancel = false;
            if (is_recruited(species("Seadramon"))) {
                say(slot0, text("s007.sec82.u2"));
                continue;
            }
            goto l3;
            l2:
            seadramon_met = true;
            load_digimon(species(134));
            set_digimon(species(134), 0, 0);
            animate(slot0, 28);
            set_obj_visibility(38, 0);
            set_obj_visibility(39, 0);
            set_obj_visibility(40, 0);
            set_obj_visibility(41, 0);
            set_obj_visibility(42, 0);
            set_obj_visibility(43, 0);
            set_obj_visibility(44, 0);
            engine.object = 40;
            engine.animation = 5;
            call_routine(routine("reset_object_animation"));
            animate(tamer, 15);
            await slot0;
            sound(8, 12);
            wait(3s);
            set_obj_visibility(40, 1);
            set_obj_visibility(41, 1);
            set_obj_visibility(42, 1);
            set_obj_visibility(43, 1);
            set_obj_visibility(44, 1);
            set_obj_visibility(45, 0);
            animate(slot0, 32);
            sound(8, 7);
            say(tamer, text("s007.sec82.u3"));
            animate(tamer, anim.idle);
            say(slot0, text("s007.sec82.u4"));
            say(tamer, text("s007.sec82.u5"));
            engine.no_cancel = true;
            set_selection(l3, l4, l5, text("s007.sec82.m1.o0"), text("s007.sec82.m1.o1"), text("s007.sec82.m1.o2"));
            l3:
            engine.no_cancel = false;
            say(slot0, text("s007.sec82.u6"));
            recruit(species("Seadramon"));
            engine.prosperity += 2;
            give_item(item("Blue Flute"), 1);
            if (engine.item_did_not_fit) {
                engine.picker_mode = false;
                say(tamer, text("s007.sec82.u7"));
                call_routine(routine("choose_item"));
                call_routine(routine("remove_all_chosen_item"));
                give_item(item("Blue Flute"), 1);
            }
            say(narrator, text("s007.sec82.u8"));
            say(slot0, text("s007.sec82.u9"));
            say(tamer, text("s007.sec82.u10"));
            say(slot0, text("s007.sec82.u11"));
            engine.no_cancel = true;
            set_dialog_owner(tamer);
            set_selection(l6, l7, text("s007.sec82.m2.o0"), text("s007.sec82.m2.o1"));
            l4:
            engine.no_cancel = false;
            say(slot0, text("s007.sec82.u12"));
            if (!knows(tech("Aqua Magic"))) {
                learn_move(tech("Aqua Magic"));
                say(narrator, text("s007.sec82.u13"));
                break;
            }
            if (!knows(tech("Winter Blast"))) {
                learn_move(tech("Winter Blast"));
                say(narrator, text("s007.sec82.u14"));
                break;
            }
            if (!knows(tech("Giga Freeze"))) {
                learn_move(tech("Giga Freeze"));
                say(narrator, text("s007.sec82.u15"));
                break;
            }
            say(slot0, text("s007.sec82.u16"));
        }
        say(slot0, text("s007.sec82.u17"));
        animate(slot0, 29);
        set_obj_visibility(45, 1);
        set_obj_visibility(46, 0);
        set_obj_visibility(47, 0);
        wait(1s);
        animate(slot0, 30);
        set_obj_visibility(46, 1);
        set_obj_visibility(47, 1);
        wait(5);
        entity_move_to(slot0, -791, 74, 30, 0);
        await slot0;
        remove(slot0);
        return;
        l5:
        engine.no_cancel = false;
        say(slot0, text("s007.sec82.u18"));
        give_item(item("Waterbottle"), 1);
        if (engine.item_did_not_fit) {
            engine.picker_mode = false;
            say(tamer, text("s007.sec82.u19"));
            call_routine(routine("choose_item"));
            call_routine(routine("remove_all_chosen_item"));
            give_item(item("Waterbottle"), 1);
        }
        say(narrator, text("s007.sec82.u20"));
        say(slot0, text("s007.sec82.u21"));
        animate(slot0, 29);
        set_obj_visibility(45, 1);
        set_obj_visibility(46, 0);
        set_obj_visibility(47, 0);
        wait(1s);
        animate(slot0, 30);
        set_obj_visibility(46, 1);
        set_obj_visibility(47, 1);
        wait(5);
        entity_move_to(slot0, -791, 74, 30, 0);
        await slot0;
        remove(slot0);
        return;
        l6:
        engine.no_cancel = false;
        say(slot0, text("s007.sec82.u22"));
        animate(slot0, 29);
        set_obj_visibility(45, 1);
        set_obj_visibility(46, 0);
        set_obj_visibility(47, 0);
        engine.object = 46;
        engine.animation = 2;
        call_routine(routine("reset_object_animation"));
        wait(1s);
        set_obj_visibility(46, 1);
        set_obj_visibility(47, 1);
        animate(slot0, 30);
        wait(10);
        camera_to(-310, -1980, speed: 15);
        await camera;
        entity_move_to_axis(tamer, -200, 1, 2);
        wait(5);
        animate(tamer, 21);
        entity_move_to(tamer, -194, -1810, 50, 0);
        run(partner, 50, -2538);
        await partner;
        entity_move_to(slot0, -791, 74, 30, 0);
        entity_move_to(tamer, -791, 74, 30, 0);
        entity_move_to(partner, -791, 74, 30, 0);
        wait(1s);
        warp_to(105, 0, 255);
        return;
        l7:
        engine.no_cancel = false;
        say(slot0, text("s007.sec82.u23"));
        animate(slot0, 29);
        set_obj_visibility(45, 1);
        set_obj_visibility(46, 0);
        set_obj_visibility(47, 0);
        wait(1s);
        animate(slot0, 30);
        set_obj_visibility(46, 1);
        set_obj_visibility(47, 1);
        wait(5);
        entity_move_to(slot0, -791, 74, 30, 0);
        await slot0;
        remove(slot0);
        return;
    """)

# the section table, in the order of the original header
sections(254, 81, 82)
