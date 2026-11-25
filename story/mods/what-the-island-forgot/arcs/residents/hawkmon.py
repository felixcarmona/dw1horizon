# The Great Canyon Entrance 36 (the bridge's heap cannot hold a fourth model with Birdramon's scene, and no spot on the
# top area keeps a walkable path):
# Hawkmon watches everything and joins if asked. No fight. Its home is Birdra Transport (city/birdra-transport.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_HAWKMON

ledge = screen(Screen.great_canyon_entrance)
hawkmon = ledge.npc(Species.Hawkmon, at=(1200, -450), range=0, still=True, when=not recruited(Species.Hawkmon) or new_challenger == CH_HAWKMON, alone=new_challenger == CH_HAWKMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Hawkmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (city/birdra-transport.py).

def challenge_hawkmon():
    if new_challenger != CH_HAWKMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("hawkmon.challenge.retry"))
        else:
            say(t("hawkmon.challenge.intro1"), t("hawkmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(hawkmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("hawkmon.challenge.won"))
                give(Item.HawkRadish)
                give(bits=1500)
                narrator.say(t("hawkmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(-1200, -1150)
                leave()


@hawkmon.on_talk
def talk():
    if recruited(Species.Hawkmon):
        challenge_hawkmon()
    else:
        say("I see everything from up here. Nobody ever asks.")
        tamer.say("Then I'm asking. What do you see?")
        say("Far off, File City. New roofs every week, and nobody keeping watch over them.")
        if ask(yes="It needs a lookout", no="It's fine as it is"):
            say("A lookout. Yes. I thought nobody would ever say it.")
            walk_away(2150, -450, looks=3)    # runs east across the open ground, as the game's recruits do, then leaves
            send_to_city(line="Hawkmon joined the city!", species=Species.Hawkmon, camera=False)
        else:
            say("I'll be here. I see everything, remember.")
