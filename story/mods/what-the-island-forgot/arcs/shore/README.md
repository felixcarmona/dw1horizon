# shore

Horizon story sources and authored resources for shore.

Whamon's five-day chase and ten-day recovery close the ferry before the old-shore
offer. `city-dock.py` and `sea-ambush.py` also remove him on entry to every File
City square layout (168-179) and Factorial Town's dock (152) while either wait is active. Presence
cannot compare the saved departure counters, so these entry handlers reuse
`elapsed_days()` and remove the appropriate dock's NPC after setup. Story
functions are local to one script, so the calendar regression also checks that
the two docks' copies of the calculation stay identical. The scratch
pstats (90-92) are overwritten before use; the calculation and removal must not
yield. Entry does not rewrite the departure date or change the step handlers'
order. Once the wait ends, the base setup leaves Whamon present again. If the
tamer stays on the city dock (including sleeping there), the return step instead
restores the removed instance from its already-loaded model before any Whamon
dialogue or the original ferry menu runs. All twelve square layouts use Whamon146
in slot 7, as recorded in their presence tables and the shared MAPHEAD setup.
The unsaved p120 records removal on this visit, including `after_him()`, and is
reset on every square arrival with a recorded wait. A normal reentry therefore
never spawns him twice.
It shares scratch storage with the hunter arrival witnesses on other screens;
no saved flag, model load or resident executable code is added. An undated
old save (`whamon_left_year == 0`) keeps the existing open-ferry fallback.
Factorial Town's use tile checks the same wait before its base dialogue and ferry
menu, using the existing closure lines while Whamon is absent.

Run the calendar and reentry regressions with
`python3 story/mods/what-the-island-forgot/test/test_story.py`.

For an English disc built with `python3 -m tools.dev build --lang en --jobs 8`,
run the original-2-MB emulator proof from a disposable corpus card:

```sh
xvfb-run -a python3 story/mods/what-the-island-forgot/test/playtest_whamon.py \
  --mode fixed --all-layouts --out build/whamon-fixed
```

Both timers are checked after an on-dock sleep and after leaving and returning.
Setup writes advance the earlier days; the final night uses the game's sleep
transition. The probe walks onto trigger 4, records paired paused screenshots,
and checks the original three-option ferry menu and return to control. Use
`--mode baseline` on an unfixed disc to record the absent Whamon and `?` speaker.
Ports default to 43167; `--port`, `--disc` and `--exe` select another instance/build.
