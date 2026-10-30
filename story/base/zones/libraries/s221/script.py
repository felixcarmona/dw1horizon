# The Python view of script 221 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(221)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t5 = text.s221.sec5

@lib.on_enter
def enter():    # section 254
    return slot0.talk()

@slot0.on_talk
def talk():    # section 5
    if recruited(Species.Agumon) and not jijimon_news_told.agumon:
        say(t5.u0)
        jijimon_news_told.agumon.set()
        return
    if recruited(Species.Palmon) and not jijimon_news_told.palmon:
        say(t5.u1)
        jijimon_news_told.palmon.set()
        return
    if recruited(Species.Kunemon) and not jijimon_news_told.kunemon:
        say(t5.u2)
        jijimon_news_told.kunemon.set()
        return
    if recruited(Species.Centarumon) and not jijimon_news_told.centarumon:
        say(t5.u3)
        jijimon_news_told.centarumon.set()
        return
    if recruited(Species.Coelamon) and not jijimon_news_told.coelamon:
        say(t5.u4)
        jijimon_news_told.coelamon.set()
        return
    if recruited(Species.Betamon) and not jijimon_news_told.betamon:
        say(t5.u5)
        jijimon_news_told.betamon.set()
        return
    if recruited(Species.Bakemon) and not jijimon_news_told.bakemon:
        say(t5.u6)
        jijimon_news_told.bakemon.set()
        return
    if recruited(Species.Vegiemon) and not jijimon_news_told.vegiemon:
        say(t5.u7)
        jijimon_news_told.vegiemon.set()
        return
    if recruited(Species.Tyrannomon) and not trigger(580):
        say(t5.u8)
        trigger(580).set()
        return
    if recruited(Species.Meramon) and not trigger(581):
        say(t5.u9)
        trigger(581).set()
        return
    if recruited(Species.Frigimon) and not jijimon_news_told.frigimon:
        say(t5.u10)
        jijimon_news_told.frigimon.set()
        return
    if recruited(Species.Garurumon) and not jijimon_news_told.garurumon:
        say(t5.u11)
        jijimon_news_told.garurumon.set()
        return
    if recruited(Species.Birdramon) and not jijimon_news_told.birdramon:
        say(t5.u12)
        jijimon_news_told.birdramon.set()
        return
    if recruited(Species.Shellmon) and not jijimon_news_told.shellmon:
        say(t5.u13)
        jijimon_news_told.shellmon.set()
        return
    if recruited(Species.Elecmon) and not trigger(580):
        say(t5.u14)
        trigger(580).set()
        return
    if recruited(Species.Kokatorimon) and not jijimon_news_told.kokatorimon:
        say(t5.u15)
        jijimon_news_told.kokatorimon.set()
        return
    if recruited(Species.Monochromon) and not jijimon_news_told.monochromon:
        say(t5.u16)
        jijimon_news_told.monochromon.set()
        return
    if recruited(Species.Unimon) and not jijimon_news_told.unimon:
        say(t5.u17)
        jijimon_news_told.unimon.set()
        return
    if recruited(Species.Patamon) and not jijimon_news_told.patamon:
        say(t5.u18)
        jijimon_news_told.patamon.set()
        return
    if recruited(Species.Biyomon) and not jijimon_news_told.biyomon:
        say(t5.u19)
        jijimon_news_told.biyomon.set()
        return
    if recruited(Species.Greymon) and not jijimon_news_told.greymon:
        say(t5.u20)
        jijimon_news_told.greymon.set()
        return
    if recruited(Species.Penguinmon) and not jijimon_news_told.penguinmon:
        say(t5.u21)
        jijimon_news_told.penguinmon.set()
        return
    if recruited(Species.Angemon) and not jijimon_news_told.angemon:
        say(t5.u22)
        jijimon_news_told.angemon.set()
        return
    if recruited(Species.Drimogemon) and not jijimon_news_told.drimogemon:
        say(t5.u23)
        jijimon_news_told.drimogemon.set()
        return
    if recruited(Species.Gabumon) and not jijimon_news_told.gabumon:
        say(t5.u24)
        jijimon_news_told.gabumon.set()
        return
    if recruited(Species.Ninjamon) and not jijimon_news_told.ninjamon:
        say(t5.u25)
        jijimon_news_told.ninjamon.set()
        return
    if recruited(Species.Whamon) and not jijimon_news_told.whamon:
        say(t5.u26)
        jijimon_news_told.whamon.set()
        return
    if recruited(Species.Mojyamon) and not jijimon_news_told.mojyamon:
        say(t5.u27)
        jijimon_news_told.mojyamon.set()
        return
    if recruited(Species.Mamemon) and not jijimon_news_told.mamemon:
        say(t5.u28)
        jijimon_news_told.mamemon.set()
        return
    if recruited(Species.Numemon) and not jijimon_news_told.numemon:
        say(t5.u29)
        jijimon_news_told.numemon.set()
        return
    if recruited(Species.Kabuterimon) and not trigger(581):
        say(t5.u30)
        trigger(581).set()
        return
    if recruited(Species.Kuwagamon) and not jijimon_news_told.kuwagamon:
        say(t5.u31)
        jijimon_news_told.kuwagamon.set()
        return
    if recruited(Species.Giromon) and not jijimon_news_told.giromon:
        say(t5.u32)
        jijimon_news_told.giromon.set()
        return
    if recruited(Species.Ogremon) and not jijimon_news_told.ogremon:
        say(t5.u33)
        jijimon_news_told.ogremon.set()
        return
    if recruited(Species.Leomon) and not jijimon_news_told.leomon:
        say(t5.u34)
        jijimon_news_told.leomon.set()
        return
    if recruited(Species.Piximon) and not jijimon_news_told.piximon:
        say(t5.u35)
        jijimon_news_told.piximon.set()
        return
    if recruited(Species.Etemon) and not jijimon_news_told.etemon:
        say(t5.u36)
        jijimon_news_told.etemon.set()
        return
    if recruited(Species.MetalMamemon) and not jijimon_news_told.metalmamemon:
        say(t5.u37)
        jijimon_news_told.metalmamemon.set()
        return
    if recruited(Species.Vademon) and not jijimon_news_told.vademon:
        say(t5.u38)
        jijimon_news_told.vademon.set()
        return
    if recruited(Species.MetalGreymonVirus) and not jijimon_news_told.metalgreymon_virus:
        say(t5.u39)
        jijimon_news_told.metalgreymon_virus.set()
        return
    if recruited(Species.Nanimon) and not jijimon_news_told.nanimon:
        say(t5.u40)
        jijimon_news_told.nanimon.set()
        return
    if recruited(Species.Monzaemon) and not jijimon_news_told.monzaemon:
        say(t5.u41)
        jijimon_news_told.monzaemon.set()
        return
    if recruited(Species.Devimon) and not jijimon_news_told.devimon:
        say(t5.u42)
        jijimon_news_told.devimon.set()
        return
    if recruited(Species.Airdramon) and not jijimon_news_told.airdramon:
        say(t5.u43)
        jijimon_news_told.airdramon.set()
        return
    if recruited(Species.Digitamamon) and not jijimon_news_told.digitamamon:
        say(t5.u44)
        jijimon_news_told.digitamamon.set()
        return
    if recruited(Species.SkullGreymon) and not jijimon_news_told.skullgreymon:
        say(t5.u45)
        jijimon_news_told.skullgreymon.set()
        return
    if recruited(Species.Andromon) and not jijimon_news_told.andromon:
        say(t5.u46)
        jijimon_news_told.andromon.set()
        return
    jump_to_script(210, 77)

# the section table, in the order of the original header
sections(254, 5)
