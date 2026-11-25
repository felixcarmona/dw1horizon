# 97, the Ice Sanctuary's statue room (§3.7, §5.5): once Angemon is awake the voice that woke it ("You who seek my
# soul") is heard again, from under the pedestal, and the pedestal is the way down to the Wall of Hearts (310; 311, the
# melted wall, after "Stay"). The hidden hall 104 is not the way in: the post-game's Machinedramon stands there always.
# Solarmon, a sun frozen in the hall (arcs/residents/README.md; its home: district/power-station.py), joins on either answer.
from dw import *
from dw.base.ice_sanctuary_97 import sanctuary
from ...state import root3, vault_kept, thaw_told
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_SOLARMON

solarmon = sanctuary.npc(Species.Solarmon, at=(800, -600), hp=580, mp=600, offense=120, defense=90, speed=110, brain=85, range=0, still=True, when=not recruited(Species.Solarmon) or new_challenger == CH_SOLARMON, alone=new_challenger == CH_SOLARMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Solarmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/power-station.py).

def challenge_solarmon():
    if new_challenger != CH_SOLARMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("solarmon.challenge.retry"))
        else:
            say(t("solarmon.challenge.intro1"), t("solarmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(solarmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("solarmon.challenge.won"))
                give(Item.MPChip)
                give(bits=1500)
                narrator.say(t("solarmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(-700, 1400)
                leave()


@solarmon.on_talk
def talk():
    if recruited(Species.Solarmon):
        challenge_solarmon()
    else:
        say("The cold forgot me here. Is the sun still up?")
        if ask(yes="It's still up", no="It has set"):
            say("Good. Then I am not the last one.")
        else:
            say("Then somebody has to shine.")
        say("Then I'll go where the lights are.")
        send_to_city(line="Solarmon joined the city!", species=Species.Solarmon)


# The band across the corridor (step 1) is also the only way on to the Sanctuary proper (BlueMeramon, the gym): the way
# down is offered until the tamer has answered, and never again stands in the way afterwards.
@sanctuary.on_step(1, when=recruited(Species.Angemon) and not root3 and not vault_kept)
def the_voice_below():
    narrator.say("From under the pedestal, a cold voice:", "\"Deeper... The hearts are kept deeper...\"")
    tamer.say("There's more down there! Let's go, {partner}!")
    warp(310, entry=0)

@sanctuary.on_step(1, when=root3 and not thaw_told)
def to_the_door():
    warp(311, entry=0)
