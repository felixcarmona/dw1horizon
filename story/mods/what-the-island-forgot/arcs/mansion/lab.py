# 67, the Underground Lab (§3.4): Myotismon's rescue. The game's own talk, then Analogman's second notebook among the
# bones, which only the tamer can read (fragment M6), and the one-time question: keep SkullGreymon (the original: both
# join the city, SkullGreymon for the Arena) or let him rest (R2: the bones go back to the basement's rune circle and the
# Crypt opens and the seven locked doors of the mansion stand open; SkullGreymon joins later, by itself: city/jijimons-house.py).
from dw import *
from dw.text import text
from dw.names import *
from dw.base.underground_lab_67 import lab, myotismon, bakemon
from ...state import root2, memories, m5_notebook, m6_notebook, memory_news

t5 = text.s064.sec5

@myotismon.on_talk(when=not myotismon_joined_city and not skullgreymon_debut_news_read, scene=True)
def the_collection():
    tamer.say(t5.u3)
    play(21)
    bakemon.play(21)
    face(tamer)
    bakemon.face(tamer)
    say(t5.u4)
    tamer.say(t5.u5)
    say(t5.u6)
    tamer.say(t5.u7)
    say(t5.u8)
    tamer.play(19)
    tamer.say(t5.u9)
    say(t5.u10)
    tamer.say(t5.u11)
    say(t5.u12)
    tamer.say(t5.u13)
    say(t5.u14)
    tamer.say(t5.u15)
    say(t5.u16)
    tamer.say("Hm? There's a notebook in the bone pile... It's written in human writing!")
    if m5_notebook:
        tamer.say("The same hand as the one under the canyon.")
    tamer.say("\"Grey will not take the new orders. The bones keep what the body forgets.\"", "\"Try the bones.\"")
    m6_notebook.set()
    memories.add(1)
    memory_news.set()
    say("Grey... the Grey Lord of this house.", "Then the research I believed was mine was his, all along.")
    say("Tell me, boy. What should become of SkullGreymon?",
        "I can keep him, and now he would obey. Or the bones can go back to the circle downstairs, and he can rest.")
    if ask(yes="Let him rest", no="Keep him"):
        say("...Yes. I think it is what the bones want.", "I will close the circle. Come down to the basement, under the stairs, when you are ready.")
        root2.set()
        open_the_doors()
        myotismon_joined_city.set()
        recruit(Species.Myotismon, prosperity=3)
    else:
        myotismon_joined_city.set()
        recruit(Species.Myotismon)
        recruit(Species.SkullGreymon)
        engine.prosperity.add(3)
    camera.on(tamer, speed=10)
    camera.arrived()

def open_the_doors():
    # the Grey Lord's seven locked doors stand open for good (the house was his; with his bones at rest it lets go)
    mansion_door_unlocked.s52_s55_exit4.set()
    mansion_door_unlocked.s52_s55_exit5.set()
    mansion_door_unlocked.s57_s58.set()
    mansion_door_unlocked.s53_s63.set()
    mansion_door_unlocked.s52_s59.set()
    mansion_door_unlocked.s53_s64.set()
    mansion_door_unlocked.s53_s232.set()
