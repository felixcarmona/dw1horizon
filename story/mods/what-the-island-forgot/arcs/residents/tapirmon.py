# Dragon Eye Lake 6: Tapirmon sleeps and talks about the dreams it has eaten; the second talk wakes it. No fight. Its home
# is the Market Shed (district/market-shed.py).
from dw import *

lake = screen(Screen.dragon_eye_lake_6)
tapirmon = lake.npc(Species.Tapirmon, at=(650, -2000), range=0, when=not recruited(Species.Tapirmon))
tapirmon_stirred = flag()


@tapirmon.on_talk(when=not tapirmon_stirred)
def asleep():
    say("Zzz... a dream of flying... crunchy... a dream of home... sweet... zzz...")
    tapirmon_stirred.set()


@tapirmon.on_talk
def awake():
    say("Mmf? Who's there? Oh. You dream of a big city. I sell those.")
    send_to_city(line="Tapirmon joined the city!", species=Species.Tapirmon)
