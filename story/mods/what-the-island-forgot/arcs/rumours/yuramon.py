# File City, Yuramon the rumour-teller (script 162, §3.0): the first talk and the offer to spread the word of the human.
# With the word spread, Jijimon's talk arms Greymon's challenge sooner: jijimon-news.py. After the ending it tells the day's
# resident challenges: a riddle for each challenger out today whose absence a walk through the city does not show.
from dw import *
from dw.names import *
from dw.base.file_city_168 import city_168, yuramon
from ...state import greymon_armed_by_old_disc, rumours_asked, rumours_spread, challenger, new_challenger
from ...state import (
    CH_BETAMON, CH_TYRANNOMON, CH_MERAMON, CH_SEADRAMON, CH_NUMEMON, CH_MAMEMON, CH_ELECMON, CH_GARURUMON,
    CH_FRIGIMON, CH_SKULLGREYMON, CH_METALMAMEMON, CH_VADEMON, CH_PATAMON, CH_KUNEMON, CH_UNIMON, CH_OGREMON,
    CH_SHELLMON, CH_BAKEMON, CH_SUKAMON, CH_ANDROMON, CH_ETEMON, CH_BIYOMON, CH_MONOCHROMON, CH_COELAMON,
    CH_KOKATORIMON, CH_MOJYAMON, CH_MEGADRAMON, CH_PIXIMON, CH_DIGITAMAMON, CH_PENGUINMON, CH_MYOTISMON,
    CH_WARUMONZAEMON, CH_KOTEMON)

@yuramon.on_talk(when=not rumours_asked)
def the_word():
    say("Ehehe! A human, a real human, in File City! Nobody out there knows yet...")
    say("Want me to tell everyone? My rumours go suuuper far.", "The whole island would know by tomorrow!")
    rumours_asked.set()
    if ask(yes="Spread it", no="Keep it quiet"):
        say("Leave it to me! Everyone will hear about you. Eeeveryone!")
        rumours_spread.set()
    else:
        say("Okaaay. It'll be our secret, then. Ehehe.")

@city_168.on_enter(when=greymon_armed_by_old_disc and greymon_challenge_ready)
def forget_old_challenge():
    # A save from 0.0.2 may hold him armed on entering the city, for whatever partner: Jijimon's talk arms him again.
    greymon_armed_by_old_disc.clear()
    greymon_challenge_ready.clear()


# After the ending (docs/mods/resident-challenges.md): the riddles of the day. The rows marked `hint` in
# content/tables/resident-challenges.json, and only those (tools/test_resident_challenges.py checks it): each one a riddle of
# who (by trade or habit, never the name) and where (the site's landscape, never its name) while its challenger is out and not
# yet beaten (a beaten one's var is its constant + CHALLENGE_BEATEN). Anyone else out, or beaten: walk the city. Nobody out:
# all quiet. The days Andromon stands in Yuramon's place there is no rumour.
@yuramon.on_talk(when=rumours_asked and engine.game_beaten)
def the_day_rumours():
    if challenger == CH_BETAMON:
        say(t("betamon.rumour.who"), t("betamon.rumour.where"))
    elif challenger == CH_TYRANNOMON:
        say(t("tyrannomon.rumour.who"), t("tyrannomon.rumour.where"))
    elif challenger == CH_MERAMON:
        say(t("meramon.rumour.who"), t("meramon.rumour.where"))
    elif challenger == CH_SEADRAMON:
        say(t("seadramon.rumour.who"), t("seadramon.rumour.where"))
    elif challenger == CH_NUMEMON:
        say(t("numemon.rumour.who"), t("numemon.rumour.where"))
    elif challenger == CH_MAMEMON:
        say(t("mamemon.rumour.who"), t("mamemon.rumour.where"))
    elif challenger == CH_ELECMON:
        say(t("elecmon.rumour.who"), t("elecmon.rumour.where"))
    elif challenger == CH_GARURUMON:
        say(t("garurumon.rumour.who"), t("garurumon.rumour.where"))
    elif challenger == CH_FRIGIMON:
        say(t("frigimon.rumour.who"), t("frigimon.rumour.where"))
    elif challenger == CH_SKULLGREYMON:
        say(t("skullgreymon.rumour.who"), t("skullgreymon.rumour.where"))
    elif challenger == CH_METALMAMEMON:
        say(t("metalmamemon.rumour.who"), t("metalmamemon.rumour.where"))
    elif challenger == CH_VADEMON:
        say(t("vademon.rumour.who"), t("vademon.rumour.where"))
    elif challenger == CH_PATAMON:
        say(t("patamon.rumour.who"), t("patamon.rumour.where"))
    elif challenger == CH_KUNEMON:
        say(t("kunemon.rumour.who"), t("kunemon.rumour.where"))
    elif challenger == CH_UNIMON:
        say(t("unimon.rumour.who"), t("unimon.rumour.where"))
    elif challenger == CH_OGREMON:
        say(t("ogremon.rumour.who"), t("ogremon.rumour.where"))
    elif challenger == CH_SHELLMON:
        say(t("shellmon.rumour.who"), t("shellmon.rumour.where"))
    elif challenger == CH_BAKEMON:
        say(t("bakemon.rumour.who"), t("bakemon.rumour.where"))
    elif challenger == CH_SUKAMON:
        say(t("sukamon.rumour.who"), t("sukamon.rumour.where"))
    elif challenger == CH_ANDROMON:
        say(t("andromon.rumour.who"), t("andromon.rumour.where"))
    elif challenger == CH_ETEMON:
        say(t("etemon.rumour.who"), t("etemon.rumour.where"))
    elif challenger == CH_BIYOMON:
        say(t("biyomon.rumour.who"), t("biyomon.rumour.where"))
    elif challenger == CH_MONOCHROMON:
        say(t("monochromon.rumour.who"), t("monochromon.rumour.where"))
    elif challenger == CH_COELAMON:
        say(t("coelamon.rumour.who"), t("coelamon.rumour.where"))
    elif challenger == CH_KOKATORIMON:
        say(t("kokatorimon.rumour.who"), t("kokatorimon.rumour.where"))
    elif challenger == CH_MOJYAMON:
        say(t("mojyamon.rumour.who"), t("mojyamon.rumour.where"))
    elif challenger == CH_MEGADRAMON:
        say(t("megadramon.rumour.who"), t("megadramon.rumour.where"))
    elif challenger == CH_PIXIMON:
        say(t("piximon.rumour.who"), t("piximon.rumour.where"))
    elif challenger == CH_DIGITAMAMON:
        say(t("digitamamon.rumour.who"), t("digitamamon.rumour.where"))
    elif challenger == CH_PENGUINMON:
        say(t("penguinmon.rumour.who"), t("penguinmon.rumour.where"))
    elif challenger == CH_MYOTISMON:
        say(t("myotismon.rumour.who"), t("myotismon.rumour.where"))
    elif challenger == CH_WARUMONZAEMON:
        say(t("warumonzaemon.rumour.who"), t("warumonzaemon.rumour.where"))
    elif new_challenger != CH_KOTEMON:
        if challenger == 0 and new_challenger == 0:
            say(t("rumour.quiet"))
        else:
            say(t("rumour.unheard"))
        return
    if new_challenger == CH_KOTEMON:
        say(t("kotemon.rumour.who"), t("kotemon.rumour.where"))
