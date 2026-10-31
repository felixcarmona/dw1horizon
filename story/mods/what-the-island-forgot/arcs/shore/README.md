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
order. Once the wait ends, the base setup leaves Whamon present again. An undated
old save (`whamon_left_year == 0`) keeps the existing open-ferry fallback.
Factorial Town's use tile checks the same wait before its base dialogue and ferry
menu, using the existing closure lines while Whamon is absent.

Run the calendar and reentry regressions with
`python3 story/mods/what-the-island-forgot/test/test_story.py`.
