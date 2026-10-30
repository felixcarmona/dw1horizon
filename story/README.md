# story/

The story sources of the game. Mods are written in the story language, a Python subset (`docs/mods/story-language.md`:
the language, and § 7 how to build a mod onto a disc and play it); DWS (`docs/mods/dws.md`) is what it compiles to, and
the hatch for what the Python surface does not say.

| folder | what |
|---|---|
| `core/` | the standard library in DWS: engine names, scene helpers, recruit. Imported by everything else |
| `base/` | committed key-only logic, originally generated from the USA disc, with reviewed Horizon edits pinned in `authored.json`; Python views and DWS, MAPHEAD and city declarations. `story-base --reproduce` checks fresh generation plus those edits; `story-build` compiles the committed source |
| `mods/<name>/` | one folder per mod or DLC: `mod.toml` (its name and `[save]` ranges), `README.md`, `src/` (its `.py` files: one per place, plus quests and constants), `text/` (`en.json` and translations, by `dws text sync`), `save.lock` (the numbers its flags got: commit it) |
| `names.toml` | the names of the game's own flags and variables (`dw.names`) |
| `story.lock` | append-only numbers of every flag and variable of the DWS sources (commit it) |

Not here: the dialogue of any disc (`text/us/`, `text/jp/`..., extracted from your own discs, gitignored) and build output
(`build/`).

Rules in one list: a mod's new lines are typed where they are said (their key is the hash of the words); the game's own
lines are keys (`text.s002.sec6.u3`: an utterance), never copied; one file per place, NPC group, quest set; a `README.md` in every
folder; no file over 400 lines. Start a mod with `python3 tools/dws.py new mod NAME`, check it with `python3
tools/dws.py check story/mods/NAME`, check the tree with `python3 tools/dws.py doctor`.
