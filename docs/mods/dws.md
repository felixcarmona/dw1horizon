# DWS: intermediate language reference

> **Write new story in Python** (`docs/mods/story-language.md`: the language; `story/mods/examples/`: small authoring
> examples). DWS is what it lowers to, the form of the generated base beside its Python view, and the escape hatch
> (a `dws(...)` block, a `city { }` block). A mod whose story is in DWS, and `overrides/`, still build with a warning.

`tools/dws.py` compiles `.dws` files, a typed language with braces, into the game's scripts
(`DG.SCN`, `MAPHEAD.SCN`, `.MAP` edits). This page is the reference of the language (**tier 0**:
the output uses only the original opcodes and runs on the **original executable**; tiers 1 and 2 are
noted where they differ).

```bash
python3 tools/dws.py check   mod.dws                                # parse, resolve, lint (add --build to assemble)
python3 tools/dws.py show    mod.dws                                # the generated assembly
python3 tools/dws.py compile mod.dws -o build/dws/DG.SCN
python3 tools/dws.py disc    mod.dws --name dws-mod                 # build/dws-mod.bin
python3 tools/dws.py fmt     *.dws                                  # canonical layout (--check to only test)
python3 tools/dws.py text-extract                                  # your disc's dialogue -> text/us/dialogue.json
python3 tools/dws.py text-keyed 2                                  # script 2 of the disc as keyed DWS (raw assembly)
python3 tools/dws.py decompile 2                                   # script 2 in the port form: typed statements, no asm()
python3 tools/dws.py decompile-all [-o story/base]                 # the whole disc into the story/ layout (one file per section chunk)
python3 tools/dws.py roundtrip [--layout]                          # decompile -> compile -> compare with the disc (222/222 + MAPHEAD)
python3 tools/dws.py decompile --readable 2                        # the beautifier: if/else, loops, choice, say, names; every section proven
python3 tools/dws.py decompile-all --readable [-o DIR] [--scripts 2,3]   # the same for the story/base layout (a sample, or all + MAPHEAD)
python3 tools/dws.py story-base [--refresh]                         # generate only when missing; --refresh replaces sources explicitly
python3 tools/dws.py story-build [SRC.dws ...] [--mods all|none|a,b] -o build/story/DG.SCN   # the game's story: story/base + mods' overrides + SRC -> DG.SCN, MAPHEAD.SCN
python3 tools/dws.py story-section 2 6 [-o FILE]                    # one event of story/base, standalone (to read, or to diff into a .patch)
python3 tools/dws.py story-verify A/DG.SCN A/MAPHEAD.SCN B/DG.SCN B/MAPHEAD.SCN   # two builds, section by section (flowcmp)
python3 tools/dws.py readable-coverage                             # what the beautifier lifts: a CSV, one row per section
python3 tools/dws.py names                                         # pstat/trigger names from the decomp headers into story/names.toml; names-todo.csv (the 30 most used unnamed)
python3 tools/dws.py coverage                                      # what DWS can express without asm(): CSVs
python3 tools/dws.py new zone|quest|npc|mod NAME                   # scaffolding in story/ (quest and npc take ZONE/NAME)
python3 tools/dws.py doctor                                        # checks the story/ layout
python3 tools/dws.py check --profile extended-save mod.dws                 # design against the expanded pools (any --exe)
python3 tools/dws.py city-extract | city-compile | city-verify | why NPC   # the city's rules as data, NPC presence (docs/mods/city-rules.md)
python3 tools/dws.py compile --exe story-state mod.dws -o DG.SCN         # optional story-state compiler target
python3 tools/dws.py compile ... --srcmap DG.SCN.srcmap.json        # also the source map: script -> [[offset, "file:line"]] (same bytes)
```

