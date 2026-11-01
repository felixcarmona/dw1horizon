# 236/237, File City, the farewell (§3.11, §4). With the key chain given away (4.3) the door home has been used: there
# is no ceremony, the tamer stays, and the game's own farewell does not run after this one. With the three roots
# broken and the key kept, the island goes back to its old size (4.2), or, if too little of it is remembered, nobody
# can say why (4.1b). With one or two roots broken, Jijimon tells what changed, then the game's own farewell (4.1).
from dw import *
from dw.text import text
from dw.base.file_city_236 import city_236, jijimon, greymon, airdramon
from ...state import root1, root2, root3, memories, key_given

t51 = text.s192.sec51

@city_236.section(51, when=key_given)
def a_different_ceremony():
    call(Routine.load_ending)
    jijimon.face(tamer)
    greymon.face(tamer)
    airdramon.face(tamer)
    partner.walk(-340, -2263, wait=False)
    camera.to(172, -1848, speed=2)
    camera.arrived()
    jijimon.say(t51.u0)
    tamer.say("Jijimon... I gave my key chain away. To him.")
    jijimon.say("Then the door has been used, my boy.", "There is no ceremony I can do for you now.")
    narrator.say(page("{color 7}Tokomon {color 1}", "You're... staying?"))
    tamer.say("My mom'll be worried. I know...", "But somebody needed that door more than I did.")
    jijimon.say("Mm, mm. Then let's begin a different ceremony.", "A house. Right here, in the city.")
    tamer.turn(0)
    tamer.turn(1024)
    tamer.turn(2048)
    tamer.turn(3072)
    tamer.say("Everyone, I had a really great time. ...And it's not over.")
    hide_hud()
    call(Routine.game_clear_save)
    tamer.face(partner)
    partner.face(tamer)
    tamer.say(t51.u7)
    hide_hud()
    jijimon.play(32)
    call(Routine.start_ending)
    dws("return;")                # the game's own farewell (the ceremony home) must not run after this one

@city_236.section(51, when=root1 and root2 and root3 and not key_given)
def the_island_as_it_was():
    if memories >= 6:
        jijimon.say("The canyon is sinking, the ice is going, the old mansion has fallen in...",
                    "It's smaller. It's ours.")
    else:
        jijimon.say("The canyon, the ice, the mansion... all going back to how they were.",
                    "I feel... nothing coming. Is that good? I can't say why.")

@city_236.section(51, when=not (root1 and root2 and root3))
def what_changed():
    if root1:
        jijimon.say("They say the ground in the canyon has stopped sinking.")
    if root2:
        jijimon.say("And the Grey Lord's doors stand open now.")
    if root3:
        jijimon.say("And Mr. M says Freezeland is thawing at the edges.")
