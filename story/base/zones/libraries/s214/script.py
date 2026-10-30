# The Python view of script 214 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(214)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s214.sec51

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    tournament_registered.clear()
    if engine.result == 3:
        if tournament.cup == 0:
            give(bits=2000)
            narrator.say(t51.u3)
            give(Item.DoubleFlop)
            if engine.item_did_not_fit:
                slot0.say(t51.u4)
                pick_item()
                take_picked(all=True)
                give(Item.DoubleFlop)
            jump_to_script(204, 51)
        if tournament.cup == 1:
            give(bits=4000)
            narrator.say(t51.u5)
            give(Item.Sirloin, 3)
            if engine.item_did_not_fit:
                slot0.say(t51.u6)
                pick_item()
                take_picked(all=True)
                give(Item.Sirloin, 3)
            jump_to_script(204, 51)
        if tournament.cup == 2:
            give(bits=6000)
            narrator.say(t51.u7)
            give(Item.Restore)
            if engine.item_did_not_fit:
                slot0.say(t51.u8)
                pick_item()
                take_picked(all=True)
                give(Item.Restore)
        roll = random.roll(99)
        if tournament.cup == 2:
            if tamer.level != 10:
                if roll <= 9:
                    tamer.add(level=1)
                    narrator.say(t51.u9)
                    jump_to_script(204, 51)
            jump_to_script(204, 51)
        if tournament.cup == 3:
            give(bits=8000)
            narrator.say(t51.u10)
            give(Item.Flamingmane)
            if engine.item_did_not_fit:
                slot0.say(t51.u11)
                pick_item()
                take_picked(all=True)
                give(Item.Flamingmane)
        roll = random.roll(99)
        if tournament.cup == 3:
            if tamer.level != 10:
                if roll <= 19:
                    tamer.add(level=1)
                    narrator.say(t51.u12)
                    jump_to_script(204, 51)
            jump_to_script(204, 51)
        roll = random.roll(2)
        if tournament.cup == 4 and roll == 0:
            give(bits=10000)
            narrator.say(t51.u13)
            give(Item.MetalPart)
            if engine.item_did_not_fit:
                slot0.say(t51.u14)
                pick_item()
                take_picked(all=True)
                give(Item.MetalPart)
        elif tournament.cup == 4 and roll == 1:
            give(bits=10000)
            narrator.say(t51.u15)
            give(Item.FatalBone)
            if engine.item_did_not_fit:
                slot0.say(t51.u16)
                pick_item()
                take_picked(all=True)
                give(Item.FatalBone)
        elif tournament.cup == 4 and roll == 2:
            give(bits=10000)
            narrator.say(t51.u17)
            give(Item.MegaHand)
            if engine.item_did_not_fit:
                slot0.say(t51.u18)
                pick_item()
                take_picked(all=True)
                give(Item.MegaHand)
        roll = random.roll(99)
        if tournament.cup == 4:
            if tamer.level != 10:
                if roll <= 29:
                    tamer.add(level=1)
                    narrator.say(t51.u19)
                    jump_to_script(204, 51)
            jump_to_script(204, 51)
        elif tournament.cup == 6:
            give(bits=5000)
            narrator.say(t51.u20)
            give(Item.WhiteFang)
            if engine.item_did_not_fit:
                slot0.say(t51.u21)
                pick_item()
                take_picked(all=True)
                give(Item.WhiteFang)
            jump_to_script(204, 51)
        elif tournament.cup == 7:
            give(bits=5000)
            narrator.say(t51.u22)
            give(Item.Bluecrystal)
            if engine.item_did_not_fit:
                slot0.say(t51.u23)
                pick_item()
                take_picked(all=True)
                give(Item.Bluecrystal)
            jump_to_script(204, 51)
        elif tournament.cup == 8:
            give(bits=5000)
            narrator.say(t51.u24)
            give(Item.IronHoof)
            if engine.item_did_not_fit:
                slot0.say(t51.u25)
                pick_item()
                take_picked(all=True)
                give(Item.IronHoof)
            jump_to_script(204, 51)
        elif tournament.cup == 9:
            give(bits=5000)
            narrator.say(t51.u26)
            give(Item.MonoStone)
            if engine.item_did_not_fit:
                slot0.say(t51.u27)
                pick_item()
                take_picked(all=True)
                give(Item.MonoStone)
            jump_to_script(204, 51)
        elif tournament.cup == 10:
            give(bits=5000)
            narrator.say(t51.u28)
            give(Item.RedRuby)
            if engine.item_did_not_fit:
                slot0.say(t51.u29)
                pick_item()
                take_picked(all=True)
                give(Item.RedRuby)
            jump_to_script(204, 51)
        elif tournament.cup == 11:
            give(bits=8000)
            narrator.say(t51.u30)
            give(Item.Fireball)
            if engine.item_did_not_fit:
                slot0.say(t51.u31)
                pick_item()
                take_picked(all=True)
                give(Item.Fireball)
            jump_to_script(204, 51)
        elif tournament.cup == 12:
            give(bits=8000)
            narrator.say(t51.u32)
            give(Item.SpikeClub)
            if engine.item_did_not_fit:
                slot0.say(t51.u33)
                pick_item()
                take_picked(all=True)
                give(Item.SpikeClub)
            jump_to_script(204, 51)
        elif tournament.cup == 13:
            give(bits=8000)
            narrator.say(t51.u34)
            give(Item.Unihorn)
            if engine.item_did_not_fit:
                slot0.say(t51.u35)
                pick_item()
                take_picked(all=True)
                give(Item.Unihorn)
            jump_to_script(204, 51)
        elif tournament.cup == 14:
            give(bits=8000)
            narrator.say(t51.u36)
            give(Item.NorthStar)
            if engine.item_did_not_fit:
                slot0.say(t51.u37)
                pick_item()
                take_picked(all=True)
                give(Item.NorthStar)
            jump_to_script(204, 51)
        elif tournament.cup == 15:
            give(bits=8000)
            narrator.say(t51.u38)
            give(Item.Fertilizer)
            if engine.item_did_not_fit:
                slot0.say(t51.u39)
                pick_item()
                take_picked(all=True)
                give(Item.Fertilizer)
            jump_to_script(204, 51)
        elif tournament.cup == 16:
            give(bits=8000)
            narrator.say(t51.u40)
            give(Item.CyberPart)
            if engine.item_did_not_fit:
                slot0.say(t51.u41)
                pick_item()
                take_picked(all=True)
                give(Item.CyberPart)
            jump_to_script(204, 51)
        elif tournament.cup == 17:
            give(bits=8000)
            narrator.say(t51.u42)
            give(Item.Sunglasses)
            if engine.item_did_not_fit:
                slot0.say(t51.u43)
                pick_item()
                take_picked(all=True)
                give(Item.Sunglasses)
            jump_to_script(204, 51)
        elif tournament.cup == 18:
            give(bits=5000)
            narrator.say(t51.u44)
            give(Item.GreyClaws)
            if engine.item_did_not_fit:
                slot0.say(t51.u45)
                pick_item()
                take_picked(all=True)
                give(Item.GreyClaws)
            jump_to_script(204, 51)
        elif tournament.cup == 19:
            give(bits=5000)
            narrator.say(t51.u46)
            give(Item.WhiteWing)
            if engine.item_did_not_fit:
                slot0.say(t51.u47)
                pick_item()
                take_picked(all=True)
                give(Item.WhiteWing)
            jump_to_script(204, 51)
        elif tournament.cup == 20:
            give(bits=5000)
            narrator.say(t51.u48)
            give(Item.SteelDrill)
            if engine.item_did_not_fit:
                slot0.say(t51.u49)
                pick_item()
                take_picked(all=True)
                give(Item.SteelDrill)
            jump_to_script(204, 51)
        elif tournament.cup == 21:
            give(bits=5000)
            narrator.say(t51.u50)
            give(Item.BlackWing)
            if engine.item_did_not_fit:
                slot0.say(t51.u51)
                pick_item()
                take_picked(all=True)
                give(Item.BlackWing)
            jump_to_script(204, 51)
    elif engine.result != 2:
        slot0.say(t51.u0)
        narrator.say(t51.u1)
        give(Item.GiantMeat)
        if engine.item_did_not_fit:
            slot0.say(t51.u2)
            pick_item()
            take_picked(all=True)
            give(Item.GiantMeat)
        return
    if tournament.cup == 0:
        give(bits=500)
        narrator.say(t51.u52)
        give(Item.GiantMeat, 2)
        if engine.item_did_not_fit:
            slot0.say(t51.u53)
            pick_item()
            take_picked(all=True)
            give(Item.GiantMeat, 2)
        return
    if tournament.cup == 1:
        give(bits=1000)
        narrator.say(t51.u54)
        give(Item.Sirloin)
        if engine.item_did_not_fit:
            slot0.say(t51.u55)
            pick_item()
            take_picked(all=True)
            give(Item.Sirloin)
        return
    if tournament.cup == 2:
        give(bits=2000)
        narrator.say(t51.u56)
        give(Item.LargeMP)
        if engine.item_did_not_fit:
            slot0.say(t51.u57)
            pick_item()
            take_picked(all=True)
            give(Item.LargeMP)
        return
    if tournament.cup == 3:
        give(bits=3000)
        narrator.say(t51.u58)
        give(Item.Restore)
        if engine.item_did_not_fit:
            slot0.say(t51.u59)
            pick_item()
            take_picked(all=True)
            give(Item.Restore)
        return
    if tournament.cup == 4:
        give(bits=4000)
        narrator.say(t51.u60)
        give(Item.SupRestore)
        if engine.item_did_not_fit:
            slot0.say(t51.u61)
            pick_item()
            take_picked(all=True)
            give(Item.SupRestore)
        return
    if tournament.cup == 6:
        give(bits=2000)
        narrator.say(t51.u62)
        give(Item.SupRecovery)
        if engine.item_did_not_fit:
            slot0.say(t51.u63)
            pick_item()
            take_picked(all=True)
            give(Item.SupRecovery)
        return
    if tournament.cup == 7:
        give(bits=2000)
        narrator.say(t51.u64)
        give(Item.SupRecovery)
        if engine.item_did_not_fit:
            slot0.say(t51.u65)
            pick_item()
            take_picked(all=True)
            give(Item.SupRecovery)
        return
    if tournament.cup == 8:
        give(bits=2000)
        narrator.say(t51.u66)
        give(Item.SupRecovery)
        if engine.item_did_not_fit:
            slot0.say(t51.u67)
            pick_item()
            take_picked(all=True)
            give(Item.SupRecovery)
        return
    if tournament.cup == 9:
        give(bits=2000)
        narrator.say(t51.u68)
        give(Item.SupRecovery)
        if engine.item_did_not_fit:
            slot0.say(t51.u69)
            pick_item()
            take_picked(all=True)
            give(Item.SupRecovery)
        return
    if tournament.cup == 10:
        give(bits=2000)
        narrator.say(t51.u70)
        give(Item.SupRecovery)
        if engine.item_did_not_fit:
            slot0.say(t51.u71)
            pick_item()
            take_picked(all=True)
            give(Item.SupRecovery)
        return
    if tournament.cup == 11:
        give(bits=3000)
        narrator.say(t51.u72)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u73)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 12:
        give(bits=3000)
        narrator.say(t51.u74)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u75)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 13:
        give(bits=3000)
        narrator.say(t51.u76)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u77)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 14:
        give(bits=3000)
        narrator.say(t51.u78)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u79)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 15:
        give(bits=3000)
        narrator.say(t51.u80)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u81)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 16:
        give(bits=3000)
        narrator.say(t51.u82)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u83)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 17:
        give(bits=3000)
        narrator.say(t51.u84)
        give(Item.Omnipotent)
        if engine.item_did_not_fit:
            slot0.say(t51.u85)
            pick_item()
            take_picked(all=True)
            give(Item.Omnipotent)
        return
    if tournament.cup == 18:
        give(bits=2000)
        narrator.say(t51.u86)
        give(Item.OmniDisk)
        if engine.item_did_not_fit:
            slot0.say(t51.u87)
            pick_item()
            take_picked(all=True)
            give(Item.OmniDisk)
        return
    if tournament.cup == 19:
        give(bits=2000)
        narrator.say(t51.u88)
        give(Item.OmniDisk)
        if engine.item_did_not_fit:
            slot0.say(t51.u89)
            pick_item()
            take_picked(all=True)
            give(Item.OmniDisk)
        return
    if tournament.cup == 20:
        give(bits=2000)
        narrator.say(t51.u90)
        give(Item.OmniDisk)
        if engine.item_did_not_fit:
            slot0.say(t51.u91)
            pick_item()
            take_picked(all=True)
            give(Item.OmniDisk)
        return
    if tournament.cup == 21:
        give(bits=2000)
        narrator.say(t51.u92)
        give(Item.OmniDisk)
        if engine.item_did_not_fit:
            slot0.say(t51.u93)
            pick_item()
            take_picked(all=True)
            give(Item.OmniDisk)
        return
    raw.end_script()

# the section table, in the order of the original header
sections(254, 51)
