# File City's lower town (script 163, screens 180-203), the gate in the hedge to the Works (maps/twnb-gate.py, step
# trigger 7): Golemon, who builds the district, opens it once it has joined the city (beaten at the Grey Lord's
# Mansion's door); before that someone is building behind the hedge and the gate is shut (design/city-recruits.md).
from dw import *
from dw.base.file_city_180 import city_180

@city_180.on_step(7, when=recruited(Species.Golemon))
def to_the_works():
    warp(357, entry=0)

@city_180.on_step(7, when=not recruited(Species.Golemon))
def still_building():
    tamer.say("Hm? Somebody's building something behind the hedge...", "The gate's shut. Maybe later.")
    tamer.walk(-850, -2550)
