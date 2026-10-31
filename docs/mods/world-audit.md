# World reachability audit

Run from the repository root:

```sh
python3 tools/world_audit.py
python3 tools/world_audit.py --built-maps build/NAME-maps --out build/world-audit-built
python3 tools/test_world_audit.py
```

The first command needs only committed files. The second additionally checks the
physical edges against the player's original extraction and the map recipes'
actual output. Both write `ORIGINAL.json`, `HORIZON.json`, `conditions.json`,
`findings.json`, `arc-findings.json`, `baseline-drift.json` and `unresolved.json`
below the output directory. A finding names
the story frontier, original screen and exact directed path, with source evidence
and conditions on each edge. One-way exits stay one-way. Cheats are excluded.

## Inputs and interpretation

- Original exit targets come from the screen table in
  [world.md](../reference/world.md). `tools/data/world-dispatch.json` records which
  exit slots have trigger tiles; unused spawn/arrival slots are not walking
  connections. It also records step/use dispatch numbers. No map bytes or game
  dialogue are stored there.
- Original scripts come from `story/base`, including the captionless Mt. Infinity
  library scripts. MAPHEAD associates scripts with their screen variants and its
  conditions are included in the inventory. The source walker retains `when`,
  branches, early returns, helper calls, cross-script section jumps, choices and
  flag writes before warps.
  Birdramon's six C destinations, unlocks and fares are included explicitly;
  MAPHEAD's Auto Pilot dispatcher is a conditional return from any screen.
- Horizon adds the mod's screens, map data, recipe overrides, early-game scripts,
  arcs and district/city scripts. The Wall of Hearts recipe's return to room 97
  overrides the old target 104 in its authoring JSON. Ferry availability includes
  the dock's earlier cooldown hooks; `ferry_elapsed_days` denotes the dated
  countdown helper's result, not a new game flag.
- `tools/data/world-gates.json` records reviewed physical gates, their evidence
  and story frontiers. These include NPC/door/trigger-strip barriers that cannot
  be inferred merely from a warp instruction. An unknown predicate keeps both
  possibilities; it never silently closes a route. A `fresh` frontier initializes
  original named flags and recruitment predicates to false before applying its
  explicit state. The bridge frontier includes the preceding jungle crossing.
- Reachability retains separate arrivals into a screen. `arrival_entry` is the
  graph's current arrival slot, not a game variable. The reviewed Devimon and
  MetalGreymon strips distinguish the near and far arrivals, so adding a warp
  beyond a mandatory fight cannot hide behind an earlier visit to that screen.

The audit compares sets of reachable screens in each recorded frontier. These are
story-state snapshots, not a solver for complete playthroughs, battles, clocks or
inventory acquisition. Literal DWS jumps are conservative edges with source
evidence; their physical area gates are reviewed separately. Internal flag changes
without a warp and NPC movement need gameplay review. Use the emitted conditions
and paths to examine a finding, and validate changed connections in the emulator.
Do not describe a passing frontier suite as a proof of every possible save state.

`tools/data/world-baseline.json` freezes the original reachable sets. The check
also fails if that baseline drifts, so changing an original gate cannot silently
make a new bypass appear acceptable. Baseline changes require an explicit review
of the original sources and the relevant frontier.

The physical-output comparison must have no unmodeled or absent edges before
accepting an audit. It catches recipe overrides and naming mismatches that a JSON
scan alone misses. If topology, dispatch or a physical gate changes, review its
source and the affected original baseline instead of simply accepting new output.

## Gates on the new connections

| Connection | Entry condition | Unrestricted retreat |
|---|---|---|
| Drain 356 → Sewer 220 | Whamon recruited (T224), or town reopened (T328) | 356 → 355; 220 → 356 |
| Rubbish Mouth 353 → Trash Mountain 165 | Forest rockslide cleared (T106), or invisible bridge crossed (T103) | 353 → 352; 165 → 353 |
| Iron Hills 317 → Gear Savanna 78 | T106 or T103 | 317 → 318; 78 → 317 |
| Overdell Pass 335 → Overdell 34 | Jungle crossing/repaired bridge (T186/T185), invisible bridge (T103), or the original postgame mansion portal | 335 → 334; 34 → 335 |

T103 records crossing the original bridge after hearing T124. Hearing the rumour
alone does not establish that the player has reached the jungle side of it.

There is one legacy escape in the last gate: a player already inside the Seam
with neither original northern road opened may leave through Overdell. Corrected
fresh games cannot enter the Seam with both northern and southern access closed.
Without this escape, old sequence-broken saves could be enclosed between the two
Seam gates. The graph checks fresh reachability and starts escape tests inside
every Seam screen, with all road flags unset. No new saved state is needed.

Exit trigger tiles become step trigger 0 on these four screens. The scripts own
the checks, translated block lines and movement away from the trigger, so standing
on it cannot reopen the same dialogue every frame. Arrival coordinates, reciprocal
exits, art, wild placements and battle stats are retained. If an authoring recipe
regenerates these layouts, retain this conversion; the source tests reject an
unconditional exit returning in its place.

## Deliberate differences and regression checks

`tools/data/world-allowlist.json` contains narrowly scoped frontier/screen pairs,
each with a reason. The existing R3 white-barrier removal is deliberate: completing
R3 already requires Angemon and prior Sanctuary access, then permits re-entry with
another partner attribute. Original routes around a gate belong in the original
graph, not in the Horizon allowlist. In particular, the northern route into the
canyon after the rockslide and the walk around Megadramon's optional fight remain
available.

One existing arc timing question remains explicit in the allowlist: the postgame
hall 104 gateway can visit the empty Vault before Angemon joins, although the
decision NPC and R3 progression remain closed. Restricting that visit needs an
owner decision and a retreat plan for old saves in hall 104. The audit records
the exception with `decision_needed`, rather than changing that connection.

The tests insert unsafe sewer, northern and summit edges and require the audit to
reject them. They also exercise both original road unlocks, old saves on either
side, arc prerequisites, ferry cooldowns and the Vault recipe override. The audit
and its tests run in `tools/selftest.sh`.

## Integration with the arrival fixes

The gated Rubbish Mouth and Drain exits retain the narrower exit regions and
inward-facing arrival rotations from the Galleries arrival fix. Convert only
the remaining gated exit tiles (111) to step trigger 0 (51); keep the cleared
floor tiles free. Spanish block lines use Sabana Gear and Selva Tropical,
matching the shared area-name bank.
