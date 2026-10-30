# 303, the Descent: the ledge inside the crack, from the Rift's ramp up to the Great Canyon Bottom Area. The canyon's music.
# The steps up are step trigger 0 (maps/descent.py): to 42, or to 368 (the crack open) once the Motor is broken (R1).
from dw import *
from ...state import root1

descent = new_screen(303, map="build/what-the-island-forgot-maps/screens/DESC01.MAP")

@descent.on_enter
def enter():
    music(6)

@descent.on_step(0, when=root1)
def up_through_the_crack():
    warp(368, entry=1)

@descent.on_step(0, when=not root1)
def up_the_steps():
    warp(Screen.great_canyon_bot_area_42, entry=1)
