# Iron Hills route

Iron Hills is a linear pass between Leomon's post in Gear Savanna and the Seam.
There is no intended self-loop. Each screen has two exits, with reciprocal entry
numbers on its neighbours.

| Screen | Map | Exit 0 leads to | Exit 1 leads to |
|---|---|---|---|
| 317 | IRON01 | Gear Savanna 78, entry 1 | Iron Hills 318, entry 0 |
| 318 | IRON02 | Iron Hills 317, entry 1 | Iron Hills 319, entry 0 |
| 319 | IRON03 | Iron Hills 318, entry 1 | Iron Hills 320, entry 0 |
| 320 | IRON04 | Iron Hills 319, entry 1 | Iron Hills 321, entry 0 |
| 321 | IRON05 | Iron Hills 320, entry 1 | The Brink 322, entry 0 |
| 322 | IRON06 | Iron Hills 321, entry 1 | The Seam 323, entry 0 |

On screens 317–320, exit 0 is at the bottom and exit 1 is at the top. Screen 321
reverses that orientation: exit 0 is at the top and exit 1 is at the bottom. The
Brink returns through the northwest and continues east into the Seam.

Screens 317 and 318 both show a large upright gear on the right. Screen 318 has a
round clearing and the area's toilet; screen 317 has the pipe stack. Screen 320
has a fallen gear on its ridge. All use the Iron Hills caption and the same wild
species, so the scenery alone can make a transition resemble a loop. Screen 319
is the distinct zigzag ramp between the hollow and the ridge.

The southern exit of 317 is a story step handler rather than an ordinary warp
when the road gate is active. It returns to screen 78 after the forest rockslide
or invisible bridge has been cleared. Otherwise its dialogue sends the tamer
back into the pass; that progression gate is intentional.

The map recipes are in `story/mods/what-the-island-forgot/maps/iron-hills-*.py`
and `the-brink.py`; the gate is in `arcs/seam/iron-hills-gate.py`.

The November 2026 route audit walked all twelve exits on a full build of
`c5b95434`, in the original 2 MB emulator configuration at night. Each check
started at the exit's real arrival, walked through its trigger with the pad,
and required the destination above plus field control after the transition.
All twelve passed, including the southern story gate with the road open. No
self-loop, wrong destination or immediate arrival bounce was reproduced.
