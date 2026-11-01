# The story language: design and rationale

How the story of Digimon World is written in this project, and why it is designed this way. The language is
implemented: every script and MAPHEAD are generated from source files alone, and the extended story is
written in it.

## 1. What it is

The story of the game (every conversation, cutscene, quest, recruitment, shop and screen setup) is bytecode for the
game's own script interpreter, stored on the disc in `DG.SCN` and `MAPHEAD.SCN`. The story language lets a person
write that story as **readable source files** and compiles them back into that bytecode.

Three layers:

| Layer | What it is | Who uses it |
|---|---|---|
| **Python subset** (this document) | valid `.py` files, never executed, read with the standard `ast` module | writers and modders |
| **DWS** (`docs/mods/dws.md`) | the project's existing script language: the intermediate form and the escape hatch | the compiler, advanced modders |
| **Bytecode** | the game's script format | the PlayStation |

## 2. Goals

1. **The source files are the story.** At build time the script containers are wiped and generated entirely from the
   sources (the committed key-only base story, plus the mods). No patching of the original, no hidden
   "original runs afterwards".
2. **Easy to read and write** for someone who programs a bit: short, regular, familiar syntax.
3. **The editor helps**: autocompletion, type errors while typing, go to definition, rename: free, without writing a
   language server.
4. **Faithful compilation**: freshly generated original sources can be checked
   against the disc; reviewed Horizon base edits are declared separately (§ 6).
5. **Publication**: no original dialogue or binary game asset is committed or shipped;
   the published base expresses logic with text keys.
6. **Mods compose**: several mods can change the same screen without copying each other's or the base's code.
7. **Works on a real PlayStation** (2 MB). Validate every shipped feature at that limit;
   an expanded emulator is not a substitute.

## 3. Key decisions and why

| Decision | Why | Alternatives rejected |
|---|---|---|
| **A Python subset** as the writing language | Python parses itself (`ast`), so the front end is robust from day one and our tools are already Python; Pylance/pyright give autocompletion and type checking from a shipped stub package; most people can read it | a **custom language**: needs its own parser and editor tooling (months) and reads too low-level for writers; **TypeScript**: same editor benefits but needs our own parser for the subset; **YAML + dialogue files**: two formats, two parsers, two error paths; **Ink/Yarn**: their choice semantics do not match the game's; **Lua**: no interpreter on the PS1, weaker editor support; **node editor**: good as a view, not as a source (diffs, merges and proofs need text) |
| **Files are never executed** | the PS1 has no Python; the files describe what the compiler emits | executing Python at build time to generate data: hides errors, allows things the engine cannot do |
| **A strict subset** with human error messages | the engine has only integers, flags, jumps and engine calls; anything else must be refused clearly, with line and column | accepting more and failing late |
| **Lowering to DWS**, then bytecode | DWS already has the proven compiler, the beautifier and the equivalence checker; the new front end only builds the same tree | a second back end (two proofs) |
| **Base text by key, new text inline** | the game's dialogue is copyrighted and cannot be published: base lines are references like `text.s002.sec6.u3` into a file extracted from the player's disc; new content is typed in place and extracted to the mod's text bank with stable tags | inline text everywhere (illegal for the base), keys everywhere (unpleasant for writers) |
| **Identity by `(screen, slot)`** | the game addresses NPCs by their slot on a screen; display names are not an engine feature (the box shows the species) and captions repeat (11 screens are called "Gear Savanna") | names or captions as identity |
| **Ownership by handler, not by file** | a mod that adds one NPC to Jijimon's house must not copy the house: it adds an NPC or a guarded handler; two mods touching the same key are an error naming both | whole-file replacement (forces copying base code into mods), `.patch` files |
| **Guarded handlers** (`on_talk(when=...)`) | the original encodes "what does this NPC say now" with thousands of hand-written stage checks; guards make it declarative and let mods add behaviour without owning the NPC | one handler with nested ifs |
| **Quests as state machines lowered to bits** | original has 83 free flag bits and only 10 saved small variables: four stages fit in two bits; the expanded presence table also reads flags | one variable per quest (exhausts original in ten quests) |
| **A reserved flag range per mod** (`mod.toml`) | a flag's number must not depend on which other mods are installed, or saves break | global allocation at build time |
| **Explicit operands where the original is not "self"** | on screen 80 two Vermilimon recruit **Yanmamon**: an implicit "join my species" would silently change the story | implicit-self verbs everywhere |
| **`scene=True` as a handler property** | the cutscene flag (trigger 44) is consumed at the first pause and does nothing in `on_enter`; as a property it is set where it works, and nowhere else | a `with scene():` block in every handler |
| **Compile-time collections only, for now** | constant tuples and dicts unroll into the code the disc already has (food lists, keeper rotas); run-time sets over known universes (`Set`, `Deck`, the `*_VI` opcodes) are deferred until a mod needs them | dynamic lists, dictionaries or strings at run time |
| **Text keys by content hash** | a new line's key is the hash of its text: moves and pastes keep translations, and no tag comment is needed on any line | `# @tag` comments on every line, keys by position |