Options of `compile/disc/show/check`: `--exe original|mods|species|story-state`
(`original` strips accents; `mods` allows wide ids; `species` also allows imported
species; `story-state` supports story flags and 32-bit variables),
`--profile original|extended-save` (default: `extended-save` with `--exe story-state`,
else `original`; `extended-save` compiles only for `--exe story-state`, while
`check` without `--build` accepts it for any executable), `--text BANK.json` (extra bank, repeatable),
`--lang LANG` (the mods' lines in their `text/LANG.json`, checked: `docs/mods/translating.md` "A mod's translation"), `disc --text-source SOURCE` (the game's own lines from `text/SOURCE/`, default `$TEXT`: "A mod in your language"), `--lock story.lock [--update-lock]`. Several files compile together; each file may
`import "other.dws";`. Test the result from the memory card (see [testing](../developing.md)).

The optional story-state runtime extension is parked and requires rebasing and
original-2-MB validation before use; compiler support does not make it a supported
playable build. See [story-state target](story-state-engine.md). The everything
recipe uses the original allocation pools on the production mod executable.

## Example

```
flag reward_taken;                 // a free trigger (717-799), allocated by the compiler
var visits;                        // a saved pstat (7-15, 20)

script 178 {                       // DG.SCN script 178: Jijimon's house
    npc jijimon = 5;               // entity number = the slot's script id in the .MAP (usually 5 + slot)

    on talk(jijimon) replace {     // section 5; without `replace` the original talk runs afterwards
        visits += 1;
        if (reward_taken) { say(jijimon, text("first.again")); return; }
        say(jijimon, text("first.hello"));
        choice {
            text("first.opt.yes") => {
                give(item("Meat"), 2);
                give_bits(500);
                reward_taken = true;
            }
            "Not now" => { say(jijimon, "Maybe next time."); }     // a literal string is fine for new text
        }
    }
}
```

A readable, hand-written version of script 2 section 6 (Kunemon's conversation, "the Kunemon twin" below:
`on talk ... replace`, `choice`, `else if`, `in [...]`, `battle(foes: ...)`, a `while` for the looks back) is proven equivalent to the
original: `tools/dws/flowcmp.py` compares it with the disc's section as a control-flow graph (bisimulation).

Complete example programs are in `story/mods/examples/src/` (written in Python, which lowers to DWS).

## Language reference

Comments `// ...` and `/* ... */`. Statements end in `;`. Names are case-sensitive.

### Top level

| Item | Meaning |
|---|---|
| `module name;` | namespace prefix of the allocation keys (default: the file name) |
| `import "lib.dws";` | loads another file first; its `pub` flags, vars, consts and fns become visible |
| `flag f;` / `flag f = 717;` | bool, one trigger 717-799. With `= N` the number is **pinned** |
| `var v;` / `var v = 12;` / `var v: u8;` | u8 saved on the memory card: pstats 7-15, 20 |
| `persistent`, `session`, `temp`, `screen` before `flag`/`var` | the scope (see "State"): `persistent` is the default; the other three are not saved (pstats 45-93; 94-99 are the compiler's scratch registers) |
| `flag[16] chests;` / `var[3] n;` | an array: consecutive numbers; `chests[3]` with a constant index (original) |
| `var stage: Stage;` | a variable of an enum type (`enum Stage { None, Found = 5, Done }`): only its values are accepted |
| `var big: i32;` | wider types (`u16 i16 u32 i32`) exist in the extended-save profiles; in original they are an error that says so |
| `group Kunemon { var stage: Stage; flag fed; }` | names become `Kunemon.stage`, `Kunemon.fed` |
| `alias flag f = 50;` / `alias var v = 28;` | names something the game already uses; nothing is allocated (`story/core/engine.dws` names the engine's own set) |
| `routine my_routine = 0x40;` | names a `CALL_ROUTINE` number (the 57 of the game are built in: `routine("shop")`) |
| `const NAME = expr;` | compile-time value (`const FOOD = item("Meat");`) |
| `fn name(a: type, b: int = 1) { ... }` | function, **inlined** at each call; `return;` leaves it |
| `sub name(a: u8) -> u8 { ... }` | a real subroutine: compiled once per script after the events, called with `JUMP_AND_LINK`, `return` is `JUMP_RETURN`. Parameters and the result are u8 temp variables (allocated as `name.a`, `name.result`); no recursion; call depth <= 8 |
| `pub` before flag/var/const/fn | visible to files that import this one |
| `script N { ... }` | patch script N of `DG.SCN` |
| `script new for screen S [empty] { ... }` | a new script (222, 223...) that screen S loads; `empty` keeps only stubs |

Parameter types of `fn`: `int bool ticks text entity item species tech card screen track str`.

### State: scopes and pools

| Scope | Lives | Original storage | Extended-save storage |
|---|---|---|---|
| `persistent` | memory card | triggers 717-799 (83), pstats 7-15, 20 (10, u8) | 16 384 flag bits (trigger 800 + n), 1 024 `i32` (`v0`-`v1023`) |
| `session`, `screen`, `temp` | original: pstats 45-93 | pstats 45-93 | 256 scene `i32` (`s0`-`s255`): not saved, cleared on a screen change and on a load |

The optional extended-save target uses a 3-block save slot; it compiles with `--exe story-state`: a story flag `f` is the trigger 800 + its
number, a persistent `var` is `SET_V v7, 100000`, a scene variable `SET_V s3, 1`; `= += -= *= /= %=` with a constant, `= += -=` with another
variable, comparisons with a constant or another variable, the type's range is checked (`i16`, `u16`, `i32`...). The compiler's own temporaries
(loop counters, `sub` arguments) stay scratch pstats 45-93 in every profile. `match`, `sub` arguments and the commands that take a pstat
refuse a story variable with a hint (copy it into a raw pstat: `p110 = story_var;` is `PSTAT_FROM_V`, clamped to 0-255).
A pool error names the pool, its range and what is left.
The names the engine already uses (p254 argument, p255 result, trigger 44 cutscene...) are in `story/core/engine.dws`:
`import "story/core/engine.dws";` then `engine.arg = 5; call_routine(routine("choose_item"));`. Raw numbers also work anywhere:
`p110`, `w3` (a wide register), `trigger(232)`.

### `city { }`: the city's rules

`city { prosperity { } revival { } top_map { } shop_maps: [..]; arena_maps: [..]; start { } presence { } }` declares what the original keeps in C (prosperity, the File City top
map, the revival screen, the start state of a new game, the overlay map lists) and `npc Species slot K [autotalk] when CONDITION;` per screen (`screen(168..=179)` for a range; `flag(name)` names a flag of the program). A presence rule
is **compiled** for a slot the same program `place`s (an `IF` around its `LOAD_DIGIMON`/`SET_DIGIMON` in MAPHEAD; a flat `and` or `or` of triggers, flags and pstat
comparisons) and check-only for the original game's slots; presence blocks of several files merge by screen. `--exe story-state`
writes the table into MAPHEAD section 1260 (the original executable refuses it); `presence` is not compiled. Reference, table format, tools and the equivalence evidence:
`docs/mods/city-rules.md`; the original rules as DWS: `story/base/city/`.

### Flags and variables: allocation and collisions

- Unpinned names take the first free number of their pool, in declaration order, skipping pinned
  numbers (the same rule as the retired quest compiler, so migrated examples kept their numbers).
- A **pin** must lie in the free range; two names on one number, an exhausted pool, or a pin outside
  the range are errors (`alias` is the explicit way to name a game trigger).
- **`story.lock`** (`--lock FILE`, written with `--update-lock`): JSON `{flags, vars, temps}` of
  `module.name -> number`, append-only. A name that is in the lock keeps its number whatever the
  declaration order; new names never reuse a locked number. Commit it for anything that ships, so
  saves keep meaning the same thing.
- Lint: a flag or var that is never used, read but never set, or set but never read is a warning.

### Commands: every instruction has one

Every opcode of the interpreter is a command named like its mnemonic in lower case (`registry.py`, 79 opcodes): positional
arguments only, typed by operand kind, wide forms chosen automatically for ids above 255.

```
entity_walk_to(5, 100, -20, 0, 0);       set_obj_visibility(3, 1);          move_object_to(0, 3, 4, 10, 120, -40);
give_item(item("Meat"), 2);              call_routine(routine("choose_item"));   call_digimon_routine(routine("toilet"));
switch(p7, L1, L2, L3);                  data(1, 2, 3);                     show_textbox(text("a"), text("b"));
set_selection(L1, L2, text("opt1"), text("opt2"));                          end_selection();
```

Operand kinds: `p` pstat (`p7` or a declared var), `t` trigger (a number or a flag), `l` label, `e` entity (`tamer`, `partner`, an npc, a
number), item/species/tech typed ids, screens, scripts, sections and cards as numbers, `w` wide register, comparisons as strings
(`"=="`). The statements `say`, `give`, `walk`... of the tables below are sugar over these. `routine("name")` knows the 57
`CALL_ROUTINE` numbers (`choose_item`, `shop`, `save_machine`, `fade_to_white`...) and the 11 `CALL_DIGIMON_ROUTINE` ones;
`routine name = N;` adds one.

### Labels, jumps, loops, match, par

| Statement | Compiles to |
|---|---|
| `name:` / `goto name;` / `gosub name;` | a label, `JUMP_TO`, `JUMP_AND_LINK` (labels are local to one event; `gosub` returns at a `jump_return()`) |
| `unless (cond) goto L;` | `IF cond, else L` (the raw form of an `IF`) |
| `shared name { ... }` (in a `script` or `maphead` block) | code of the script that several events reach: `goto name;`, `gosub name;` (it ends with `jump_return();`), `unless (c) goto name;`, a `choice`/`set_selection` target. Compiled once, after the events, under the label `sh_name`; it ends like an event (`END_SECTION` unless its last statement jumps). The beautifier writes the code the original shares between sections this way |
| `shared name:` (a label inside an event) | a label every event of the script can jump to. For data the engine reads by position (the rows a jump table points to: the cups' `DATA` of scripts 102/168/209/213, MAPHEAD's shop texts), so the section keeps its layout |
| `sections 254, 5, 81 as old81;` (in a `script` or `maphead` block) | the script's section table, in order: an id is that section's event, `id as NAME` an entry whose code is `shared NAME { }` (a repeated id: the engine takes the first). The story build makes each script from its sources alone, header included; without the list the events go in source order. The beautifier writes the original header's list |
| `goto secN;` | the entry of section N of the same script (a section that falls into the next one, or jumps to another's start). Labels named `secN...` are reserved for this |
| `goto original(L);` / `gosub original(L);` ... | **deprecated** (a warning): a jump to label `L` of the disc's text. The story is built from the sources alone now, so there is no disc text to jump into; write the code as a `shared` block |
| `unless (c) break;` / `continue;` / `return;` | the guard form: `IF c, else <the loop's exit / its top / an END_SECTION>` (the beautifier writes it for `loop { head; unless (c) break; body }`) |
| `loop { }`, `repeat (n) { }`, `for i in 0..n { }`, `while (c) { }` | back jumps; `repeat`/`for` use a hidden temp variable per nesting level (constant bounds in original); `break`/`continue` work in all |
| `match (v) { 0 => ..., 1 => ..., _ => ... }` | a `SWITCH` when the cases are exactly 0..n-1 (n >= 3; with a bound check, because `SWITCH` clamps to the last label), else an `IF` chain; `v` is a variable, patterns are numbers or enum values |
| `match (v, clamp) { 0 => ..., 1 => ... }` | the original's `SWITCH` as it is: the arms are exactly 0..n-1 (n >= 2), no `_`, no bound check (a value past the end takes the last arm, as the engine does). The beautifier writes it for the 6 `switch` statements of the disc that stay in their section |
| `group anim { const idle = 0; ... }` | constants in a group are `anim.idle` (`story/core/scene.dws` uses it for the animation slots) |
| `par { walk(a, 1, 2); walk(b, 3, 4); }` | starts all the walks, then one `WAIT_FOR_ENTITY` for each |
| `return value;` | in a `sub` with a result |

The `IF` instruction folds left to right, and a clause **without** `and`/`or` replaces the result so far (6 original `IF`s do this);
the operator `~>` writes that: `(trigger(5) ~> trigger(6)) && trigger(7)`.

### Events (inside `script { }`)

| Header | Section | Runs |
|---|---|---|
| `on talk(npc) { }` | the NPC's entity number (5-12) | talking to / touching it; `self` is that NPC |
| `on enter { }` | 254 | entering the screen |
| `on step(t) { }` | 51 + t (t 0-28) | stepping on collision tile t |
| `on use(t) { }` | 80 + t (t 0-29) | pressing X on tile t |
| `section(n) { }` | n (1-254) | any other section |
| `section(n) replace { }` in `script 0` | n of 255-1999 | the unused script 0's global sections (`sec1220`-`sec1253`): only a section the script already has can be replaced (the build refuses a new one); the beautifier writes the 26 of the disc this way |
| `maphead { section(n) replace { } }` | n of MAPHEAD.SCN (0-254, 1230...) | **check only**: the compiler generates and checks it, `assemble` refuses (MAPHEAD is built from `maphead port`); the beautifier proves its sections this way |

Modifier after the header: `replace` (the original code of the section is not run) or `before` (default: the new code runs
first and the original follows unless you `return`). `after` needs an extended-save interpreter and is an error.
`npc name = N;` declares an entity of the script.

### Statements

| Statement | Instructions |
|---|---|
| `say(who, text...)` | `SET_DIALOG_OWNER` (always: every `say` statement is one dialogue box, and the engine sets the box up again at each `SET_DIALOG_OWNER`) + `SHOW_TEXTBOX` per page (the pages of one `say` are chained: `SHOW_TEXTBOX` followed by `SHOW_TEXTBOX` is one box whose pages go on without closing, which is how `showTextbox` reads it; `say(a, x); say(a, y);` are two boxes, `say(a, x, y);` one); text is wrapped with the real font widths (3 lines per page, 4 for `narrator`); several texts are several pages |
| `choice { text => stmt, ... }` | `SET_SELECTION`; one block per option, falls out at the end (triangle cancels) |
| `choice(open) { ... }`, `choice(narrator, open) { ... }` | the original's selection **without** `END_SELECTION`: the first option's code follows `SET_SELECTION` at once (no cancel path). With `cancel =>` (or `or cancel`) the cancel path is what follows `SET_SELECTION`, and the first option no longer does: the sections of the disc where a menu falls into other code (the tamer cancels into a scene's start) are written that way. 16 sections of the disc use the plain form |
| `choice(keep) { ... }` | a menu that does not set the dialog owner: it keeps the one that is set (the options of an earlier menu jump to a second menu with no `SET_DIALOG_OWNER`); `choice(keep, open)` too. 10 menus in 5 scripts |
| `choice { ... cancel => stmt }` | the code the triangle button runs (it follows `END_SELECTION`); without it the triangle skips the whole `choice` |
| `choice { ... "No" or cancel => stmt }` | the option that the triangle button also chooses (`END_SELECTION` jumps to its code) |
| `choice(narrator) { ... }` | whose dialog owns the menu (default `tamer`: `SET_DIALOG_OWNER TAMER` before `SET_SELECTION`) |
| `if (c) stmt else stmt`, `while (c) stmt`, `break`, `continue`, `return` | `IF`/`JUMP_TO`; `return` in an event is `END_SECTION` |
| `give(item, n=1)`, `take(item, n=1)` | `GIVE_ITEM`, `REMOVE_ITEM` |
| `give_bits(n)`, `take_bits(n)`, `merit(n)`, `give_card(n)`, `learn(tech)` | money, merit, cards, techniques |
| `f = true;` / `f = false;`, `v = 3;`, `v += 1;`, `v -= 1;` | triggers and pstats |
| `set_trigger(n)`, `clear_trigger(n)` | raw triggers (warns outside 717-799) |
| `music(n)`, `sound(bank, n)`, `warp(screen, exit: 0, section: 255)` | |
| `wait(30)`, `wait(2s)`, `wait(5 ticks)` | `DELAY` (20 ticks per second) |
| `battle();` | the NPC of the section fights you |
| `battle(foes: [a, b, c], escape: false);` | predefined enemies (up to 3); the result is `won`, `lost`, `fled` in conditions |
| `cutscene { ... }` | `SET_TRIGGER 44`, then the body. Nothing clears it: the engine does, at the start of the next script event (`scriptPauseGame`, `script_interp.c:2672`; it reads it just before, `:2659`, to decide whether the NPC turns to the tamer). Also `cutscene_start();` (the same) and `hide_hud();` (`FADEOUT_HUD 0`). It writes nothing else: none of the 14 sections that set trigger 44 on the disc writes `FADEOUT_HUD 0` or `UNSET_TRIGGER 44` beside it |
| `walk(who, x, z, camera: false)`, `run(...)` | `ENTITY_WALK_TO[_WITH_CAMERA]`; `let h = walk(...); await h;` waits for it |
| `await who;`, `await all;`, `await camera;` | `WAIT_FOR_ENTITY` |
| `camera_to(x, z, speed: 20)`, `camera_on(who, speed: 10)` | camera |
| `face(a, b)`, `rotate(who, angle)`, `animate(who, n)` | look at, set rotation (4096 = full turn), animation |
| `let g = spawn(species("X"), slot: 3, talks: false);` | `LOAD_DIGIMON` + `SET_DIGIMON`; `g` is the entity 5 + slot (warns in a talk section: a second `LOAD_DIGIMON` there hangs the game) |
| `remove(who)` | `UNLOAD_ENTITY` |
| `asm("INSTRUCTION args", ...)` | any `bytecode` instruction as it is; `text("key")` arguments become text rows |
| `let x = expr;` | a compile-time name, visible to the rest of the event |

Entities: `tamer` (`player`), `partner`, `narrator`, `camera`, `all`, the `npc` names, `entity(n)`.

### Conditions

`flag`, `!flag`, `trigger(n)`, `chests[2]`, `Group.flag`, `has(item("X"))` (at least 1) or `has(item("X")) >= 2`, `bits >= n`,
`has_card(n) >= 1`, `knows(tech("X"))`, `condition(bit)` (a partner condition bit), `stat(n) >= v` (the raw stat numbers), `w3 < 9`,
`is_recruited(species("X"))` (the `200+type` flag; `recruit(species("X"))` sets it), `~>` (restart),
`clock.year|day|hour|minute OP n`, `partner.is(species("X"))`, `partner.hp >= n` (also `off def speed brain max_hp max_mp mp
tiredness happiness discipline energy virus lifetime merit battles fled_battles tournaments_won tournament_wins`),
`chance(30)`, `won`/`lost`/`fled`, `var OP n`; `!` flips (comparisons get the opposite operator).
`v in [a, b, c]` (a variable against a list of numbers or ids, a `const` list works too) is `v == a || v == b || v == c`; it must come first or after
an `||`, never after an `&&` (the fold has no groups).
Combine with `&&` and `||`. The game's `IF` folds **left to right without grouping**, so a chain like
`a && b || c` is exact, but a group on the right (`a || (b && c)`) is an error: nest ifs instead.

### Typed ids

`item("Meat")`, `species("Greymon")`, `tech("Spit Fire")` (names from `docs/data/*.csv`, close matches are suggested; `Item.Meat`
also works), or the id number `item(38)`. `card(n)`, `screen(n)`, `track(n)`, `entity(n)` for the rest.
Passing a bare number where an item is expected is an error. Ids above 255 need the wide opcodes of the mod executable:
with `--exe original` the compiler says so at the line that uses them.

## Text keys and the text bank

`text("key")` is looked up in a **bank**: a JSON file `{ "key": value }` where value is a string (wrapped into
lines and pages for you), a list of strings (one page with exactly those rows) or a list of lists (several pages).
Banks load in this order, later wins: `text/us/dialogue.json` (the game's own text, **gitignored**),
`text/<lang>.json` (the project's), `<source>.<lang>.json` next to each `.dws` (`quest.en.json` for `quest.dws`), and `--text FILE`.
`page("a", "b")` builds a page from explicit rows. Plain string literals work for new text; keys are what you use
for anything that must be translatable or that is not yours to publish.

**The original dialogue is never committed.** `python3 tools/dws.py text-extract` disassembles *your*
`extracted/SCN/DG.SCN` and `MAPHEAD.SCN` and writes `text/us/dialogue.json`: one key per **utterance** (a text box: a run of
`SHOW_TEXTBOX` in a row, with its pages; a label between two of them starts a new one) and per **menu option**, derived from the
position (`docs/mods/translating.md`): `s<script>.sec<N>.u<i>` (`s002.sec6.u3`: script 2, section 6, utterance 3),
`s<script>.sec<N>.m<k>.o<j>` (option j of menu k of that section) and `m<section>.u<i>`, `m<section>.m<k>.o<j>` for MAPHEAD (`m1230.u0`).
3 927 utterances (4 514 pages, 8 586 rows) and 799 options of 330 menus. The US bank gives an utterance its exact pages, so the
build makes the disc's bytes; another text source (`text/<source>/`) may give a string, which the compiler wraps into rows and
pages with the target font's widths. `{player}`, `{partner}`, `{color 6}`... stay in the text. A missing key says so; a missing
original bank says "extract the texts from your own disc first".

`python3 tools/dws.py text-keyed 2` prints script 2 in the **lossless keyed form**, `script 2 lossless { ... }`: every instruction verbatim,
every utterance one `text("key")` below its first `SHOW_TEXTBOX` (the key gives the pages back), every option `text("key")`, so the
file holds no game text. `maphead lossless { }` does the same for MAPHEAD. Compiled with the bank, the
result is byte-identical to the disc for **all 222 scripts and MAPHEAD**. The decompiler builds on this form.

## The port form and the decompiler

`python3 tools/dws.py decompile 2` writes a whole script as one typed statement per instruction:

```
script 2 port {
    tail;                                  // keep the garbage tail bytes of the disc slot
    entry 254 sec254;                      // the section table, in order: entry ID label;
    entry 5 sec5;  ...

sec254:
    store_random(p110, 99);
    unless (p110 <= 24) goto L1;
    spawn_item(item("Digimushrm"), 46, 45);
L1:
    ...
sec6:
    set_dialog_owner(6);
    show_textbox(text("s002.sec6.u0"));     // a key of text/us/dialogue.json, never the text (all its pages)
    set_selection(L4, L12, text("s002.sec6.m0.o0"), text("s002.sec6.m0.o1"));
    end_selection();
```

`maphead port { }` is the same for MAPHEAD. A port block replaces the whole script and may `include "file.dws";` files that contain
`part { ... }` (statements); the include order is the address order. The decompiler's own checks: `dws.py roundtrip` (one file per
script) and `roundtrip --layout` (the `story/base` directory) compile the output and compare it with the disc: **222 of 222 scripts and
MAPHEAD byte-identical, 39 797 instructions as typed statements, 0 `asm()`**. Conditions are written
with the same atoms as new code (`trigger(232)`, `p110 <= 24`, `has(item("Meat")) >= 2`, `bits >= n`, `stat(9) >= 3`), `p`-numbers
are raw pstats, ids have names where the name resolves back to the same id (`item("Meat")`) and numbers otherwise.

What the port form is not: structured (no `if/else`; control flow is `unless ... goto`) and not named (flags are `trigger(232)`).
Those are optional passes on top, each checked by the same recompile.

`dws coverage` measures all this against the original: 36 365 instructions, **74.0 % expressible without `asm()` before, 100 % now**;
`dws-missing-constructs.csv` ranks what was missing by occurrences.

## Generated base story

`story/base` is committed source: readable DWS and Python views with text keys,
never disc dialogue. `story-build` compiles it and the selected mods; it does not
regenerate an existing base. `story-base --reproduce` compares a fresh generation
from the player's USA disc with the committed files, allowing only reviewed edits
whose original and authored hashes and reasons are pinned in `authored.json`.
`story-base --refresh` explicitly replaces generated sources; review its changes
before committing. Use a Python mod for a new quest. `story-verify` compares
supplied containers; positional jump tables must preserve layout as well as flow.

New mods use Python handlers, named state and keyed translations as described in
[the story language](story-language.md). Existing DWS sources and overrides are
accepted for compatibility with a deprecation warning. The retired `.quest`
language is not a supported authoring workflow.

## Compiler and build integration

The Python front end lowers into the DWS compiler. `tools/dws/gen.py` emits events;
`tools/dws/backend.py` handles sections, NPC placement, map edits and target limits;
`tools/dws/bytecode/__init__.py` assembles the bytecode. See [bytecode and containers](scripts.md)
for container growth and the round-trip check.

## If DG.SCN grows

Container growth and script RAM limits are documented in
[bytecode and scnasm](scripts.md#if-dgscn-grows).

The derive story step runs the recipe's sources for the selected language, font
and story variants. [Building](../building.md) describes the integrated disc;
[derive](../derive.md) describes output manifests and ordering. These build paths
manage script assembly and disc relayout automatically.
