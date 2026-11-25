# Yuramon's riddles of the day (script 210, section 1: the library its talk in File City jumps to). They live here, not in
# script 162 with the rest of its talk: the riddles in nine languages do not fit in the 16 384 bytes of one script. Script
# 210 is Jijimon's news (jijimon-news.py); a library costs no memory while the screen runs, it is read when the talk jumps.
#
# After the ending (docs/mods/resident-challenges.md): the rows marked `hint` in content/tables/resident-challenges.json,
# and only those (tools/test_resident_challenges.py checks it): each one a riddle of who (by trade or habit, never the
# name) and where (the site's landscape, never its name) while its challenger is out and not yet beaten (a beaten one's
# var is its constant + CHALLENGE_BEATEN). Anyone else out, or beaten: walk the city. Nobody out: all quiet.
from dw import *
from dw.names import *
from ...state import challenger, new_challenger
from ...state import (
    CH_BETAMON, CH_TYRANNOMON, CH_MERAMON, CH_SEADRAMON, CH_NUMEMON, CH_MAMEMON, CH_ELECMON, CH_GARURUMON,
    CH_FRIGIMON, CH_SKULLGREYMON, CH_METALMAMEMON, CH_VADEMON, CH_PATAMON, CH_KUNEMON, CH_UNIMON, CH_OGREMON,
    CH_SHELLMON, CH_BAKEMON, CH_SUKAMON, CH_ANDROMON, CH_ETEMON, CH_BIYOMON, CH_MONOCHROMON, CH_COELAMON,
    CH_KOKATORIMON, CH_MOJYAMON, CH_MEGADRAMON, CH_PIXIMON, CH_DIGITAMAMON, CH_PENGUINMON, CH_MYOTISMON,
    CH_WARUMONZAEMON, CH_KOTEMON)

lib = script(210)                 # no screen of the Screen list
yuramon = entity(5)               # Yuramon, slot 0 of File City's script 162, still talking

@lib.section(1, when=engine.game_beaten)
def the_day_rumours():
    if challenger == CH_BETAMON:
        yuramon.say(t("betamon.rumour.who"), t("betamon.rumour.where"))
    elif challenger == CH_TYRANNOMON:
        yuramon.say(t("tyrannomon.rumour.who"), t("tyrannomon.rumour.where"))
    elif challenger == CH_MERAMON:
        yuramon.say(t("meramon.rumour.who"), t("meramon.rumour.where"))
    elif challenger == CH_SEADRAMON:
        yuramon.say(t("seadramon.rumour.who"), t("seadramon.rumour.where"))
    elif challenger == CH_NUMEMON:
        yuramon.say(t("numemon.rumour.who"), t("numemon.rumour.where"))
    elif challenger == CH_MAMEMON:
        yuramon.say(t("mamemon.rumour.who"), t("mamemon.rumour.where"))
    elif challenger == CH_ELECMON:
        yuramon.say(t("elecmon.rumour.who"), t("elecmon.rumour.where"))
    elif challenger == CH_GARURUMON:
        yuramon.say(t("garurumon.rumour.who"), t("garurumon.rumour.where"))
    elif challenger == CH_FRIGIMON:
        yuramon.say(t("frigimon.rumour.who"), t("frigimon.rumour.where"))
    elif challenger == CH_SKULLGREYMON:
        yuramon.say(t("skullgreymon.rumour.who"), t("skullgreymon.rumour.where"))
    elif challenger == CH_METALMAMEMON:
        yuramon.say(t("metalmamemon.rumour.who"), t("metalmamemon.rumour.where"))
    elif challenger == CH_VADEMON:
        yuramon.say(t("vademon.rumour.who"), t("vademon.rumour.where"))
    elif challenger == CH_PATAMON:
        yuramon.say(t("patamon.rumour.who"), t("patamon.rumour.where"))
    elif challenger == CH_KUNEMON:
        yuramon.say(t("kunemon.rumour.who"), t("kunemon.rumour.where"))
    elif challenger == CH_UNIMON:
        yuramon.say(t("unimon.rumour.who"), t("unimon.rumour.where"))
    elif challenger == CH_OGREMON:
        yuramon.say(t("ogremon.rumour.who"), t("ogremon.rumour.where"))
    elif challenger == CH_SHELLMON:
        yuramon.say(t("shellmon.rumour.who"), t("shellmon.rumour.where"))
    elif challenger == CH_BAKEMON:
        yuramon.say(t("bakemon.rumour.who"), t("bakemon.rumour.where"))
    elif challenger == CH_SUKAMON:
        yuramon.say(t("sukamon.rumour.who"), t("sukamon.rumour.where"))
    elif challenger == CH_ANDROMON:
        yuramon.say(t("andromon.rumour.who"), t("andromon.rumour.where"))
    elif challenger == CH_ETEMON:
        yuramon.say(t("etemon.rumour.who"), t("etemon.rumour.where"))
    elif challenger == CH_BIYOMON:
        yuramon.say(t("biyomon.rumour.who"), t("biyomon.rumour.where"))
    elif challenger == CH_MONOCHROMON:
        yuramon.say(t("monochromon.rumour.who"), t("monochromon.rumour.where"))
    elif challenger == CH_COELAMON:
        yuramon.say(t("coelamon.rumour.who"), t("coelamon.rumour.where"))
    elif challenger == CH_KOKATORIMON:
        yuramon.say(t("kokatorimon.rumour.who"), t("kokatorimon.rumour.where"))
    elif challenger == CH_MOJYAMON:
        yuramon.say(t("mojyamon.rumour.who"), t("mojyamon.rumour.where"))
    elif challenger == CH_MEGADRAMON:
        yuramon.say(t("megadramon.rumour.who"), t("megadramon.rumour.where"))
    elif challenger == CH_PIXIMON:
        yuramon.say(t("piximon.rumour.who"), t("piximon.rumour.where"))
    elif challenger == CH_DIGITAMAMON:
        yuramon.say(t("digitamamon.rumour.who"), t("digitamamon.rumour.where"))
    elif challenger == CH_PENGUINMON:
        yuramon.say(t("penguinmon.rumour.who"), t("penguinmon.rumour.where"))
    elif challenger == CH_MYOTISMON:
        yuramon.say(t("myotismon.rumour.who"), t("myotismon.rumour.where"))
    elif challenger == CH_WARUMONZAEMON:
        yuramon.say(t("warumonzaemon.rumour.who"), t("warumonzaemon.rumour.where"))
    elif new_challenger != CH_KOTEMON:
        if challenger == 0 and new_challenger == 0:
            yuramon.say(t("rumour.quiet"))
        else:
            yuramon.say(t("rumour.unheard"))
        return
    if new_challenger == CH_KOTEMON:
        yuramon.say(t("kotemon.rumour.who"), t("kotemon.rumour.where"))
