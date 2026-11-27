# 325, the Kennel (design/arc-seam.md §2, story-bible.md §3.8): the hunters' dead-end chamber, with cages of light.
# Its keeper is the named hunter, a DarkLizardmon (Overdell's stats): a scripted battle, no running. Beaten (flag H), it
# runs, and the one Digimon still in a cage, a Bearmon "being erased", remembers itself and goes to the city (its
# origin: it lives in the Works' Container House, district/container-house.py).
from dw import *
from dw.text import text
from ...state import hunter_beaten
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_BEARMON

kennel = new_screen(325, map="build/what-the-island-forgot-maps/screens/SEAM03.MAP")
chest_kennel = flag()
keeper = kennel.npc(Species.DarkLizardmon, at=(0, -500), hp=3600, mp=3600, offense=580, defense=320, speed=120, brain=150,
                    bits=800, range=0, when=not hunter_beaten)
caged = kennel.npc(Species.Bearmon, at=(-600, 300), hp=590, mp=600, offense=115, defense=95, speed=110, brain=80, range=0, still=True, when=not recruited(Species.Bearmon) or new_challenger == CH_BEARMON, alone=new_challenger == CH_BEARMON)

@keeper.on_talk(scene=True)
def the_named_hunter():
    face(tamer)
    tamer.face(keeper)
    say(text.s034.sec7.u0)
    say("Nobody leaves this place with a name. Not them, not you.")
    if fight(keeper, escape=False) != "won":
        return                    # a lost battle wakes the tamer in Jijimon's house: the hunter waits here still
    say("I am not allowed a single mistake... and now...")
    hunter_beaten.set()
    sound(8, 13)
    wait(1000)
    leave()                       # (walk_away after its battle never ended: the scene hung there, twice)
    warp(325, entry=0)            # the screen again: Bearmon walked out of its cage for the battle (every bystander does)

@caged.on_talk(when=hunter_beaten and not recruited(Species.Bearmon), scene=True)
def remembers_itself():
    face(tamer)
    say("Orders... Important... Orders...")
    tamer.say("Hey. Hey! You're free now. The hunter's gone.")
    wait(1000)
    say("...Grr? Where... I am Bearmon. I am Bearmon! I wrestle in the hills!", "I had almost forgotten my own name.")
    send_to_city(line="Bearmon joined the city!", species=Species.Bearmon)

# Resident challenges (content/tables/resident-challenges.json): the talk of a recruited Bearmon, on its challenge day
# (it leaves without a walk: walk_away hung on this screen).
def challenge_bearmon():
    if new_challenger != CH_BEARMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("bearmon.challenge.retry"))
        else:
            say(t("bearmon.challenge.intro1"), t("bearmon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(caged, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("bearmon.challenge.won"))
                give(Item.RedBerry)
                give(bits=1500)
                narrator.say(t("bearmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                leave()


@caged.on_talk
def being_erased():
    if recruited(Species.Bearmon):
        challenge_bearmon()
    else:
        say("Orders. Important. Orders. Important...")

@kennel.on_enter
def enter():
    spawn_chest(Item.OffChip, at=(600, 300), opened=chest_kennel)
    # Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Bearmon is the
    # challenger and has not been beaten yet it waits in its old cage, stronger; any other day it is home.
    if recruited(Species.Bearmon) and new_challenger != CH_BEARMON:
        caged.leave()
