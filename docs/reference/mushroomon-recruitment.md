# Mushroomon: the three Spore Area screens

Mushroomon belongs in Mt. Panorama Spore Area **234** (MIHA06), on the left
side of the lower clearing, below the UFO. From northern Native Forest the
route is **109 → 111 → 18 → 233 → 234**. In the first Spore Area (233), take
the lower exit; the upper path goes to Plains instead.

The northern route requires the forest rockslide to have been cleared through
Drill Tunnel. The first Meramon scene in Lava Cave 31 sets
`native_forest_rockslide_cleared` (T106), before its battle. The gate is normal
story progress, not a missing flag: the Native Forest 109 step handler then
selects 111 instead of the blocked 110 variant. Drill Tunnel's excavation,
boulder and Meramon events are authored in `story/base/zones`; no item is
consumed to open the forest road. The canyon route provides another way around
the mountain after hearing Yuramon's invisible-bridge rumour at prosperity six
and actually crossing that bridge. The recruit itself has no clock or item gate.

Talk to Mushroomon and win its 1200 HP fight. It joins the Clinic medicine
shop. Its existing recruitment bit is retained; already recruited saves do not
spawn another Mushroomon. Existing saves with it still missing can use the new
placement without starting over.

## Cause and source inventory

Before this fix, including v0.0.7, the scene targeted **21** (MIHA03). This is
an unused original variant with exits out and **no incoming walking edge**.
The actual MIHA00 exit goes to 233; Plains exits go to 233/234. All three
variants have the same Spore Area caption. Waiting, collecting an item or
completing the story never supplies a walking entrance to 21.

| Source | Statement or role |
| --- | --- |
| `story/mods/what-the-island-forgot/arcs/residents/mushroomon.py` | Authoritative screen, coordinates, unrecruited-only presence, dialogue and battle. Previously 21; now 234. |
| `story/mods/what-the-island-forgot/arcs/residents/README.md` | Scene inventory; corrected to 234. |
| `story/mods/what-the-island-forgot/city/centar-clinic.py` | Recruited Mushroomon runs the medicine shop on 213. |
| `tools/derive/recipes/everything.json` | Includes the resident scene in the disc. |
| `content/species/263-mushroomon.json` | Species/model and partner data; does not choose the recruitment screen. |
| `tools/guide/recruits.json` | Previously advertised 21, “Talk and win the fight”, “Any time”. Now supplies the route and source-checked placement variants. |
| `web/i18n/*.json` | Nine localized recruitment instructions; now explain the route, normal progression and older versions' inaccessible placement. |
| `tools/guide/out/` | Historical generated standalone guide; not the deployed wiki or an authoring source. Regenerate from a chosen snapshot when needed. |
| `tools/wiki/build.py` | Recruitment section of the wiki's Mushroomon article and recruit directory uses the same reviewed annotations. There is no separate Mushroomon paragraph in the general article catalogs. |
| `docs/reference/world.md`, `tools/data/world-dispatch.json` | Original targets and actually dispatched exits, distinguished from unused arrival slots. |
| `story/base/maphead/hooks.py`, `story/base/zones/mt-panorama-spore-area/` | Original setup and story scenes on all three variants. None changes a normal arrival into 21. |

The guide now selects its placement and translated explanation against the
**selected game's source**. A v0.0.7 wiki build explains that the encounter is
unreachable and needs an updated game; it does not advertise the repaired route
as if it existed on that disc. A working/fixed build shows 234 and the route.

## Console constraints and checks

Screen 233 was rejected as a replacement: Unimon, Starmon and Mushroomon would
need 193 KB against 192 KB available. Screen 234 retains its Vademon scene and
places Mushroomon at (-450, -900), below the UFO trigger strip and away from
all three chest footprints. The compiler checks the simultaneous model loads.
This is a story-data change with no C or resident executable additions, so no
engine patch is needed in `mods/patches/series`.

`tools/test_world_audit.py` checks the orphaned original variant, the actual
scene's walking route and its talking approach from both arrivals with chest
collision present. The guide and wiki tests distinguish old and fixed sources
in all nine languages. The world audit can additionally compare against built
maps. `tools/dev/playtest/mushroomon_walk.py` reuses the recorded-walk driver with
clock/stat writes and partner repositioning disabled and requires exactly 2 MB
RAM. It can boot a fresh game or load an exact-disc `--checkpoint`. For the
short route check, `--prepare-rockslide` sets only T106 before walking; the
checkpoint may contain stat boosts applied through the normal Cheats menu.
The driver captures each visited screen and logs the walking coordinates.
`tools/dev/playtest/mushroomon_recruitment.py` attaches at the talking approach
on 234, checks the unrecruited actor has 1200 HP, and records the conversation,
real fight, join message and return to field control. It only reads RAM and
presses the pad. Both drivers write screenshots and structured evidence to
their output directory.

The English PCSX-Redux check on original 2 MB RAM completed the pad route
109 → 111 → 18 → 233 → 234, talked to Mushroomon, won its unmodified 1200 HP
fight, displayed “Mushroomon joined the city!” and returned field control with
the saved recruitment bit set. T106 was prepared as a fixture; partner stat
boosts used the normal Cheats menu. The dirt-hauling quest was not replayed.
No tamer/partner positions, NPC state, fight outcome or recruitment bit were
written by the test. Physical hardware and other runtime languages were not
checked in this run.
