# File City (script 162): what 0.0.2 could lose, recovered on the next arrival. Nothing sets these states now.
from dw import *
from dw.names import *
from dw.base.file_city_168 import city_168
from ...state import airdramon_killed

# Ending 4.4 (nobody came to the summit) skipped the reward tail of the game's own ending.
@city_168.on_enter(when=engine.game_beaten and not recruited(Species.Devimon))
def the_rewards_of_the_summit():
    recruit(Species.MetalGreymonVirus)
    recruit(Species.Devimon)
    engine.prosperity.add(7)

# The curse was cleared for good with the three roots broken (and 4.4 never set it): no portal and no Koromon from a station
# beaten is a state the game itself never reaches after its ending.
@city_168.on_enter(when=engine.game_beaten and back_dimension_portal == 0 and not recruited(Species.Koromon))
def the_curse_comes_back():
    raw.store_random(back_dimension_portal, 2)
    if back_dimension_portal == 0:
        back_dimension_portal.set(3)
    days_since_passed_out.set(0)

@city_168.on_enter(when=airdramon_killed)
def he_was_breathing():
    narrator.say(page("{color 7}Jijimon {color 1}", "That Airdramon was still breathing, my boy.", "He has been mending in my house."))
    airdramon_killed.clear()
    trigger(355).set()
    if engine.game_beaten:
        recruit(Species.Airdramon)

# The newspaper could still take Myotismon away after "Let him rest" (the base now tests myotismon_joined_city).
@city_168.on_enter(when=myotismon_joined_city and not recruited(Species.Myotismon))
def he_never_left():
    myotismon_missing.clear()
    recruit(Species.Myotismon)
