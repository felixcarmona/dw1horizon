# The Python view of script 220 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(220)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s220.sec51
t83 = text.s220.sec83

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_use(3)
def use3():    # section 83
    if recruited(Species.Agumon):
        return
    sound(0, 0)
    narrator.say(t83.u0)
    if engine.prosperity >= 30:
        narrator.say(t83.u1)
        sound(0, 1)
        return
    if engine.prosperity >= 15:
        narrator.say(t83.u2)
        sound(0, 1)
        return
    narrator.say(t83.u3)
    sound(0, 1)
    return

@lib.on_step(0)
def step0():    # section 51: the prizes of the cups after the original's (23 to 37); script 214 jumps here
    if engine.result == 3:
        if tournament.cup == 23:
            give(bits=3000)
            narrator.say(t51.u0)
            give(Item.QuickChip)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.QuickChip)
            jump_to_script(204, 51)
        elif tournament.cup == 24:
            give(bits=5000)
            narrator.say(t51.u1)
            give(Item.DVChipA)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.DVChipA)
            jump_to_script(204, 51)
        elif tournament.cup == 25:
            give(bits=7000)
            narrator.say(t51.u2)
            give(Item.DVChipD)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.DVChipD)
            jump_to_script(204, 51)
        elif tournament.cup == 26:
            give(bits=10000)
            narrator.say(t51.u3)
            give(Item.DVChipE)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.DVChipE)
            jump_to_script(204, 51)
        elif tournament.cup == 27:
            give(bits=5000)
            narrator.say(t51.u4)
            give(Item.HPChip)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.HPChip)
            jump_to_script(204, 51)
        elif tournament.cup == 28:
            give(bits=5000)
            narrator.say(t51.u5)
            give(Item.BrainChip)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.BrainChip)
            jump_to_script(204, 51)
        elif tournament.cup == 29:
            give(bits=5000)
            narrator.say(t51.u6)
            give(Item.OffChip)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.OffChip)
            jump_to_script(204, 51)
        elif tournament.cup == 30:
            give(bits=5000)
            narrator.say(t51.u7)
            give(Item.SuperVeggy)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.SuperVeggy)
            jump_to_script(204, 51)
        elif tournament.cup == 31:
            give(bits=5000)
            narrator.say(t51.u8)
            give(Item.Digiseabass)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.Digiseabass)
            jump_to_script(204, 51)
        elif tournament.cup == 32:
            give(bits=5000)
            narrator.say(t51.u9)
            give(Item.BlackTrout)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.BlackTrout)
            jump_to_script(204, 51)
        elif tournament.cup == 33:
            give(bits=5000)
            narrator.say(t51.u10)
            give(Item.SpeedLeaf)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.SpeedLeaf)
            jump_to_script(204, 51)
        elif tournament.cup == 34:
            give(bits=5000)
            narrator.say(t51.u11)
            give(Item.DefChip)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.DefChip)
            jump_to_script(204, 51)
        elif tournament.cup == 35:
            give(bits=5000)
            narrator.say(t51.u12)
            give(Item.MPChip)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.MPChip)
            jump_to_script(204, 51)
        elif tournament.cup == 36:
            give(bits=5000)
            narrator.say(t51.u22)
            give(Item.PowerFruit)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.PowerFruit)
            jump_to_script(204, 51)
        elif tournament.cup == 37:
            give(bits=5000)
            narrator.say(t51.u23)
            give(Item.SageFruit)
            if engine.item_did_not_fit:
                slot0.say(t51.u13)
                pick_item()
                take_picked(all=True)
                give(Item.SageFruit)
            jump_to_script(204, 51)
    if tournament.cup == 23:
        give(bits=1000)
        narrator.say(t51.u14)
        give(Item.Sirloin)
        if engine.item_did_not_fit:
            slot0.say(t51.u15)
            pick_item()
            take_picked(all=True)
            give(Item.Sirloin)
        return
    if tournament.cup == 25:
        give(bits=3000)
        narrator.say(t51.u16)
        give(Item.Restore)
        if engine.item_did_not_fit:
            slot0.say(t51.u17)
            pick_item()
            take_picked(all=True)
            give(Item.Restore)
        return
    if tournament.cup == 26:
        give(bits=4000)
        narrator.say(t51.u18)
        give(Item.SupRestore)
        if engine.item_did_not_fit:
            slot0.say(t51.u19)
            pick_item()
            take_picked(all=True)
            give(Item.SupRestore)
        return
    give(bits=2000)
    narrator.say(t51.u20)
    give(Item.SupRecovery)
    if engine.item_did_not_fit:
        slot0.say(t51.u21)
        pick_item()
        take_picked(all=True)
        give(Item.SupRecovery)
    return

# the section table, in the order of the original header
sections(254, 83, 51)
