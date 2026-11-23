# postgame

The post-game's Machinedramon stations (the fortress room 47, the mansion basement 66, the ice hall 104) and the Back
Dimension portal stay as in the original on every branch: a broken root changes the land above, not the curse. `arcs/summit/old-saves.py`
restores the portal on 0.0.2 saves that lost it. The shared story source gives the second BlueMeramon in screen 227 its
missing battle in both story modes.

`blackwargreymon.py` adds the one fight above the final one: after the ending, when Digitamamon has left the summit (screen 225) for the
city, BlackWarGreymon stands where Machinedramon fell. It is optional, recruits nobody and gates nothing. The first win gives one
Offense chip and one Defense chip; later wins give nothing, and it never pays bits (a fight that can be repeated is not a source of
money). Its sheet (11000 HP, 1100 Offense, 900 Defense before the difficulty factors; 19250 HP and 1375 Offense on NORMAL) and its
moves (`content/battle/enemy-movesets.json`, with its finisher Terra Destroyer one choice in seven) were set from live fights:
`tools/dev/playtest/hard_battles.py ... --cases boss --boss-screen 225 --boss-slot 4 --boss-triggers 256`.