## 4. The language at a glance

An illustrative quest in the Python form (abridged: the waiting handler and some lines are left out):

```python
from dw import *
from dw.base.jijimons_house import tokomon

class Horn(Quest):
    NONE = auto()
    ASKED = auto()
    FOUND = auto()
    JOINED = auto()

invited = flag()

house = screen(Screen.jijimons_house)
gekomon = house.npc(Species.Gekomon, at=(450, -650), behaves_like=tokomon,
                    when=Horn.before(Horn.JOINED))
resident = house.npc(Species.Gekomon, at=(150, -350), behaves_like=tokomon,
                     when=Horn.JOINED)

@gekomon.on_talk(when=Horn.NONE, scene=True)
def asks():
    say("Hrrm... Oh! A Tamer! Sorry for the gloomy face. I play the horn, far away in the swamps.",
        "Jijimon asked me to play the morning call for File City, but my horn has gone silent!")
    if ask(yes="Leave it to me", no="Not right now"):
        say("Thank you! Walk the forest path and listen for a bad whistle. That is the thief!")
        advance(Horn.ASKED)
    else:
        say("I understand. I will wait here with Jijimon. The city is so quiet without music...")

@gekomon.on_talk(when=Horn.FOUND, scene=True)
def comes_home():
    say("That shine... my mouthpiece! You really found it! Pa-paaa! My horn sings again!")
    if invited:
        say("A puppet who wants to play with others? I will teach him a proper tune! Here, thank you.")
        give(Item.SweetNut, 2, bits=800)
        narrator.say("Received 800 bits and 2 Sweet Nuts.")
    else:
        say("And the thief ran off? Then the forest will be quieter. Please, take these bits.")
        give(bits=1500)
        narrator.say("Received 1500 bits.")
    walk(150, -350)
    send_to_city(line="Gekomon joined File City!", prosperity=2)
    advance(Horn.JOINED)

@resident.on_talk
def morning_call():
    say("Pa-paaa! Good morning! Doesn't File City sound livelier now?")
```

