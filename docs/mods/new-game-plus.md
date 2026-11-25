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

Saved pstat 20 (`engine.new_game_plus_count`) counts the New Game+ runs this save has started (up to 255). Nothing
reads it yet.

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
