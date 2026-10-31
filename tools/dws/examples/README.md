# tools/dws/examples

The DWS examples: the reference of the language the Python story language lowers to, and fixtures of the compiler's
tests (`tools/test_dws.py` checks them against the golden bytes of the retired quest compiler; `tools/selftest.sh`
compiles and formats every file). They are not a mod: story mods are written in Python (small ones in
`story/mods/examples/`). Each file is self-contained: compile one at a time, because several edit the same scripts.

```
python3 tools/dws.py check tools/dws/examples/tokomon-sparring.dws --build     # compile and assemble
python3 tools/dws.py disc  tools/dws/examples/first-quest.dws --name dws-first-quest
```

| file | shows |
|---|---|
| `first-quest.dws`, `house-cutscene.dws` | the language tour: flags, vars, choices, items, a cutscene with walking and camera (`lib/common.dws` is imported) |
| `tokomon-sparring.dws` | a scripted battle with a reward |
| `jijimon-errand.dws` | an errand: bring items, get bits |
| `forest-challenge.dws` | a wild Digimon challenges you; reward if you win |
| `new-house-story.dws` | a brand-new script for a screen, nothing of the original kept |
| `font-accents.dws` | Spanish and Catalan characters (needs `--exe mods`) |
| `font_punctuation.py` | the punctuation glyphs ( ) & % / … [ ] # * ~ @ – — ♪ (needs a mod executable with patch 0024's punctuation glyphs) |
| `item_names.py` | the item lists with long names (`docs/mods/font.md` "Item names"): the Item Keeper's counter opens the keeper, Mojyamon's trades or a battle; a chest holds a Deluxe Mushroom (`docs/developing.md`) |
| `forest-garurumon.dws` | any Digimon as a map enemy with its own stats (`place`) |
| `jungle-newcomer.dws` | a new NPC slot in a map (the `.MAP` grows, needs `--exe mods`) |
| `species-180.dws` | a species that is not on the disc (needs `--exe species`) |
| `expanded-state.dws` | the story-state engine (needs `--exe story-state`): story flags above 799 (bit 16000), 32-bit and scene variables, saved in the three-block save file |
| `dev-save.dws` | development helper: talking to Jijimon opens the save machine (used by `tools/build-full.sh`, `python3 -m tools.dev build --dev-save` and the DLC's `DEV=1` build; never on a player's disc) |
| `kunemon-readable.dws` | Kunemon's talk (script 2 section 6) as a person writes it in DWS; a test proves it is the disc's section |
| `expanded-crowd.dws`, `expanded-city-rules.dws` | Story-state target: placed Digimon by rules, the city's own rules |

The text of each example is in `<name>.en.json` beside it (own text only). `tools/selftest.sh` compiles every file.
