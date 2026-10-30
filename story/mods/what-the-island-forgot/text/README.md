# text

`en.json`: every line of the story by key, written by `python3 tools/dws.py text sync what-the-island-forgot` from the strings in
the Python files listed under `sources` in `mod.toml` (`early-game.py`, `arcs/*/*.py`, `district/*.py`, `city/*.py`; the same
files `build.sh` compiles). The key is the hash of the words (`what-the-island-forgot.bbe10652`); `_where` says which file, line
and handler, and who speaks. The build reads the words from the sources; a translation is `<lang>.json` with the same keys
(no text of the original game), used by `STORY_LANG=<lang>` / `--lang <lang>` (docs/mods/translating.md).

`text sync` lowers the files like the build does, so it needs the story's new screens: run it with
`SCREEN_CONTENT=build/<name>-maps/screens DWS_MAPS=$PWD/build/<name>-maps/retouch` (the output of `build.sh` step 1),
or it stops at "screen N has no step trigger".
