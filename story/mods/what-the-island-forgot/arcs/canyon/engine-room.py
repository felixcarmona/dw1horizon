# 300, the Engine Room under the Ogre Fortress (§3.2, §5.2): what is left of Ogremon's band guards the pit he fled by.
# Beaten, they run; on the crate by the fire is Analogman's first notebook (M5), which only the tamer can read; then the
# one-time choice: break the Motor (R1: the canyon sinks, Shellmon's rock lets go of him) or leave it.
from dw import *
from dw.names import *
from ...state import Canyon, root1, memories, m5_notebook, memory_news

room = new_screen(300, map="build/what-the-island-forgot-maps/screens/ENGN01.MAP")
lookout = room.npc(Species.Agumon, at=(150, -900), range=0, when=Canyon.CHASING)
guard = room.npc(Species.Agumon, at=(800, -1000), range=0, when=Canyon.CHASING)

@room.on_enter
def enter():
    music(6)

@lookout.on_talk(scene=True)
def lookout_talk():
    band()

@guard.on_talk(scene=True)
def guard_talk():
    band()

def band():
    tamer.face(lookout)
    lookout.face(tamer)
    guard.face(tamer)
    lookout.say("It's that kid again! Boss said nobody comes down here!")
    tamer.say("Where's Ogremon?")
    guard.say("Gone! Out the old tunnel, to the sea. And we ain't movin'.")
    if fight(lookout, guard, escape=False) != "won":
        return                    # a lost battle wakes the tamer in Jijimon's house: the band waits here still
    lookout.say("Eeek! Same as upstairs!")
    guard.say("Boss found this place, y'know. Said it was already here when he came!")
    lookout.run(2300, 150, wait=False)
    guard.run(2300, 150, wait=False)
    lookout.arrived()
    guard.arrived()
    lookout.leave()
    guard.leave()
    the_motor()

def the_motor():
    tamer.walk(450, -650, camera=True)
    tamer.turn(2048)
    tamer.say("Hm? There's a notebook on the crate.", "Whoa... It's written in my kind of writing. Human writing.")
    tamer.say("\"Year 9 below. The lift holds the north plateau.\"",
              "\"Rock-types take to it on their own. Let them.\"")
    m5_notebook.set()
    memories.add(1)
    memory_news.set()
    tamer.say("Somebody like me wrote this. Down here, a long time ago...")
    sound(8, 9)
    wait(1000)
    tamer.say("This machine's still running. It's what pushes the ground up!", "The whole canyon's sitting on top of it.")
    if ask(yes="Break the Motor", no="Leave it"):
        tamer.say("{partner}! The shaft! Pull it loose!")
        sound(8, 9)
        fade_to_white(1500)
        wait(1000)
        root1.set()
        invisible_bridge_rumor_heard.set()   # the bridge is stone now: the canyon entrance's step scripts let anyone across
        invisible_bridge_crossed.set()
        if not recruited(Species.Shellmon):
            recruit(Species.Shellmon, prosperity=2)
        fade_from_white(1500)
        narrator.say("With a scream of metal, the Motor stops.", "Far above, the ground groans and begins to settle.")
        tamer.say("Whoa... It's so quiet.", "The way we came is caved in. We'll have to go out through the tunnel.")
    else:
        tamer.say("Better leave it alone. Who knows what'd happen up there.")
        tamer.say("The fortress's other lift still goes up to the canyon top.")
    advance(Canyon.SETTLED)
    # Keep the gear in view during the scene, then replace the camera walk's retained follow offset.
    camera.on(tamer, speed=10)
    camera.arrived()
