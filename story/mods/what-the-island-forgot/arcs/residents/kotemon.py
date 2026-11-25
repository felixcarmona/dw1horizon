# Ogre Fortress 45, the gate yard (the brief's 130 reads no NPC list): Kotemon trains alone once the fortress has fallen. A fight at
# the fortress's strength, with no running away. Its home is the Arena lobby (city/arena-lobby.py).
# Only after ogre_fortress_cleared: until then the screen is the Gabumon ambush (MAPHEAD 45 places the three Gabumon only while
# the fortress stands), and Kotemon's 87 KB model next to three Gabumon left 38 KB of heap with a big partner, and a fourth
# Digimon the battle start has to send away. The two never load together.
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KOTEMON

yard = screen(Screen.ogre_fortress_45)
kotemon = yard.npc(Species.Kotemon, at=(1000, 850), hp=2400, mp=1600, offense=480, defense=260, speed=120, brain=120, bits=300,
                   range=0, still=True, when=ogre_fortress_cleared, alone=new_challenger == CH_KOTEMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kotemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (trains in the arena lobby).
@yard.on_enter(when=recruited(Species.Kotemon))
def challenge_away_kotemon():
    if not engine.game_beaten or new_challenger != CH_KOTEMON:
        kotemon.leave()


def challenge_kotemon():
    if new_challenger != CH_KOTEMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("kotemon.challenge.retry"))
        else:
            say(t("kotemon.challenge.intro1"), t("kotemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(kotemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kotemon.challenge.won"))
                give(Item.MuscleYam)
                give(bits=1500)
                narrator.say(t("kotemon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(700, 3300)
                leave()


@kotemon.on_talk
def talk():
    if recruited(Species.Kotemon):
        challenge_kotemon()
    else:
        say("One more thousand swings.")
        if fight(kotemon, escape=False) != "won":
            return                    # a lost battle wakes the tamer in Jijimon's house: Kotemon goes on swinging
        say("Teach me? No, I'll teach you. Where's the Arena?")
        run(250, 1150)
        send_to_city(line="Kotemon joined the city!", species=Species.Kotemon, camera=False)
