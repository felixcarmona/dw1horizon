# Canyon

After the Ogre Fortress chase, leaving the Motor intact keeps Shellmon's original
route open. The tamer adds one short reminder, in all eight languages, that the
fortress's other lift still reaches the canyon top. The chase cable belongs to
the Shaft route; it does not disable that other lift.

Leave through the tunnel, Rift and Descent to screen 42, then return through
41, 40 and fortress rooms 45–48. On room 48's step tile 0, the base ride-up menu
still follows the mod's handler. Ride to 37 (section 53), hear Shellmon's plea on
bridge 39, and use 37's lift back to the fortress (section 54). Leave on foot,
ride the lower canyon lift up to 38 and return through 43 and 37 to Shellmon on
127. Breaking the Motor recruits Shellmon immediately instead, with the shared
join announcement. While CHASING, returning by the Shaft lift and choosing
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
