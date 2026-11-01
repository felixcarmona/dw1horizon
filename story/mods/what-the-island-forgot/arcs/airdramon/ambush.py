# File City, Airdramon's ambush (script 162, step trigger 6, §3.9): the game's own scene, by its keys, with Jijimon's
# shout before the battle and the one-time choice. "Hold back": a battle of 90 seconds (the engine's time limit, patch
# 0172) in which the partner must last without beating him; spared, the game's own end (Airdramon is carried to
# Jijimon's house and healed: AIR). Beaten, or "No choice: fight!": Airdramon fights "even if it costs my life", falls,
# and is still breathing: the same end, with one line more. The game's own ambush does not run after this one.
from dw import *
from dw.text import text
from dw.names import *
from dw.base.file_city_168 import city_168

slot5 = entity(10)                # slot 5: the script spawns Airdramon there
t57 = text.s162.sec57
holding_back = flag()

@city_168.on_step(6, when=mt_infinity_entrance_found and not airdramon_ambush_fought)
def the_ambush():
    mt_infinity_entrance_found.clear()
    load(Species.Airdramon131)
    spawn(Species.Airdramon131, slot=5)
    tamer.face(slot5)
    partner.face(slot5)
    slot5.face(tamer)
    wait(1000)
    camera.on(slot5, speed=20)
    camera.arrived()
    raw.entity_move_to(slot5, 2084, -211, 30, 0)
    camera.on(tamer, speed=20)
    wait(1000)
    tamer.play(17)
    partner.play(40)
    damage_percent.set(10)
    raw.deal_damage(damage_percent)
    wait(750)
    slot5.run(432, -2236, wait=False)
    camera.to(410, -1474, speed=2)
    camera.arrived()
    slot5.run(432, -2236)
    tamer.face(slot5)
    partner.face(slot5)
    slot5.face(tamer)
    wait(250)
    slot5.say(t57.u11)
    tamer.say(t57.u12)
    slot5.say(t57.u13)
    tamer.say(t57.u14)
    narrator.say(page("{color 7}Jijimon {color 1}", "Don't kill him! He's not himself!"))
    if ask(yes="Hold back", no="No choice: fight!"):
        holding_back.set()
        tamer.say("{partner}, don't finish him! Just hold on until he wears himself out!")
        pstat(242).set(90)                # patch 0172: the next battle's time limit in seconds (it ends with both standing)
    else:
        holding_back.clear()
    partner.run(50, -1950)
    partner.face(slot5)
    wait(250)
    fight(slot5, escape=False)            # a lost battle wakes the tamer in Jijimon's house: the ambush comes again
    tamer.face(slot5)
    slot5.face(tamer)
    partner.face(slot5)
    slot5.say(t57.u15)
    slot5.play(29)
    wait(1500)
    # held back and still standing when the time ran out: he is spared; beaten (held back or not), he falls
    if not holding_back or pstat(241) != 1:   # patch 0172: 1 when that battle ended by the time
        narrator.say("Airdramon fell to the ground, and did not move.")
        narrator.say(page("{color 7}Jijimon {color 1}", "...He's still breathing! Quick, my boy!"))
    tamer.play(7)
    wait(250)
    tamer.say(t57.u16)
    raw.entity_walk_to_entity(tamer, 1, slot5)
    raw.entity_walk_to_entity(partner, 1, slot5)
    wait(2000)
    airdramon_ambush_fought.set()
    trigger(355).set()
    mt_infinity_entrance_found.set()
    warp(Screen.jijimons_house_206, entry=1, then=60)
