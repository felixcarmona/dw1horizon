# 328, the Watchtower (design/arc-seam.md §2): Saberdramon, who has "flown high and seen far", reports to a voice that
# is not there: the first time the player sees Analogman listening. Seen, it flies off. No battle.
from dw import *

tower = new_screen(328, map="build/what-the-island-forgot-maps/screens/SEAM06.MAP")
lookout = tower.npc(Species.Saberdramon, at=(-450, 450), range=0, autotalk=True, when=not recruited(Species.Saberdramon))
report_heard = flag()

@lookout.on_talk(when=not report_heard, scene=True)
def the_report():
    say("...Yes. The human has come to the Seam. Small. With a Digimon.", "He walks where the ground does not match.")
    wait(1000)
    say("...As you say. I will keep watching.")
    tamer.say("Who's it talking to? There's nobody here...")
    face(tamer)
    say("!")
    report_heard.set()
    sound(8, 13)
    wait(1000)
    leave()

@lookout.on_talk
def gone():
    leave()
