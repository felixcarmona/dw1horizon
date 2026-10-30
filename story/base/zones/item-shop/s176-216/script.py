# The Python view of script 176 of DG.SCN: screen 216 Item Shop.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

shop_ = screen(Screen.item_shop)
keeper = shop_.npc(None, slot=0)    # the .MAP has Patamon151 here; the script spawns what stands here
piximon = shop_.npc(Species.Piximon173, slot=4)
punimon = shop_.npc(Species.Punimon, slot=5)
t7 = text.s176.sec7
t81 = text.s176.sec81
t82 = text.s176.sec82

@shop_.on_enter
def enter():    # section 254
    if recruited(Species.Devimon) or recruited(Species.Numemon) or recruited(Species.Mamemon) or recruited(Species.Mojyamon):
        objects[21].show()
    else:
        raw.set_rect_impassable(0, 35, 45, 2, 16)
    if item_shop_keeper == 3:
        keeper.play(28)
    if item_shop_intros < 3:
        objects[18].hide()
        objects[20].hide()
    else:
        objects[18].show()
        objects[20].show()

@shop_.on_step(0)
def step0():    # section 51
    tamer.walk(250, -5000, wait=False)
    piximon_in_item_shop.clear()
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=3)
                    return
                warp(Screen.file_city_191, entry=3)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=3)
                return
            warp(Screen.file_city_190, entry=3)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=3)
                return
            warp(Screen.file_city_194, entry=3)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=3)
            return
        warp(Screen.file_city_189, entry=3)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=3)
                    return
                warp(Screen.file_city_183, entry=3)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=3)
                return
            warp(Screen.file_city_182, entry=3)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=3)
                return
            warp(Screen.file_city_186, entry=3)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=3)
            return
        warp(Screen.file_city_181, entry=3)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=3)
                return
            warp(Screen.file_city_198, entry=3)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=3)
            return
        warp(Screen.file_city_197, entry=3)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=3)
            return
        warp(Screen.file_city_201, entry=3)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=3)
        return
    warp(Screen.file_city_180, entry=3)
    return

