# Translating: our own English from the Japanese

`text/ours/` is the repository's own translation: **English, translated from the Japanese script**. It
fills the same keys as the text of the discs, so `TEXT=ours tools/build-full.sh ours` builds the
game with it, and every key not translated yet stays US English (listed in `build/ours/text-fallback.txt`).

The Japanese is the source; the US English and the Spanish fan translation are context only. **Never copy a line** of any
disc (US, Japanese or Spanish) into `text/ours/`: the discs' text belongs to its rights holders (and the fan translators); ours is our own
writing. The discs' text lives in the gitignored `text/<source>/` folders of your machine.

## Workflow

1. **Extract everything first** from your own discs:

   ```bash
   python3 tools/dws.py extract-text "DigimonWorld (Japan) (Rev 1).cue"     # the source: Rev 1 (the US story's fixes)
   python3 tools/dws.py extract-text "Digimon World (USA).cue"              # context
   python3 tools/dws.py extract-text spanish-fan-translation.iso --base "DigimonWorld (Japan).cue"   # context, if you have it
   ```

2. **Open the review** of a zone: `python3 tools/dws.py text review native-forest` → `build/text-review/index.html` (JP, US,
   ES and ours side by side, with the speaker, the screen and the alignment status). The zones are the folders of
   `story/base/zones/`; `maphead` and `names` are the shared dialogue and the executable's strings.
3. **Translate per key from the JP column**, then compare with the US and ES readings for context: who speaks, what the
   scene is, what a name refers to. Where they disagree with the Japanese, the Japanese wins (the US cut or invented
   things; the Spanish is a translation too).
4. **Write** `text/ours/dialogue/<zone>.json` (`{"s018.sec68.u1": "..."}`) and `text/ours/names.json`. A value is a
   string: the compiler wraps it into rows and pages with the game font's real widths, so you never count characters. Use a
   list of pages (`[["row", "row"], ["row"]]`) only when the page breaks matter (a reveal on its own page).
5. **Build and read it in the game**: `TEXT=ours tools/build-full.sh ours`, play to the scene. A box that overflows or a name that is missing is a build error. To test only your zones,
   `TEXT=ours TEXT_ZONES=toy-town,toy-mansion tools/build-full.sh ours-toys`: the other zones stay US English.
6. Have a second reader review the zone in the game.

## Keys

