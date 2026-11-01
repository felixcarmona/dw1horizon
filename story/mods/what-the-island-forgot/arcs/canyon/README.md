# Canyon

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
