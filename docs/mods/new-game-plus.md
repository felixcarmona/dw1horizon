# New Game Plus

Once the island is saved, the save machine in Jijimon's house (screens 218 and 205) offers **New Game+** next to saving
and the rite of return. Jijimon explains it and asks twice; then the adventure starts again from the questions of the
first day. Jijimon does not ask boy or girl, the tamer's name or the Look page: the tamer keeps the name and the look of
the run before, and the questions go from the seven about the partner straight to naming it. Nothing is written to the memory card: the old save stays until the player saves the new run over it.

| Carries over | Starts again |
|---|---|
| The Digimon ever raised (the chart) | The partner: a new one from Jijimon's questions |
| The medals, and the counters behind them: cups won, tournament wins and losses, fish caught, curling cups | The city: every recruit and its prosperity |
| The cards, old and new | Bits, merit points, and the bag |
| The techniques learned | |
| The tamer level | Every story flag, chest and gym upgrade |
| The play time, the tamer's name and look, the options | The date |
| The Digimon registered for VS battles | |

The game beaten (trigger 50) starts clear, so the whole story and its ending play again. Every New Game+ gives the medal **New Beginning**
(medal 21, trigger 643); saving the island again in such a run gives **Second Journey** (medal 22, trigger 644) in the
homecoming scene, after the Ending medal. Trigger 642 (`engine.new_game_plus_unlocked`) marks a run that came from a
New Game+. The option at the machine needs the game beaten in the current run, every time: a new run must save the
island before it can restart again.

Saved pstat 20 (`engine.new_game_plus_count`) counts the New Game+ runs this save has started (up to 255). It is the
number of rewinds each egg may make (below).

## How it works

- The house scripts (`use5` of scripts 178 and 165) add the row when `game_beaten` is set;
  it jumps to section 75 of library script 212, which sets pstat 126 (`engine.new_game_plus`, unsaved) and calls routine
  `save_machine`.
- `openSaveMachine` sees pstat 126 and calls `modNewGamePlusReset` (`main_menu.c`, resident: MENU has no room left, and
  MENU is loaded while it runs). It builds the default save in `SAVE_FILE.saves[0]` like NEW GAME does, copies the kept
  fields into it from the live game, and loads it. The kept triggers are the macro `NG_PLUS_KEPT`. The battle
  registrations wait in `saves[1]` (the backup copy the next save rewrites); the tamer's look, the extra cards and the
  raised species bits wait on the stack.
- With trigger 642 set, `newGameStateMachine` (`script_menu.c`) does not clear the tamer's name at state 0, and
  `lookPageQuiz` (`game_menu.c`) sends state 0x30 straight to 0x18, naming the partner: no boy or girl, tamer name or
  Look page.
- It then sets `MOD_CHEATS_TRANSITION` to 3. The main loop leaves the world as it does for a save loaded from Cheats,
  fades out and enters the new-game path (`MAIN_STATE` 0).

A state that should carry over needs its place in `modNewGamePlusReset`; anything else is
reset by default.

## Rewind

In a run that came from a New Game+ (trigger 642), the save machine also offers **Go back**: the partner returns to the
form it had before, exactly as it was the day it became the current one. Its stats, the lifetime it had left, its age
and its weight are the ones it arrived with, with HP and MP full; the techniques it has learned stay; care mistakes,
battles and the hours at its level start from 0. Then it must be trained again, and it can evolve into another branch. Jijimon explains it,
says how many times this egg can still go back, and asks twice.

- **Uses.** Each egg may go back as many times as the save has started New Game+ runs (pstat 20). Rebirth and a new
  New Game+ start a new egg and its count.
- **One form back.** The line keeps the form before and the current one (the save has room for no more): after going
  back, the partner must evolve again before it can go back once more. A partner whose form the machine did not see
  arrive (Sukamon, a form from before this feature, a save without the record) is refused: "the machine does not
  remember".
- **Tamer level.** The roll for a tamer level on reaching Champion, Ultimate or Mega is given once an egg: reaching a
  level again after going back out of it gives no second roll, and going back gives none. The lifetime bonuses of
  Ultimate and Mega are given again, since going back took them away.
- **Sukamon.** Turning into Sukamon is not written (the King of Sukamon turns the partner back), and neither is his
  way back. Forms after a lost life (Bakemon, SkullGreymon...) are.

### How it works

- `MOD_PARTNER_LINE` (`mod_qol.c`) holds the state the current form and the one before arrived with. A new game
  (`main.c`) and a rebirth (`evolution.c`) start it with `modPartnerLineStart`; the end of `EVL_applyEvolution`
  (`lineArrived`, `evl.c`) has `modPartnerLinePush` write each new form on top, or, on a rewind, puts the saved state
  back itself (in the EVL overlay, to keep the heap). It is saved as record `0x0010`, the struct as it is in RAM
  ([save format](../reference/save-format.md)).
- The house scripts (`use5` of scripts 178 and 165) add the row when trigger 642 is set; it jumps to section 76 of
  library script 212. When New Game+ is on the menu too, Rebirth and the rewind sit under a Partner row: a menu box
  draws 4 rows.
- `CALL_DIGIMON_ROUTINE 13` (`rewind_check`) tells the script in p254 whether it can (0 does not remember, 1 none
  left, 2 yes, 3 yes and the egg has not gone back yet) and in p253 (`engine.rewind_left`) how many are left. Routine
  14 (`rewind`) sets `pending` and starts the ordinary evolution scene into the form before. While `pending` is set
  `EVL_applyEvolution` gives no tamer-level roll; its stat gains and lifetime bonuses run as usual and `lineArrived`
  then overwrites them with the saved state. HP and MP are set full rather than clamped: the clamp did not fit in
  EVL.
- Heap: the resident part (`modPartnerLinePush`, `modPartnerLineQuery`, the 44-byte line) would cost 560 bytes; cutting
  `SEQ_BUFFER_SIZE` from 0x7400 to 0x7288 (4 bytes over the largest music font's SEQ block) pays 376 of them. The
  nine-language build goes from 184,112 to 183,920 bytes of heap, and screen 207 keeps 112 bytes (304 before).
- Section 76 explains it in full (`rewind.how_1`-`how_4`) while the egg has not gone back yet (routine 13 answers 3),
  and in one line after that.
- So that a player learns of it at all: in the homecoming scene after the ending (script 162, File City) Jijimon calls
  the tamer to his machine (`ngplus.hint`). The first use of the machine after that (`use5` of scripts 178 and 165)
  has Jijimon tell what it gained, New Game+ and the rewind (`ngplus.intro_1`, `intro_2`), once per save: trigger 648
  (`machine_new_explained`) is in the range New Game Plus keeps. His New Game+ explanation and farewell
  (`ngplus.explain`, `ngplus.go`) mention the rewind again.
