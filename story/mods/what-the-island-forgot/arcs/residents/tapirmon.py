# Dragon Eye Lake 6: Tapirmon sleeps and talks about the dreams it has eaten; the second talk wakes it. No fight. Its home
# is the Market Shed (district/market-shed.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_TAPIRMON

lake = screen(Screen.dragon_eye_lake_6)
tapirmon = lake.npc(Species.Tapirmon, at=(650, -2000), range=0, still=True, when=not recruited(Species.Tapirmon) or new_challenger == CH_TAPIRMON, alone=new_challenger == CH_TAPIRMON)
tapirmon_stirred = flag()


@tapirmon.on_talk(when=not tapirmon_stirred)
def asleep():
    say("Zzz... a dream of flying... crunchy... a dream of home... sweet... zzz...")
    tapirmon_stirred.set()


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Tapirmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/market-shed.py).

def challenge_tapirmon():
    if new_challenger != CH_TAPIRMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("tapirmon.challenge.retry"))
        else:
            say(t("tapirmon.challenge.intro1"), t("tapirmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(tapirmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("tapirmon.challenge.won"))
                give(Item.RestPillow)
                give(bits=1500)
                narrator.say(t("tapirmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(1350, -4400)
                leave()


@tapirmon.on_talk
def awake():
    if recruited(Species.Tapirmon):
        challenge_tapirmon()
    else:
        say("Mmf? Who's there? Oh. You dream of a big city. I sell those.")
        walk_away(2050, -2050, looks=3)         # off to the east exit along the shore (the inside of a free tile), as Kunemon
        send_to_city(line="Tapirmon joined the city!", species=Species.Tapirmon)
