# What the island forgot

For new or changed screens, follow the [new-map checklist and complete recipe](../../../docs/mods/new-maps.md).

Horizon's story mod: the island's lost memory, three roots under the north-east lands, new places (screens 300 and up)
and new recruits for File City. Everything in this folder is ours; nothing of the game is in it. The maps are made from
the player's own extracted disc when the disc is built, with our art laid over the game's backgrounds or in place of
them.

    story/mods/what-the-island-forgot/build.sh          build/what-the-island-forgot.cue
    DEV=1 story/mods/what-the-island-forgot/build.sh    plus the playtest hook (Tokomon in Jijimon's house warps to the Engine Room)
    NAME=wtif ...                                       another disc name (the everything disc is built as wtif)

What is built, and in which order, is the recipe `tools/derive/recipes/everything.json` (its `story` sources and its
`maps`): a new story file or map recipe is added there.

| Folder | What it holds |
|---|---|
| `early-game.py`, `arcs/<arc>/*.py`, `district/`, `city/`, `state.py` | the story, in the Python story language (`docs/mods/story-language.md`): screens, characters, battles, choices, the flags the mod keeps (`mod.toml` `[save]`, numbers pinned in `save.lock`) |
| `text/` | the mod's lines in eight languages (`dws text sync` keeps the keys) |
| `screens/` | one screen file per new screen (id, map file, camera, music) |
| `maps/<screen>.py` | one recipe per map: a new screen (our art + our geometry on a structure read from a disc map with its own pixels cleared) or a retouch of an original screen (our cut-out pasted on the player's background, plus the map edits) |
| `maps/author/` | the authoring scripts that produced the layouts and composed pictures (`gallery.py` makes a Galleries screen from its description in `galleries/<name>.json`) |
| `art/` | our pictures at the screen's size: full new screens, and RGBA cut-outs for the retouches |
| `dev/` | the playtest hook of `DEV=1` |

Rules the maps follow:

- a retouch of an original screen is only our new element, as an RGBA cut-out, pasted on the player's own background
  at build time; the game's backgrounds are never committed, whole or in part;
- a new screen's `.MAP` takes its structure from a disc map read at build time, with its sprite pixels zeroed, its
  instances hidden, its Digimon and exits cleared;
- foreground objects use reviewed SAM silhouettes and world depth anchors so the
  character can walk behind raised parts while solid footprints remain blocked;
  palette packing preserves exact background colours in every time-of-day CLUT;
- wild Digimon stand at least their chase range + 300 from every arrival point (`maps/author/audit-spawns.py` checks
  every screen at build time).

Connections into original areas retain their story gates: the Galleries' Drain
needs Whamon or the reopened town; the Rubbish Mouth and Iron Hills need an opened
northern road; the Overdell Pass retains the jungle crossing. The conditions live
in `arcs/galleries/` and `arcs/seam/`, with block lines in all eight text banks.
Mineward exits and a legacy escape for saves stranded inside the Seam stay open.
See [the world audit](../../../docs/mods/world-audit.md) before changing these
connections or regenerating their step-trigger tiles.