@shop_.on_use(1)
def use1():    # section 81
    tamer.face(keeper)
    if item_shop_keeper != 3:
        keeper.face(tamer)
    if item_shop_keeper_met.patamon or item_shop_keeper_met.biyomon or item_shop_keeper_met.unimon or item_shop_keeper_met.monochromon:
        pass
    elif recruited(Species.Patamon) and not item_shop_keeper_met.patamon and item_shop_keeper == 0:
        keeper.say(t81.u0)
        item_shop_keeper_met.patamon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    elif recruited(Species.Biyomon) and not item_shop_keeper_met.biyomon and item_shop_keeper == 1:
        keeper.say(t81.u1)
        item_shop_keeper_met.biyomon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    elif recruited(Species.Unimon) and not item_shop_keeper_met.unimon and item_shop_keeper == 2:
        keeper.say(t81.u2)
        item_shop_keeper_met.unimon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    elif recruited(Species.Monochromon) and not item_shop_keeper_met.monochromon and item_shop_keeper == 3:
        keeper.say(t81.u3)
        item_shop_keeper_met.monochromon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    if recruited(Species.Patamon) and not item_shop_keeper_met.patamon and item_shop_keeper == 0:
        keeper.say(t81.u4)
        item_shop_keeper_met.patamon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    if recruited(Species.Biyomon) and not item_shop_keeper_met.biyomon and item_shop_keeper == 1:
        keeper.say(t81.u5)
        item_shop_keeper_met.biyomon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    if recruited(Species.Unimon) and not item_shop_keeper_met.unimon and item_shop_keeper == 2:
        keeper.say(t81.u6)
        item_shop_keeper_met.unimon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    if recruited(Species.Monochromon) and not item_shop_keeper_met.monochromon and item_shop_keeper == 3:
        keeper.say(t81.u7)
        item_shop_keeper_met.monochromon.set()
        item_shop_intros.add(1)
        if item_shop_intros >= 3:
            objects[18].show()
            objects[20].show()
        return
    if item_shop_intros == 1:
        shop_stock.sm_recovery.set()
        shop_stock.med_recovery.set()
        shop_stock.mp_floppy.set()
        shop_stock.various.set()
        shop_stock.off_disk.set()
        shop_stock.def_disk.set()
        shop_stock.hispeed_dsk.set()
        shop_stock.auto_pilot.set()
        shop_stock.port_potty.set()
        shop_stock.meat.set()
    if item_shop_keeper == 0:
        shop_stock.omnipotent.set()
    if item_shop_keeper == 1:
        shop_stock.sup_recovery.set()
    if item_shop_keeper == 2:
        shop_stock.sup_restore.set()
    if item_shop_keeper == 3:
        shop_stock.protection.set()
    engine.picker_mode.clear()
    if item_shop_intros in (2, 3):
        shop_stock.sm_recovery.set()
        shop_stock.med_recovery.set()
        shop_stock.mp_floppy.set()
        shop_stock.various.set()
        shop_stock.off_disk.set()
        shop_stock.def_disk.set()
        shop_stock.hispeed_dsk.set()
        shop_stock.auto_pilot.set()
        shop_stock.port_potty.set()
        shop_stock.meat.set()
        shop_stock.lrg_recovery.set()
        shop_stock.medium_mp.set()
    if item_shop_keeper == 0:
        shop_stock.omnipotent.set()
    if item_shop_keeper == 1:
        shop_stock.sup_recovery.set()
    if item_shop_keeper == 2:
        shop_stock.sup_restore.set()
    if item_shop_keeper == 3:
        shop_stock.protection.set()
    if item_shop_intros == 4:
        shop_stock.sm_recovery.set()
        shop_stock.med_recovery.set()
        shop_stock.mp_floppy.set()
        shop_stock.various.set()
        shop_stock.off_disk.set()
        shop_stock.def_disk.set()
        shop_stock.hispeed_dsk.set()
        shop_stock.auto_pilot.set()
        shop_stock.port_potty.set()
        shop_stock.meat.set()
        shop_stock.lrg_recovery.set()
        shop_stock.medium_mp.set()
        shop_stock.double_flop.set()
        shop_stock.large_mp.set()
        shop_stock.restore.set()
    if item_shop_keeper == 0:
        shop_stock.omnipotent.set()
    if item_shop_keeper == 1:
        shop_stock.sup_recovery.set()
    if item_shop_keeper == 2:
        shop_stock.sup_restore.set()
    if item_shop_keeper == 3:
        shop_stock.protection.set()
    if item_shop_intros == 5:
        shop_stock.sm_recovery.set()
        shop_stock.med_recovery.set()
        shop_stock.mp_floppy.set()
        shop_stock.various.set()
        shop_stock.off_disk.set()
        shop_stock.def_disk.set()
        shop_stock.hispeed_dsk.set()
        shop_stock.auto_pilot.set()
        shop_stock.port_potty.set()
        shop_stock.meat.set()
        shop_stock.lrg_recovery.set()
        shop_stock.medium_mp.set()
        shop_stock.double_flop.set()
        shop_stock.large_mp.set()
        shop_stock.restore.set()
        shop_stock.omnipotent.set()
        shop_stock.sup_recovery.set()
        shop_stock.protection.set()
        shop_stock.sup_restore.set()
    engine.picker_mode.clear()
    call(Routine.shop, arg=5)
    shop_stock.sm_recovery.clear()
    shop_stock.med_recovery.clear()
    shop_stock.mp_floppy.clear()
    shop_stock.various.clear()
    shop_stock.off_disk.clear()
    shop_stock.def_disk.clear()
    shop_stock.hispeed_dsk.clear()
    shop_stock.auto_pilot.clear()
    shop_stock.port_potty.clear()
    shop_stock.meat.clear()
    shop_stock.lrg_recovery.clear()
    shop_stock.medium_mp.clear()
    shop_stock.double_flop.clear()
    shop_stock.large_mp.clear()
    shop_stock.restore.clear()
    shop_stock.omnipotent.clear()
    shop_stock.sup_recovery.clear()
    shop_stock.protection.clear()
    shop_stock.sup_restore.clear()

@shop_.on_use(2)
def use2():    # section 82
    if not piximon_in_item_shop:
        return
    tamer.face(piximon)
    piximon.face(tamer)
    piximon.say(t82.u0)
    dws(r"""
        choice(open) {
            text("s176.sec82.m0.o0") => {
                if (bits >= 50000) {
                    take_bits(50000);
                    give_item(item("Trn. manual"), 1);
                    if (engine.item_did_not_fit) {
                        say(piximon, text("s176.sec82.u2"));
                        give_bits(50000);
                        return;
                    }
                    sound(0, 5);
                    say(narrator, text("s176.sec82.u3"));
                } else {
                    say(piximon, text("s176.sec82.u1"));
                    return;
                }
            }
            text("s176.sec82.m0.o1") => {}
        }
    """)
    piximon.say(t82.u4)

@shop_.on_use(3)
def use3():    # section 83
    if item_shop_intros < 3:
        return
    tamer.turn(2048)
    jump_to_script(219, 51)

@punimon.on_talk
def talk():    # section 7
    roll = random.roll(2)
    if engine.prosperity >= 20:
        if roll == 0:
            say(t7.u0)
            return
    say(t7.u1)

@shop_.on_step(1)
def step1():    # section 52
    warp(Screen.secret_item_shop, entry=0)
    return

# the section table, in the order of the original header
sections(254, 51, 81, 82, 83, 7, 52)