| key | what |
|---|---|
| `s018.sec68.u1` | utterance 1 of section 68 of script 18: one text box, all its pages |
| `s002.sec6.m0.o1` | option 1 of menu 0 of that section (one row, short: the menu box is narrow) |
| `m1230.u3` | MAPHEAD: the shared dialogue (shops, the save machine...), section 1230 |
| `main.ITEM_NAMES.38`, `main.ITEM_DESCS.38` | item 38's name (19 bytes at most: an accented letter counts 2; and at most 96 px drawn condensed, the lists' width: `glossary.toml` `[items]`) and description |
| `main.MOVE_NAMES.12` | technique 12 |
| `main.STR_YES`, `btl.BTL_STR_DROPPED`, `fish.FISH_STR_...` | the executable's and overlays' messages (the decompilation's text yaml files name them) |
| `main.LAB_STR_*`, `shop.STR_IN_HAND`, `dget.DGET_STR_TOURNAMENT` | the mod's own strings (patch 0090): the lab menu and three labels |

Keep the escapes exactly: `{player}`, `{partner}` (the names the player chose), `{digimon 12}` (the species in story variable 12), `{item 38}`, `{move 5}`,
`{money}` (they print a name or a number at run time: never write the name yourself), `{color 6}` ... `{color 1}` (a coloured
span: keep it around the same words), `{tab 3}`. A `us-only` key has no Japanese counterpart (the US added a page or a
line): translate it from the context. An `x.jp-rev1...` key is Japanese text the US story has no place for: leave it.

## Names

Official English names wherever they exist:

- **species**: the `name` of `content/species/<id>-*.json` (the project's validated species names). Write them as they are there.
  `{digimon N}` does not print species N: it prints the species held in story variable N (`script_textbox.c` case 7,
  `readPStat`), so keep it only where the Japanese or US line already has it, and write a fixed species by its name.
- **items, techniques, places, NPCs**: as the US release named them (the typed ids `Item.<Name>`, `Tech.<Name>` of the story
  language, `docs/data/items.csv`, the screen names of `story/names.toml`).
- **a fresh translation from the Japanese only where the US invented or garbled a name** (truncated item names such as
  `Happymushrm`, a pun lost in English, one place with two names). Apply each chosen name consistently across the translation.

Spanish area names follow the **official Spanish PAL disc**, except garbled or mistranslated names
(such as Sabana Gear, which stays Sabana Gear). Apply the same spelling to map captions, music titles,
dialogue and mod translations; English keeps its own naming rule above. In particular, Misty Trees is
**Árboles de Niebla** (plural masculine: los, de los, en los, a los) and Freezeland is **Tierra Helada**.

The Spanish map signs use **Cabo Iceberg / Árboles de Niebla** (`frzl06`),
**Tienda Monocromática** (`gcan09`, two black lines; the red **de todo** stays),
**TÚNEL TALADRO** (`audit-13`) and **GIMNASIO VERDE** (`audit-14`).
The gym name wraps across the tall board in grey `GIM / NA / SIO` and magenta
`VER / DE`. Authoring wording is recorded in `content/localized/signs/jobs.py`
and `audit.json`. After regenerating private full edits, use
`python3 tools/localize/signs.py --make-cutouts --src build/localized-src/signs`
to publish only masked deltas; inspect the composed, quantized text at game scale.

Check articles and agreement in each sentence when changing a name. Map names must fit the on-screen
caption and music titles their list field; validate the build and review them in the game. Rewrap explicit
dialogue rows by hand when a longer name exceeds the font's row limits below. Check both the original
font and font b: the multilingual build compiles both layouts. Keep the full place name in music labels;
shorten the `Tema de...` framing or use `(n.)` for the night variant when necessary.

Display names and identifiers are separate: renaming an item in `names.json` changes what the player reads, never the
`Item.X` a story file uses. A mod's line that names an item writes
`{item Item.Digimushrm}` (or `{item 44}`): the name the inventory shows, whatever the text source.

## Lines the game shows one box at a time

The game's own code shows some lines as **one box, never a second page**: the texts of MAPHEAD's tables (sections 1220-1253
that begin with a table of jumps: the shopkeepers' lines `m1230.*`, the item keeper's, the card shop's...), which it reads by
entry (`getShopkeeperLine`, `resolveMapHeadEntry`, `script_common.c`) and shows with a single box. A translation of such a
key that wraps to more pages than the US text has is a build error that names the key ("m1230.u14 takes 2 pages ...: the
rest would never be shown"): shorten it. A menu option is one row too (62 bytes and 240 px with font b; 31 units with the
original font): a longer one is an error at its
key, in the game's text and in a mod's.

## A new language of the game

`text/<name>/` with the layout of `text/ours/` (`dialogue/<zone>.json` by the keys of the US story, `names.json` for the
executable's strings) is a text source: `TEXT=ca tools/build-full.sh ca` builds it, with no change to the tools. Missing keys follow the text bank's fallback chain and are listed in the build's
fallback report. For the supported runtime language selector, see [languages](language.md).

## A mod's translation

A mod's new lines are in its own `text/en.json`, written by `python3 tools/dws.py text sync MOD`: the lines written in place
(`say("Thank you!")`) by the hash of their words, **in source order**, with `_where` saying where each is, **who says it**
(`courier (Gotsumon) says, page 1 of 2`, `the narrator says`) and which are **menu options** (`option yes of the tamer's
menu`: one row, 31 units), and the **named lines** (`t("greeter.hello")` in the source) by their names. The translation is
`text/<lang>.json` beside it, by the same keys. **The source wins**: the English of a line written in place lives in
`src/*.py`, and `en.json` is rewritten from it (an edit there is lost); a named line's English is `en.json`'s.

- An edited line written in place gets its old translation back marked `~fuzzy `: the build **does not ship it** (it shows
  the English and warns at the line) until you read it against the new English and drop the marker. A named line keeps
  its translation when its English changes; `text sync` lists it under `"_changed"` (with the English it was made from)
  and `check --lang` notes it until you remove the entry.
- `python3 tools/dws.py text review MOD` writes `build/text-review/MOD/index.html`: every line in source order, the English
  beside each language, and what is left (missing, `~fuzzy`, English changed).
- `python3 tools/dws.py check --lang es MOD` checks the translation as the game will draw it: a character the target's font
  lacks or an unknown escape is an error at the line (`es.json, courier.a1b2c3d4: ...`); a menu option too wide, the same; the
  lines it does not translate (they stay English) and the keys that are no line of the mod (a typo; a key of the game's own
  text, which a mod does not change) are warnings; a language no bank has is an error.

## A mod in your language

The game's own lines follow the text source (`TEXT=`/`--text-source`), the mods' new lines `--lang`:

```bash
python3 tools/dws.py disc --exe mods --lang es story/mods/MOD                       # the mod in Spanish on the US game
python3 tools/dws.py disc --exe mods --text-source ours --lang es story/mods/MOD    # on our game (story/base in text/ours)
TEXT=ours STORY_LANG=es EXTRA_STORY=story/mods/MOD tools/build-full.sh ours-es      # the whole build, our game and the mod in Spanish
```

`disc --text-source` (default `$TEXT`) builds the game's story from `story/base` in that source as `story-build` does,
the mod's files on top; the accents and the 16 punctuation glyphs need a mod executable (`--exe mods`, `species` or
`story-state`).

## Style

- **Natural English, faithful to the Japanese meaning and tone**, not to its word order. Short sentences: a page is 3 rows
  with a speaker (4 for the narrator). **Row limits depend on the executable's font** (`docs/mods/font.md` "Fonts"; the
  compiler reads it from the build, or `--exe-font`): with font b (the default of the mod executables since patch 0099)
  a row holds **62 bytes and 240 px**, the last row of a page 228 px (it stops before the "next" button), about 43
  characters: a letter, digit, space or `. , : ; ? ! ' " + - =` takes one byte, an accented letter, a button or other
  punctuation two, a colour code two, a name about 16. With the original font (the US executable, `TEXT=us`) a row holds
  31 units and 240 px (the compiler wraps at both; a row of 32 or more spills into the next row's text on screen). A unit is a letter, a space, a button glyph
  (○ □ △ ×) **or a colour code**: `{color 6}` draws nothing but takes a unit of the row, so a row of 31 letters with
  `{color 6}×{color 1}` in it is 33 units and runs into the next row. The player's and
  partner's names count as about 8. In a list of pages, a row that does not fit makes the build rewrap the whole value
  (its page breaks are lost). MAPHEAD keys (`m...`, the questions of a new game, the shops) share one resident buffer: **32 768 bytes**
  (0x8000) in the mod executables (integration and tier 2, 2 MB and 8 MB alike; patch 0091). The US MAPHEAD is about 24 700 bytes and the Spanish fan text with every key in 25 712, so a translation has
  about 7 KB to grow; the build prints `MAPHEAD.SCN: N bytes of the executable's 32768 (F free)` and, when it is full, lists
  the keys that stayed US. The original executable still holds 25,000; `TEXT` selects text, not the executable target.
  The other keys (`sNNN...`, the scripts of `DG.SCN`) have no total limit: a longer translation makes `DG.SCN` larger
  than the disc's and the build moves the files after it on its own ([container growth](scripts.md#if-dgscn-grows)); each
  script must stay within 16 384 bytes (the build stops and names the one that does not; with all of `text/ours` the largest is about 12 KB).
- **Voices**: each character keeps one voice throughout. Jijimon is an old man (a little pompous, kind); the Digimon of
  File City are plain and friendly; villains are blunt. Keep the Japanese speech tics as a light English equivalent
  (a catchphrase, a habit), never as romanized Japanese.
- **Style rules:**
  1. Jijimon is **warm and grandfatherly**, a little old-fashioned; contractions are fine (not a stiff, formal voice).
  2. His nickname is **Jiji** (the US name; "jiji" already means grandpa).
  3. The first question asks about a **Digital Monster** (the virtual pet's real name).
  4. **Capitals only for proper names** of items and game stats (Meat, Tiredness, Tamer Level, Happymushroom); generic words lower
     case ("items", "training").
  5. Botamon's baby talk stays a **light tic** ("'kay?"), never a written lisp.
  6. **No honorifics** (the "-san" after the player's name is dropped).
  7. **Digivolve** everywhere (the official English term), never "evolve".
  8. Item names the US cut short get their **full names where they fit** (19 bytes), decided per item in
     `glossary.toml`.
  9. **File City** keeps its official name.
- **Jokes and puns**: translate the joke, not the words; when there is no equivalent, keep the meaning and a light touch.
- **Consistency**: one spelling for every name and term (`glossary.toml` `[terms]`: Bits, Digivolve, the cup names...);
  numbers as digits in menus and stats, words in dialogue under ten.
- **Punctuation the game can draw**: letters, digits, space and `. , ? ! ' " : ; - + =` plus `á é í ó ú ñ ü ç ¿ ¡ « » ·` and
  `( ) & % / … [ ] # * ~ @ – — ♪` (the mod font, `docs/mods/font.md`): parentheses, slashes, `%`, `&`,
  the ellipsis as one glyph `…` (12 px, `...` is 15), the en and em dashes and the note are fine in dialogue, menus and
  names. No quotes other than `"` and `'` (curly quotes become straight ones). The build replaces or drops what the
  target's font has no glyph for and lists it (an older executable: `…` as `...`, `( )` dropped).
- Do not reflow the Japanese page by page: write the sentence; the compiler pages it. Keep a deliberate pause (a reveal,
  a dramatic beat) as its own page with the list form.
