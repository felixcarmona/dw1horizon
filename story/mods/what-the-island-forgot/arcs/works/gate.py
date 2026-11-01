# File City's lower town (script 163, screens 180-203), the gate in the hedge to the Works (maps/twnb-gate.py, step
# trigger 7): Digmon, who builds the district, opens it once it has joined the city (beaten in the Drill Tunnel,
# arcs/residents/digmon.py); before that someone is digging behind the hedge and the gate is shut. Trigger 308 was Golemon's
# recruit flag, when Golemon built the Works: a save that has it keeps the gate open.
from dw import *
from dw.base.file_city_180 import city_180

@city_180.on_step(7, when=recruited(Species.Digmon) or trigger(308))
def to_the_works():
    warp(357, entry=0)

@city_180.on_step(7, when=not recruited(Species.Digmon) and not trigger(308))
def still_building():
    tamer.say("Hm? Somebody used to dig behind the hedge... There's only rubble now.", "The gate's shut. Maybe a real builder could open it.")
    tamer.walk(-850, -2550)
