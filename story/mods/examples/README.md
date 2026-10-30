# examples

Small, complete story mods in Python (`docs/mods/story-language.md`). Each file in `src/` is one example. They also
compile together (`check story/mods/examples`): several add guarded handlers to the same NPCs of Jijimon's house, and
the guards of one NPC are tried in the order of the files, the first that holds answering:

```
python3 tools/dws.py check story/mods/examples                                 # the whole folder
python3 tools/dws.py check story/mods/examples/src/first_quest.py --build      # one file: lower, compile and assemble
python3 tools/dws.py lower story/mods/examples/src/first_quest.py              # the DWS it becomes
build/pyright/node_modules/.bin/pyright story/mods/examples/src               # the editor's check (pyright strict)
```

| file | shows |
|---|---|
| `first_quest.py` | Jijimon's gift: a flag, a counter, `ask`, items and bits, two guarded handlers on a base NPC |
| `house_cutscene.py` | the first entry into the house: camera, `face`, `wait`, the narrator; a line that depends on `clock.hour` |
| `tokomon_sparring.py` | a scripted battle with a reward, once (`fight(...) == "won"`) |
| `jijimon_errand.py` | a quest in stages (`class Errand(Quest)`, `advance`): bring two Meat, get 1000 bits |
| `forest_garurumon.py` | owning NPCs of the base (`take_over`): a Garurumon with its own stats in the ModokiBetamon's slot, and two species swaps that say and recruit what they now are |

The words are in the sources; `python3 tools/dws.py text sync examples` writes `text/en.json` (keys by the hash of the
words). `mod.toml [save] flags = "780-799"` keeps the examples' flags in the original engine's free range; `save.lock`
pins each name to its number (append-only).

The DWS examples (the compiler's reference and its golden tests: tier 2 state, fonts, new species, new map slots, the
dev save) are in `tools/dws/examples/`.
