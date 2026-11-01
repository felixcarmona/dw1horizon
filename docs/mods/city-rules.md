# City rules and NPC presence

Use [Python story handlers](story-language.md) for new quests, NPCs and presence
conditions. This page describes the declarative city data read by the tier-2
engine and the tools that explain the base game's city rules.

## City data

`story/base/city/city.dws` expresses the original C rules for prosperity,
File City layout, revival screens, new-game state, and shop/arena overlay lists.
`tools/dws/city.py` extracts and compiles these declarations. A `city { }` block
is a DWS escape hatch for changing those rules; it requires a compatible tier-2
target. The original executable and `ENGINE_TIER=0` retain their C rules.

The compiled table uses little-endian u16 words, a `CY` header, a version and
six block offsets. Conditions are clauses of four-byte atoms. MAPHEAD section
1260 holds a mod's table; the engine uses its built-in default when no replacement
is present. The default header is generated from the base declaration.

This data shares the target's resident MAPHEAD buffer. Current mod targets allow
0x8000 bytes; the original executable allows 25,000. The compiler checks capacity.
Historical heap measurements from a different patch series do not establish that
a changed city fits; validate the actual final build at the original 2 MB.

## Residents and prosperity

`content/tables/city-residents.json` owns the City page's species IDs and hidden
flags. Species must be defined IDs below 1024 and Rookie or higher. A resident above ID 58 is one
of a kind: the only one of its species on the island, with its own recruit site
(`arcs/residents/README.md`). Myotismon and WaruMonzaemon are the two story
exceptions, and `tools/test_city_residents.py` enforces the rule. The current
roster has 18 Rookies, 34 Champions and 20 Ultimates, worth 143 points. The 50 IDs
below 59 are worth 100 points. Baby flags are deliberately excluded: several
represent story state, including the city medal.

`tools.city_residents` decodes SET_TRIGGER instructions in every compiled
DG.SCN and MAPHEAD.SCN produced by the story derive passes, including base,
mods, languages and font variants. The build checks each pass separately after cache restores too: extended passes
must match the roster exactly; original passes must match its IDs below 59.
Otamamon (species 109, trigger 309) records the Geko Swamp victory for Misty Trees; it is
excluded from the resident check, City page and prosperity. Its raw story recruit
write remains intact. Legacy original-story writes above 58 do not make residents.
Patch 0304 supports imported residents. IDs 0..111
keep trigger 200+id; IDs 112..1023 use existing saved recruit bits, addressed by
`SET_TRIGGER`, `UNSET_TRIGGER` and `IF trigger` operands 0x8000+id. Ordinary
triggers 312+ retain their meanings. `recruit`, `unrecruit`, `recruited`,
`send_to_city(species=...)`, automatic join announcements and NPC
`when=recruited(Species.X)` share that mapping on patched targets. The original
engine still rejects high IDs. The gate decodes both operand ranges, refuses
unlisted recruits and missing residents, and rejects roster prosperity above 255.
Run `python3 -m tools.city_residents PATH/TO/DG.SCN ...` for a standalone check.
The same gate is in `tools/selftest.sh` when compiled stories are available.

`recalculateProsperity` rebuilds pstat 1 independently of tournament cleanup.
It runs before the City page is shown; saves and game start still call
`recalculatePPandArena`, which calls it before its arena work. Original story
counts only IDs 3..58; extended story counts only roster members. The balance
build generates the executable’s 14-byte membership bitset for IDs below 112.
Before native compilation, `tools.city_residents --c-extra-header TREE` generates
`src/main/city_residents_extra.h` with an exact-sized u16 list of roster IDs
112 and above. The build driver and native cache regenerate it before hashing
compiler inputs. The current roster's 20 high IDs take 40 bytes of list data,
plus the loop's code. There is
no per-frame scan of all 1024 species. Flags left in older saves cannot add
unlisted residents. The City tab already reads u16 IDs from DIGI.DAT and calls
`isDigimonRecruited`, so it needs no change. Continue applies the
story option before game start recalculates. `city.dws` continues to describe
the original rule, which `city-verify` compares against the unmodified C.
Wild recruit scripts do not add points immediately, and some scripted recruits
add more than their level weight. Opening City therefore shows what the next
save would write, so Jijimon and city layout read the same pstat.

The base story awards the Thriving City medal at any prosperity of at least
100. Seven wild recruitment sites now set the species present in the balanced
`content/maps` slot; nine other explicit joins already matched their slots.
These are reviewed authored base changes, pinned in `story/base/authored.json`;
the original-disc generator remains unchanged.

## Presence

NPC presence comes from MAPHEAD setup, rather than the city C table.
`tools/dws/presence.py` follows setup branches and derives conditions for each
screen, slot, species and autotalk value. The key-only declarations live under
`story/base/city/presence/`.

For new NPCs, the Python compiler combines presence conditions with the slots it
places. Use `screen(...).npc(..., when=...)` and guarded handlers. A change to an
existing NPC should use the supported base imports and ownership operations;
do not copy and hand-edit MAPHEAD assembly.

## Inspect and verify

Run from the repository root with the decompilation and player's USA extraction
available:

```sh
python3 tools/dws.py city-verify
python3 tools/dws.py why Angemon --screen 205 --recruit Angemon
python3 tools/dws.py why top_map --recruit Angemon --recruit Monzaemon
```

`city-verify` compares declarations with the original rules and checks presence
conditions over its state grid. `city-extract` regenerates base declarations from
the unmodified C and scripts; review the diff before committing regenerated source.
`city-compile --help` describes standalone table/header outputs for compiler work.
The integrated builder generates the required executable inputs automatically.

After changing a city rule or NPC, run the compiler checks and the affected
runtime scenarios. Check map selection, prosperity, NPC slots, transitions,
new-game state and save/continue where applicable. See
[development checks](../developing.md) and [memory budgets](../reference/memory.md).

Wild recruitment in the extended story requires a won battle and an unset recruit
flag. It then sets the flag, plays the join jingle and announces the species by
name, without moving or addressing the defeated entity. Repeated wins, fleeing
and losing do nothing. Silent bare recruits receive the same announcement;
existing join narration and departures keep their own scene. Reward and ending
narration alone do not hide a recruitment.

ModokiBetamon, Dokunemon, Vermilimon, IceDevimon, DarkLizardmon and Gururumon
are ordinary wild enemies. DarkLizardmon still keeps the Kennel and Gururumon
still hunt. They have no City page entry and never contribute prosperity. The
100-point prosperity medal remains reachable (the roster totals 143).
