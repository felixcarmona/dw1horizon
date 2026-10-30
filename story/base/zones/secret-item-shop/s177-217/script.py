# The Python view of script 177 of DG.SCN: screen 217 Secret Item Shop.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

shop_ = screen(Screen.secret_item_shop)
keeper = shop_.npc(None, slot=0)    # the .MAP has Numemon135 here; the script spawns what stands here
ninjamon = shop_.npc(Species.Ninjamon175, slot=4)
t5 = text.s177.sec5
t6 = text.s177.sec6

@shop_.on_enter
def enter():    # section 254
    pass

@shop_.on_step(0)
def step0():    # section 51
    warp(Screen.item_shop, entry=1)

@ninjamon.on_talk
def talk():    # section 6
    if pstat(44) == 0:
        say(t6.u0)
        pstat(44).set(1)
        return
    if pstat(44) == 1:
        say(t6.u1)
        pstat(44).set(0)

@keeper.on_talk
def talk():    # section 5
    tamer.face(keeper)
    face(tamer)
    if secret_shop_keeper_met.numemon or secret_shop_keeper_met.mojyamon or secret_shop_keeper_met.mamemon or secret_shop_keeper_met.devimon:
        pass
    elif recruited(Species.Numemon) and not secret_shop_keeper_met.numemon and secret_shop_keeper == 0:
        say(t5.u0)
        secret_shop_keeper_met.numemon.set()
        return
    elif recruited(Species.Mojyamon) and not secret_shop_keeper_met.mojyamon and secret_shop_keeper == 1:
        say(t5.u1)
        secret_shop_keeper_met.mojyamon.set()
        return
    elif recruited(Species.Mamemon) and not secret_shop_keeper_met.mamemon and secret_shop_keeper == 2:
        say(t5.u2)
        secret_shop_keeper_met.mamemon.set()
        return
    elif recruited(Species.Devimon) and not secret_shop_keeper_met.devimon and secret_shop_keeper == 3:
        say(t5.u3)
        secret_shop_keeper_met.devimon.set()
        return
    if recruited(Species.Numemon) and not secret_shop_keeper_met.numemon and secret_shop_keeper == 0:
        say(t5.u4)
        secret_shop_keeper_met.numemon.set()
        return
    if recruited(Species.Mojyamon) and not secret_shop_keeper_met.mojyamon and secret_shop_keeper == 1:
        say(t5.u5)
        secret_shop_keeper_met.mojyamon.set()
        return
    if recruited(Species.Mamemon) and not secret_shop_keeper_met.mamemon and secret_shop_keeper == 2:
        say(t5.u6)
        secret_shop_keeper_met.mamemon.set()
        return
    if recruited(Species.Devimon) and not secret_shop_keeper_met.devimon and secret_shop_keeper == 3:
        say(t5.u7)
        secret_shop_keeper_met.devimon.set()
        return
    if secret_shop_keeper == 0:
        shop(Item.EnemyRepel, Item.EnemyBell)
        return
    if secret_shop_keeper == 1:
        shop(Item.RestPillow, Item.HealthShoe)
        return
    if secret_shop_keeper == 2:
        shop(Item.OmniDisk, Item.SOffDisk, Item.SDefDisk, Item.SSpeedDisk)
        return
    if secret_shop_keeper != 3:
        return
    # ours (economy, docs/mods/balance.md 6.1): the six chips for bits too, at their price (9999), something worth saving for
    shop(Item.DVChipA, Item.DVChipD, Item.DVChipE, Item.OffChip, Item.DefChip, Item.BrainChip, Item.QuickChip, Item.HPChip,
         Item.MPChip)

# the section table, in the order of the original header
sections(254, 51, 6, 5)
