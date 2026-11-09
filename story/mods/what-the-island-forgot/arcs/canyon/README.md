# Canyon

Breaking the Motor is the one choice that stays: the sinking canyon, the fallen nest and the stone crossing are its
visible consequence. Everything else converges. Until the Motor is broken, the fortress elevator (48) offers the way down
every time: if the chase was given up, the band and the notebook are still there; if the Motor was left, its choice is
asked again on arriving in the Engine Room. The bridge rumour and elevator routes still work on every branch; the two
Gabumon who leave Ogremon's cave scene with R1 are extras of that scene, with no recruit or item attached.

After the Ogre Fortress chase, leaving the Motor intact keeps Shellmon's original
route open. The tamer adds one short reminder, in all eight languages, that the
fortress's other lift still reaches the canyon top. The chase cable belongs to
the Shaft route; it does not disable that other lift.

Leave through the tunnel, Rift and Descent to screen 42, then return through
41, 40 and fortress rooms 45–48. On room 48's step tile 0, the base ride-up menu
still follows the mod's handler. Ride to 37 (section 53), hear Shellmon's plea on
bridge 39, and use 37's lift back to the fortress (section 54). Leave on foot,
ride the lower canyon lift up to 38 and return through 43 and 37 to Shellmon on
127. The Motor's destruction choice is offered only after hearing Shellmon's plea
on bridge 39 (`shellmon_plea_heard`, original saved flag 182). Visiting the Engine
Room first leaves the Motor intact and still settles the chase, preserving the
notebook and tunnel route. After hearing the plea, return by the mended cable;
the Engine Room offers the choice again. Breaking the Motor then recruits
Shellmon with the shared join announcement. Declining still permits the original
rescue or a later change of mind. No new save allocation is needed: existing
plea/recruitment flags and `save.lock` retain their meanings, and already broken
Motor/recruited saves are left intact. This is script-only, with no main-executable
or heap growth. Run the offline regression with:

```sh
python3 -m unittest discover -s story/mods/what-the-island-forgot/test -p test_shellmon.py
```

While CHASING, returning by the Shaft lift and choosing
"Not down there" also falls through to the base menu.

These routes were exercised on an origin/main English disc at the original
2 MB limit before adding the reminder. No route logic or existing dialogue was
changed.
Breaking the Motor leaves the nest fallen on screen 366, including after Birdramon
joins. Until recruited, Birdramon waits at Great Canyon Bridge (39), even on old
saves with `birdramon_gone` set. Losing leaves it there for another attempt.
Winning keeps its anger in the dialogue but recruits species 21 with the usual
extended join announcement and two prosperity points. The player arrives in the
same File City layout selected by the original nest recruitment (script 124,
section 51), testing the updated prosperity against 50 as well as Angemon,
Monzaemon, Vegiemon and Palmon. Birdra Transport and Birdramon's summit rescue
use the normal recruit flag. The legacy departure bit remains allocated in
`save.lock`.

The departure uses the wing sound and removes the actor without movement:
Birdramon's postbattle `walk_away` can hang the scene. No run clip is required.

After an English smoke build, run the real-battle regression on original 2 MB RAM:

```sh
python3 tools/dev/playtest/birdramon_recruitment.py build/dev-everything.cue \
  --exe build/dev-everything/exe/SLUS_010.32 --port 42139
```

It checks the join announcement, the prosperity-50 city arrival, a paid flight,
the fallen nest, Birdramon's summit rescue without Airdramon or Angemon, a legacy
departure flag, and Birdramon waiting after a loss. It seeds battle HP and saved
flags; the game executes the actual fights, rewards and route handlers.

Once Monochromon has moved to File City, his cousin Tuskmon keeps the Monochrome Shop (49) open
(`monochrome-shop.py`): never before the recruit, never a recruit himself. Talked to across the counter, he
runs a normal shop for canyon travellers and a deal of the day: one item worth 2000 bits (Large MP,
Omnipotent, Health Shoe or Digicatfish) at 2500. Two haggles at most (60 %, then 40 %) bring it to 2150 and
1800; a lost haggle angers him and closes the deal until the next day. The lowest price stays above the
1000 the item sells for. A full bag or too few bits take nothing.