A piece of the **base story** (Kunemon, generated from the player's disc by `dws story-base`; keys only, the text stays on
the disc; the view keeps the disc's order of the tests, so the cancelled menu is an explicit `pass`):

```python
bed = screen(Screen.kunemons_bed)
kunemon = bed.npc(Species.Kunemon152, slot=1)
t6 = text.s002.sec6

@kunemon.on_talk(scene=True)
def talk():    # section 6
    play(29)
    say(t6.u0)
    if ask(yes=t6.m0.o0, no=t6.m0.o1):
        pick = pick_item()
        if pick is Picked.EMPTY:
            tamer.say(t6.u1)
        elif pick is Picked.CANCELLED:
            pass
        elif pick in (Item.Meat, Item.GiantMeat, Item.Sirloin, Item.Supercarrot, Item.HawkRadish, Item.Digimushrm, Item.Digianchovy, Item.MoldyMeat):
            take_picked()
            play(30)
            wait(1000)
            play(8, wait=True)
            say(t6.u3)
            ...                                  # (abridged: the fight, the talk, the walk away)
            send_to_city(line=t6.u8, species=Species.Kunemon)
            return
        else:
            tamer.say(t6.u2)
    say(t6.u9)
    play(28)
    wait(1000)
```

(The disc tests the eight foods in two `IF`s of four
with the same code after each; the beautifier writes them as one test and the proof accepts it, because the engine folds
an `IF`'s clauses left to right: `flowcmp` compares one node per clause.)

## 5. Concepts

- **Imports.** `from dw import *` is the language; `from dw.base.<screen> import house, jijimon` the base's screens and
  NPCs; `from dw.text import text` the game's own lines by key (`text.s178.sec5.u0`: an utterance, one text box with its pages; `t6.m0.o1`: an option of a menu); `from dw.names import *` the
  game's named state (`debug_mode`, `piximon_in_item_shop`...); `from .quests import Horn` another file of the same mod
  (no `__init__.py` is needed; `from ..state import root1`: a file in another folder of the same mod). Nothing else is importable. What crosses files is a mod's quests, flags, counters and
  constants (a file of constants only is fine: `FOODS = (Item.Meat, Item.Sirloin)`, `OPEN_FROM = 8`); an NPC stays in the
  file of its screen, with its handlers (one file per place: the DLC's layout), and a `def` is used in the file that has
  it.
- **Screens and NPCs.** `screen(Screen.x)` is a game screen; `new_screen(N, map=...)` is a screen of the mod's own.
  The base's screens and NPCs are imported from the screen's module, named like its `Screen` member:
  `from dw.base.jijimons_house import house, jijimon` (the stub lists each NPC with its slot, and the screen it stands on
  when the script serves several). `house.npc(Species, at=, behaves_like=, when=)` declares a new NPC, once, with its
  species, position (`at=(x, z)` is required), the NPC whose behaviour (range, stats, path) it copies and the condition
  under which it is there. **A new NPC takes the screen's next free slot**; two in one file, two files or two mods on one
  screen take them in load order (`python3 tools/dws.py slots SCREEN` shows the first free one; `slot=` may say it, and
  must be that one). Which script section answers when it is talked to is the compiler's: usually 5 + slot; when another
  screen of the same script has an NPC on that section (script 168 serves both arena lobbies: slot 1 is free on 208 and
  Airdramon's on 223), the first section no NPC of the script uses, and `check` and `slots` say so.

  Three ways to change an NPC, and what the base keeps:

  | You want | Write | The base keeps |
  |---|---|---|
  | **add** lines to a base NPC or screen | import it, `@jijimon.on_talk(when=...)`, `@house.on_enter(when=...)` | everything: its talk answers whenever no guard of yours holds; its enter, step and use code runs after yours |
  | **own** a base NPC | `jiji = take_over(jijimon)`, then `@jiji.on_talk` handlers | its slot, species and presence; its talk runs only where a handler of yours goes on into it (`return jijimon.talk()`: a line of yours, then the game's own talk) |
  | **swap** its species | `vegie = take_over(modokibetamon1, species=Species.RedVegiemon)` (+ `at=`, stats) and its own `@vegie.on_talk` | its slot and presence; the base's talk would say and recruit the old species, so a taken-over NPC needs a handler |
  | a **new** NPC | `house.npc(Species.Gekomon, at=(x, z), ...)`: the next free slot | nothing to keep: the slot is the mod's |

  A new NPC's `when=` is its presence: the compiler writes it into the screen's MAPHEAD setup (`IF ... LOAD/SET_DIGIMON`),
  which every engine runs. It tests saved state and **the clock**, as the game's own shopkeepers do: an NPC there only at
  night is `house.npc(Species.Bakemon, at=(-450, -650), behaves_like=tokomon, when=clock.hour >= 20 or clock.hour < 5)`
  (the setup reads the clock when the screen loads: leaving and coming back at 22:00 finds him there). Items, counters,
  stats and random draws are not presence (`check` says so); to send an NPC away by one of them, `npc.leave()` in an
  `on_enter`. `screen(a, b).npc(...)` puts it in the same slot of each screen (one script's screens: the
  File City square is the twelve screens `file_city_168`-`file_city_179` of script 162, one per layout the recruits
  choose, every one with its eight slots used). `python3 tools/dws.py slots SCREEN` shows the free slot, the species
  that fit in the heap left (measured as `check` measures it; a species already on the screen costs only its instance
  data, its model is loaded once) and where a new NPC can stand: the box of the walkable tiles (`at=(x, z)` inside it) and the
  `dwmap.py overlay` command that draws the screen with them and the coordinates every 500; `check` refuses a species
  that does not fit, or a wall tile, at the `npc()` line.

  **A newcomer who "moves to the city"** stands in Jijimon's house, as the DLC's Gekomon does: the square has no free
  slot on the original engine and little heap left for another model. In the house, take the first free slot and check the
  room that `python3 tools/dws.py slots jijimons_house` shows with your other mods in mind (alone: slot 4, about 96 KB
  on the original engine; the DLC takes slots 4 and 5 and 54 KB of it; with the DLC installed, yours takes slot 6).
  `check` with all the mods together says it exactly:

  ```python
  from dw.base.jijimons_house import house, tokomon
  resident = house.npc(Species.Gabumon, at=(150, -350), behaves_like=tokomon, when=recruited(Species.Gabumon))
  ```

  What needs the story-state engine (`check --exe story-state`): NPC slots 8-15, species beyond the game's
  180 (the imported ones, DIGI.DAT), more flags than the original engine's 83 free ones (story flags), a `city { }`
  table (prosperity, top map...). Everything else, presence included, builds for the original engine.

  `when=` composes differently on talk and on the screen's events, and the rule is fixed: **on talk, a guard that holds
  answers instead of the base; on enter/step/use, yours runs first and the base's code always runs after it**, so a
  `return` there is refused (it would skip the screen's setup; a `warp` ends the handler by itself).
- **Events.** `on_talk`, `on_enter`, `on_step(tile)`, `on_use(tile)` (a trigger of the screen's map: `dws slots SCREEN`
  lists them with where they are; one the map lacks is refused), and the expanded hooks. Several handlers per NPC,
  each with a `when=` guard, tried in order (the first that holds answers; a handler without `when=` goes last). A guard
  tests saved state (quest stages, flags, counters, items, recruits): the clock, random draws and battles are tested with
  an `if` inside the handler, and pyright already marks them red in `when=` (a new NPC's own `when=`, its presence,
  may test the clock: Screens and NPCs).
- **Dialogue.** `say(...)` with several strings is one box with several pages; a new `say` is a new box (the game
  distinguishes chained pages from separate boxes, and the compiler keeps that). The speaker is the NPC being talked
  to unless written (`tamer.say`, `narrator.say`, `npc.say`). Boxes are split automatically to the PS1's 3 lines.
- **Text.** Base lines: `text.sNNN.secN.uN` keys (typed, from the player's own extracted text; `TEXT=` switches them to
  another text source). New lines are written in one of two ways, which mix freely in one mod:

  - **in place**, `say("Thank you!")`: the key is the hash of the words, so a translation stays with the line wherever it
    moves; an edited line gets its old translation back marked `~fuzzy`, which the build does not ship (it shows the
    English and warns at the line until the translator drops the marker);
  - **named**, `say(t("greeter.hello"))`: the English is in the mod's `text/en.json` under that name, written there by
    you; the name never changes, so a translation is never fuzzy (when the English changes, `text sync` lists the line
    under `"_changed"` in each translation, and `check --lang` notes it). A name `en.json` lacks is an error at the line
    with the nearest names; a name nobody uses is a note.

  ```python
  # a mod "hello": src/hello.py                             # and its text/en.json
  from dw import *                                         # {
  from dw.base.jijimons_house import house, tokomon        #  "greeter.hello": "Hello, {player}! I am the greeter.",
                                                           #  "greeter.yes": "Yes, please",
  greeter = house.npc(Species.Tokomon, at=(150, -350), behaves_like=tokomon)    #  "narrator.bow": "The greeter bows."
                                                           # }
  @greeter.on_talk
  def hello():
      say(t("greeter.hello"), "And this line is written in place.")       # a named page, then an inline one
      if ask(yes=t("greeter.yes"), no="No"):
          narrator.say(t("narrator.bow"))
          give(Item.Digimushrm)
          narrator.say("Received a {item Item.Digimushrm}.")    # the name the inventory shows, renamed or translated
  ```

  **Escapes** put what the game knows into a line: `{player}` and `{partner}` (the names the player gave),
  `{item Item.Digimushrm}` (an item's name as the inventory shows it: `Digimushrm` on the US disc, `Digimushroom` with
  `TEXT=ours`, the translation's in another language: write it so, not by hand), `{move Tech.X}`, `{money}`, and
  `{color N}`...`{color 1}` (a colour; it takes a unit of the row). An escape the game does not have, or an item that does
  not exist, is an error at the line. No tag comments. A line uses the game's font: letters, digits, spaces and
  `. , ? ! ' " : ; + - =` (the original's 79 glyphs); `--exe mods`, `species` or `story-state` add the accents, `ñ`, `¿` `¡`
  and `( ) & % / … [ ] # * ~ @ – — ♪` (`docs/mods/font.md`; an older executable lacks the
  punctuation, and `check` says so). For the original executable `check` refuses `( ) & % / [ ] # * ~ @` at the line
  and draws the others plain (a note: accents stripped, `…` as `...`, `–` `—` as `-`, `♪` left out).
- **Choices.** A menu option is one row of the box: at most 31 units and 240 px (`check` refuses a longer one at its
  line, in English or in a translation: the game cuts it at the box edge and does not draw the options below it). A menu
  of the tamer or an NPC has 3 rows under the speaker's name, and the narrator's box 4: `choose()` with more options than
  that is refused (the last ones would not be drawn); `narrator.choose(...)` takes four, more need two menus.
  `ask(yes="...", no="...")` returns True when the player picks `yes`, which is always the top option
  (the keywords are bound by name, in any order; both are required, cancel counts as "no"; `if not ask(...):` tests
  "no"); `choose(...)` with `match` for more options or other names, with the cancel case explicit. The item menu:
  `pick = pick_item()`, then `if pick == Item.Medicine:` (or `pick in (Item.Meat, Item.Steak)`), `pick is Picked.EMPTY`,
  `pick is Picked.CANCELLED`, and `take_picked()` takes what was given.
- **Quests.** `class Q(Quest)` with stages; conditions `Q.X`, `Q.before(Q.X)`, `Q.reached(Q.X)`; `advance(Q.X)`.
  `match Q.stage:` with a `case` per stage.
- **Flags.** `flag()` gives a named flag, `counter()` a small saved number, from the mod's reserved range: a mod that has
  any reserves it in its `mod.toml` (`[save] flags = "717-726"`, `vars = "9-11"` for counters), or `check` refuses it
  and prints the lines to add with a range no other mod reserves (a number that depended on the other mods installed
  would make old saves read the wrong flag). Who sets or reads a flag of the game (`meat_farm_explained`, `from dw.names
  import *`): `python3 tools/dws.py why meat_farm_explained` lists where `story/base` uses it.
- **Talk and turning.** When a talk starts, the NPC and the tamer turn to face each other (most of the game's talks).
  `on_talk(scene=True)` keeps them as they are: a staged scene whose `walk`/`face` place them (14 talks of the game).
- **Actions.** `give(item, n, bits=)`, `take`, `fight(...)` (its outcome is tested where it is fought:
  `if fight(x) == "won":`, or every outcome of the one battle with `match fight(x):` and `case "won":`, `case "lost":`,
  `case "fled":`; each `fight(...)` is a battle of its own, so testing `fight(x)` twice in a row is refused; `fight()`
  with no foes is the game's open battle, which any Digimon on screen may join and which can always be fled, so
  `escape=False` needs the foes named: `fight(hunter, escape=False)`),
  `recruit(species, prosperity=)` (the flag `recruited(species)` tests), `unrecruit(species)` (clears it),
  `send_to_city(line=, ...)` (the departure scene), `recruitable(npc, line=)`, `walk`, `face`, `play(anim)`, `wait`,
  `camera.on`, `sound(bank, n)` (`sound.jingle()` for 8, 11), `warp(screen, entry=)`, `leave`, `spawn`,
  `spawn_item(item, at=(x, z))` (an item on the ground, picked up in passing; world units like every position),
  `objects[n].show()/hide()/animate(k)`, `spawn_chest(item, at=(x, z), opened=a_flag)` (in `on_enter`; the flag is set when
  the chest is taken and keeps it open; `facing=` 0, 1024, 2048 or 3072), `shop(Item.A, Item.B)` (in `on_talk`: the NPC
  being talked to opens the game's buy/sell menu with these items, in its own box), `roll = random.roll(2)` then
  `if roll == 0:` (a draw, kept until the next; `random.chance(p)` for a percentage), `call(Routine.x, arg=)`; the writer types the
  "Received ..." narrator line. Three ways a Digimon joins the city: `recruitable(npc, line=)` is the game's wild
  recruit. In the extended pass it says the line and fights, then recruits only
  on a first win by a roster species: a jingle and narrator announcement follow
  the completed battle. Repeated wins, fleeing and losing add nothing. An unlisted
  species fights without a recruit flag. The original pass keeps its original bytes. For a base wild NPC,
  check its balanced `content/maps` slot before supplying `joins=`; the variable
  name and original disc placement can differ from the species fought. City
  roster verification checks each compiled story pass separately; `if fight(x) == "won":` then `send_to_city(line=)` is a
  story's (the departure scene: it walks off, the jingle, the narrator's line); `recruit(species)` sets the flag; in the extended pass a silent bare recruit
  gets the same one-time announcement (and a win check after a battle). Existing
  explicit join narration and departures retain their own scene. The compiler expands
  `city.join` from the mod’s text bank using the game’s species name. Reusable pieces are plain `def`s: inlined with parameters; without them, compiled once
  when the def always ends the handler (a warp or `dws("return;")` last), inlined where it is called otherwise, so the
  code after the call runs (a `return` inside such a def ends the whole handler);
  a def that speaks as the NPC being talked to (`def closed(): say("Closed.")`, a `say` without a speaker) is inlined
  in each talk that calls it, so it speaks with that talk's NPC (`return closed()` is the def, then the end of the
  handler).
- **The partner and the tamer.** `partner.happiness >= 50` and the other stats by name, `partner.species ==
  Species.Agumon`, `partner.level >= Level.champion` (the partner species of those levels: the game's 62 on the original
  engine; on `--exe species` / story-state every species of `content/species` with a `partner` block, the imported ones too, and
  every test of the species reads the engine's wide register), its conditions as yes/no (`if partner.sick:`, `hungry`,
  `injured`...), `tamer.level` (and `tamer.add(level=1)`): read where the line runs, in an `if` (a guard tests saved state
  only). An imported species (`Species.Guilmon`, 433) can be the partner only on those discs: on the original engine
  `check` refuses the test at its line. A counter is a byte there (0-255): `n >= 300` is refused too, as `give(Item.Meat,
  300)` is.
- **Time.** Every duration is in milliseconds, on the game's grid of 50 ms (20 ticks a second): `wait(1000)`,
  `fade_to_white(2000)`, `walk_away(x, z, pause=1000)`; a time off the grid is an error that gives the two nearest.
  (`camera.on(speed=)` is a speed, not a time.) The clock is read where a line runs: `if clock.hour >= 18:`, a day of
  the 30-day year `clock.day == 7`. A waiting period ("come back tomorrow", "three days later") keeps the day in a counter,
  `last_day.set(clock.day)` (every engine), and tests `if clock.day - last_day >= 3:` (`== 0`: the same day, "one catch a
  day"; only days are counted, so a wait longer than the 30-day year has no form; the story-state engine: the original
  engine's `IF` compares a saved number with a constant only, so `check` refuses it there; counted on the 30-day year,
  right for any wait under 30 days). Animation slots stay numbers (`play(29)`) except the few the engine
  itself gives a meaning to (`anim.idle`...): what the NPCs' gestures 28-32 are, nothing on the disc says.
- **Collections.** A constant tuple is a test: `x in (Item.Meat, Item.Sirloin)` (`not in`: test the members one by
  one). There are no loops over tuples, dicts or run-time collections (`Set`, `Deck`, `LINES[visits]`, `random.choice`,
  the expanded `*_VI` instructions): deferred until a mod needs them.
- **Hatches.** `raw.<command>(...)` for one DWS command by name, `dws("""...""")` for DWS statements verbatim; the
  generated base uses them where the disc's form has no Python equivalent (jump tables, open menus, the `~>` fold).

## 6. How it is compiled and proven

1. The `.py` files are parsed with `ast`, checked against the subset, and lowered to the DWS tree. Anything outside the
   subset is an error with line, column and a suggested rewrite; every error of a file is reported in the same run.
   What the compiler finds after that (a slot or a position the screen's `.MAP` refuses, the screen's heap, an engine
   tier) is reported at the `.py` line too, through the source map: a writer never sees the lowered DWS.
2. The DWS compiler emits the bytecode and fills the script containers from scratch (steps 1 and 2: done). The base is
   compiled from its committed Python view by default (`--from-dws` selects DWS).
   The generated view must lower to equivalent code, and `typings/dw/base` supplies
   the import surface for mods.
3. **Proof**: `dws.py story-verify` compares builds by control-flow equivalence per
   section. Freshly generated original sources can be compared with the disc;
   Horizon's authored base changes are declared in `story/base/authored.json`.
   Emulator checks exercise behaviour beyond this static comparison.
4. Mods are compiled on top, with ownership checks and their own flag ranges.

The base story's key-only logic is committed in `story/base`. Dialogue is extracted
locally from the player's disc and is never committed. The build preserves the
committed sources; `story-base --reproduce` checks fresh generation plus the
reviewed changes pinned in `story/base/authored.json`.

## 7. Build it and play it

A mod is checked and put on a disc with these commands (with a one-NPC mod, each takes a second or two):

```bash
python3 tools/dws.py check story/mods/MOD                  # errors at the .py lines; the slots, the heap, the numbers
python3 tools/dws.py disc story/mods/MOD -o build/MOD.SCN --name MOD   # -> build/MOD.cue, the whole disc
                                                              #    (a mod for the engine tier 2: add --exe story-state)
```

Then play `build/MOD.cue` in a PlayStation emulator, with a copy of a memory card that has a save near the mod's
screen (the game writes to it). A new NPC's slot is printed by `disc`; a mod's flag numbers are in `allocation:`,
printed by `check`. A disc is built from the original disc's files plus what the mod changed
(`DG.SCN`, `MAPHEAD.SCN`, the screens' `.MAP`); it is not committed (`build/` is ignored). Save states do not survive a
new disc (they hold the old scripts in RAM): start from the memory card, as above. For new maps, follow [new-map authoring](new-maps.md); register the map and story
sources in the derive recipe.

## 8. Tools

- **Editor**: a generated stub package (`typings/dw`) so VS Code with Pylance autocompletes species, items, screens,
  text keys and quest stages, and flags typos as errors; one `pyrightconfig.json` at the repository root (strict; an
  unused import is a warning). The stubs offer only what the compiler accepts, and refuse in the editor what types can
  express (`ask` without `yes=`/`no=`, the clock or a random draw in `when=`, a name that does not exist); the rest (an
  assignment, `wait(333)`, `say()` in `on_enter`...) is refused by `dws check` with the line and a rewrite. A mod's files
  live in `story/mods/<mod>/src/`: guards and new text are refused elsewhere.
- `dws types`, `dws check`, `dws lower`, `dws text sync`: the stubs, the subset check, the lowered DWS, the text banks.
- A source map, so emulator traces and errors point at source lines.

## 9. What is forbidden, and why

Run-time lists, dictionaries and strings of variable size, floating point, closures and objects created at run time,
imports of real Python libraries, `async`/`await`, recursion: the engine has none of them. They are refused with a
clear message. The escape hatches stay: DWS blocks and raw instructions for the rare cases the surface cannot express.

## 10. Commands

How the pieces fit: code the original shares between sections has a source form (shared blocks, labels, tables);
every script and MAPHEAD is generated from the sources alone; a stub package and a Python view of the base (screens,
NPCs, guards, keys) give the import surface; the Python front end checks the subset, lowers it and enforces ownership;
mods have their own flag ranges and a source map; `story-build` reads the base's Python view (`story/base/**/*.py`),
and the `.dws` is the generated intermediate. The commands:

```bash
python3 tools/dws.py types [--check]                 # typings/dw: the stubs for Pylance/pyright (pyrightconfig.json at the root)
python3 tools/dws.py lower FILE.py                   # the DWS a story file becomes
python3 tools/dws.py check|compile FILE.py ... X.dws # .py and .dws compile together (a mod's errors point at its .py lines)
python3 tools/dws.py check story/mods/MOD             # a mod's folder: all its sources (src/*.dws, src/*.py); `-v`: the build's details too
python3 tools/dws.py disc story/mods/MOD -o build/MOD.SCN --name MOD   # the mod on a disc: build/MOD.cue (§ 7: play it)
python3 tools/dws.py text sync [MOD]                 # text/en.json of a mod from its strings; translations carried as ~fuzzy
python3 tools/dws.py why NPC [MOD...] [--as "Horn=ASKED, invited"]   # where a mod's NPC is (story/mods, or the mod folders given), when it is there, which handler answers
python3 tools/dws.py slots SCREEN                    # a screen's NPC slots (species, base names, positions), the next free one, where a new NPC can stand (at=), its entries (warp entry=)
python3 tools/dws.py story-base --check              # remake story/base with its Python view and prove the view against the disc
python3 tools/dws.py story-build ...                 # the base is built from its Python view (`--from-dws`: from the DWS; same bytes)
```

A mod reserves its save flags in `mod.toml` (`[save] flags = "12000-12099"`); the numbers it got are in `save.lock`
(append-only, committed). DWS mods and `overrides/` still build, with a deprecation warning.

Any change to the pipeline must end with the full verification at 0 differences.

## 11. Risks

- Writers may expect full Python: mitigated by the error messages and the stub package (only allowed names exist).
- The two shared-exit sections of the original (Kunemon, Jijimon) needed a new equivalence rule (one node per `IF` clause); they
  print as Python. What still prints as a `dws(...)` block: jump tables, data rows, the 16 KB libraries.
- The stubs must stay in sync with the game data: they are generated, never hand-written.
- Tier 0 memory and flag space are tight: the compiler reports budgets per mod.

## 12. See also

- `docs/mods/dws.md`: the DWS language, the intermediate form and escape hatch.
