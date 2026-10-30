# 143, the Secret Beach Cave (§3.1, §3.3): with the Motor broken (R1) Ogremon's band scattered at the Engine Room, so he
# comes to the New Ogre Fortress alone and calls WaruSeadramon himself. The game's own scene otherwise; afterwards the
# same surrender in 142.
from dw import *
from dw.text import text
from dw.names import *
from dw.base.secret_beach_cave_143 import cave, ogremon, gabumon1, gabumon2
from ...state import root1

slot3 = entity(8)                 # slot 3: the script spawns WaruSeadramon there
t51 = text.s137.sec51

@cave.on_enter(when=root1 and not new_ogre_fortress_cleared)
def no_band():
    gabumon1.leave()
    gabumon2.leave()

@cave.on_step(0, when=root1 and not new_ogre_fortress_cleared)
def alone():
    tamer.say(t51.u0)
    tamer.run(1104, 243, wait=False)
    partner.run(675, 290, wait=False)
    tamer.arrived()
    camera.to(1156, -416, speed=20)
    camera.arrived()
    tamer.face(ogremon)
    partner.face(ogremon)
    wait(250)
    ogremon.say(t51.u1)
    ogremon.face(tamer)
    ogremon.say(t51.u2)
    tamer.say("Ogremon! What are you up to now?!")
    ogremon.say("You again... You broke my canyon. My boys ran off.", "This cave's all I got left. Gweh!")
    tamer.say(t51.u8)
    ogremon.say(t51.u9)
    ogremon.say("WaruSeadramon, sir! Now!")
    spawn(Species.WaruSeadramon, slot=3)
    slot3.walk(586, -461)
    slot3.face(tamer)
    wait(250)
    tamer.say(t51.u12)
    tamer.say(t51.u14)
    ogremon.say(t51.u15)
    fight(ogremon, slot3, escape=False)
    tamer.face(ogremon)
    ogremon.face(tamer)
    partner.face(ogremon)
    ogremon.run(1100, 1000, wait=False)
    slot3.run(1100, 1000, wait=False)
    ogremon.say(t51.u16)
    ogremon.arrived()
    slot3.arrived()
    ogremon.leave()
    slot3.leave()
    tamer.say(t51.u18)
    new_ogre_fortress_cleared.set()
    tamer.run(1100, 1000, wait=False)
    wait(500)
    partner.run(1100, 1000, wait=False)
    warp(Screen.secret_beach_cave_142, entry=0, then=6)
