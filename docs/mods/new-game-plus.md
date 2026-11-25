# New Game Plus

Once the island is saved, the save machine in Jijimon's house (screens 218 and 205) offers **New Game+** next to saving
and the rite of return. Jijimon explains it and asks twice; then the adventure starts again from the questions of the
first day. Nothing is written to the memory card: the old save stays until the player saves the new run over it.

| Carries over | Starts again |
|---|---|
| The Digimon ever raised (the chart) | The partner: a new one from Jijimon's questions |
| The medals, and the counters behind them: cups won, tournament wins and losses, fish caught, curling cups | The city: every recruit and its prosperity |
| The cards, old and new | Bits, merit points, and the bag |
| The techniques learned | |
| The tamer level | Every story flag, chest and gym upgrade |
| The play time, the tamer's name and look, the options | The date |
| The Digimon registered for VS battles | |

The game beaten (trigger 50) starts clear, so the whole story and its ending play again. Trigger 642
(`engine.new_game_plus_unlocked`) is set instead and keeps the option at the machine from the first day of every later run.

## How it works

- The house scripts (`use5` of scripts 178 and 165) add the row when `game_beaten` or `new_game_plus_unlocked` is set;
  it jumps to section 75 of library script 212, which sets pstat 126 (`engine.new_game_plus`, unsaved) and calls routine
  `save_machine`.
- `openSaveMachine` sees pstat 126 and calls `modNewGamePlusReset` (MENU_REL): it builds the default save in
  `SAVE_FILE.saves[0]` like NEW GAME does, copies the kept fields into it from the live game, and loads it. The kept
  triggers are the macro `NG_PLUS_KEPT` in `main_menu.c`. The battle registrations (from offset `0x500` of the buffer) and
  the tamer's look and extra cards are left as they are.
- It then sets `MOD_CHEATS_TRANSITION` to 3. The main loop leaves the world as it does for a save loaded from Cheats,
  fades out and enters the new-game path (`MAIN_STATE` 0).

A state that should carry over needs its place in `initializeDefaultSavegame`'s New Game Plus block; anything else is
reset by default.
