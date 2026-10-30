# 157, Factorial Town, Andromon (§3.5): once the town has reopened (the game's own talk, which also lifts the lockdown of
# the main entrance), Andromon asks where the power should go. "Restart it": the game's own factory. "Keep it shut":
# all of it to the archive, which then tells where the three stations of the north-east are (fragment M3+).
from dw import *
from dw.names import *
from dw.base.factorial_town_157 import andromon
from ...state import factory_asked, factory_kept_shut, m3_stations, memories, memory_news

@andromon.on_talk(when=factorial_town_reopened and not factory_asked and not recruited(Species.Andromon))
def where_the_power_goes():
    say("There is one more decision. The power of this town can run the factory again,",
        "or it can all go into the archive. Not both.")
    factory_asked.set()
    if ask(yes="Restart it", no="Keep it shut"):
        say("Understood. The factory will restart.")
        return andromon.talk()
    factory_kept_shut.set()
    say("Understood. All power to the archive.")
    wait(1000)
    say("Partial data recovered.", "Three places in the north-east were made at the same time, eighty years ago:",
        "a room under the Ogre Fortress, a basement under the Grey Lord's Mansion, a hall under the Ice Sanctuary.")
    say("Something touches the island from each of them. They are... stations.")
    m3_stations.set()
    memories.add(1)
    memory_news.set()
