# author

Map authoring inputs and recipes for author in What the island forgot. Generated maps go under build/; the everything recipe controls their build order.

Contents:

- `bone-field-layout.py`
- `crypt-corridor-layout.py`
- `descent-1-layout.py`
- `descent-2-layout.py`
- `descent-3-layout.py`
- `descent-4-layout.py`
- `descent-5-layout.py`
- `descent-6-layout.py`
- `descent-layout.py`
- `district/`
- `drowned-shore-layout.py`
- `galleries/`
- `gallery.py`
- `infinity-engine-layout.py`
- `iron-hills-1-layout.py`
- `iron-hills-2-layout.py`
- `iron-hills-3-layout.py`
- `iron-hills-4-layout.py`
- `iron-hills-5-layout.py`
- `kennel-layout.py`
- `lake-terrace-layout.py`
- `lectern-room-layout.py`
- `mine-head-layout.py`
- `old-gallery-layout.py`
- `ossuary-layout.py`
- `passage-layout.py`
- `rift-layout.py`
- `root-clearing-layout.py`
- `seam-1-layout.py`
- `seam-2-layout.py`
- `seam-3-layout.py`
- `seam-4-layout.py`
- `seam-5-layout.py`
- `second-chamber-compose.py`
- `second-chamber-layout.py`
- `the-brink-layout.py`
- `wall-of-hearts-layout.py`
- `watchtower-layout.py`

Spawn safety is checked from compiler placements with `python3 tools/dws.py check-spawns`.
Use `--suggest` to print source-positioned diffs for review; it never writes a story file.
The derive recipe checks all sources after the maps exist, enforcing the original early-game scope
and reporting additional placements, unknown maps and skipped original-screen entries explicitly.
