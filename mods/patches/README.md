# mods/patches: the C patch series

The single series of C changes on the decompilation (`decomp/`, at the commit the repository pins), applied with
`git am` in the order of [`series`](series), one patch file name per line. The series is linear: a change to an earlier
patch is a new patch on top. [index.md](index.md) has one row per patch: what it does and what it costs the main
executable; each patch's commit message describes its change in detail.

```
tools/mods.sh prepare [mods|int]   # a working copy with the series applied: mods = the core (the patches before the
                                   # first merge patch), int = all
tools/mods.sh build [mods|int]     # build it with GCC (Docker); FPS=20|30|60, FONT=original|a|b override the defaults
tools/mods.sh save [mods|int]      # export the commits made in the working copy as new patches at the end of the series
python3 tools/patch_series.py check --apply   # series against the files, then the whole series on the pinned decomp
```

Flow: `prepare` -> edit in `build/decomp-int/src` -> `git commit` there -> `save` -> `build`. `tools/build-full.sh` makes
the full disc.

**Heap.** Every byte a patch adds to the main executable comes off the heap the screens load their models into; too
little and a screen never finishes loading. Measure `main_BSS_END` before and after a patch and keep data that is not
needed every frame out of the main executable; `tools/build-full.sh` stops when a screen would be short
(`tools/heapcheck.py`).

**The font patch** (`Font-extra-glyphs-for-Spanish-and-Catalan-text-and-p.patch`, number 0024 in older texts) is the one
exception to "a change is a new patch on top": it is regenerated in place when a glyph is appended to
`tools/font/extra.txt` (`font_extra.h` is its own file, which no later patch touches; `docs/mods/font.md` "Adding a
glyph").

## Adding a patch

A patch has no number: its file is `<name>.patch`, the name being its commit subject as `git format-patch` writes it,
and its place is its line in `series`. `tools/mods.sh save` does both: it exports each new commit of the working copy,
drops the number `format-patch` puts in front, refuses a name that is already taken (reword the commit's subject),
appends the name to `series` and a row to the end of [index.md](index.md) with the subject as its text. Rewrite that
row: what the patch does and what it costs the main executable; the **was** column stays empty.

```
| `<name>.patch` |  | what it does | main executable cost |
```

By hand, in the working copy: `git format-patch -N -1 HEAD`, set the file's second line to `From: Horizon authors <>`
as in the other patches, move it here without its number, and append its name to `series` and its row to `index.md`.

Refer to a patch by its name, not its position: positions move when the branches merge.

A branch that still has a numbered patch from before the files lost their numbers (`NNNN-<name>.patch`): after
rebasing it, `git mv` the file to `<name>.patch` and append it to `series` and `index.md`. The tools that apply the
series stop at a patch file that `series` does not list.

## Merging branches

`series` and `index.md` merge with git's `union` driver (`.gitattributes`): two branches that each append a patch keep
both lines, the base branch's first, without a conflict, in a local merge or rebase. GitHub's merge button does not
use merge drivers: when a pull request shows a conflict only in these two files, `git rebase origin/main` in the branch
resolves it by itself; push the rebased branch (GitHub runs no pull-request check while it reports a conflict).

The union driver does not know C: two patches that change the same lines merge cleanly here and fail when applied. The
pull-request check (`.github/workflows/patches.yml`) runs `tools/patch_series.py check --apply` on the merged result,
so that failure shows before the merge; regenerate the later patch on top of the other one (`tools/mods.sh prepare int`,
redo the commit, `save`). The check also fails when a union merge leaves a name twice, or two versions of one row of
`index.md` (both branches edited it): keep one by hand. Append rows; edit an old row in a change of its own.

Applying cleanly is not the whole proof: two patches can apply and still break each other at run time, and two
branches can still take one story flag number (`docs/mods/compatibility.md`). Build the merged result before a release.

## Notes that are not patches

The localized Ogre Tunnel takeover sign is a map-art change in
`tools/localize/signs.py` and `content/localized/signs/delta`, with no engine
patch or resident executable growth. See [game languages](../../docs/mods/language.md).
Whamon's timed return at the city dock is a story-only fix, using the existing
spawn instruction; it adds no engine patch or resident executable bytes. See the
[shore story notes](../../story/mods/what-the-island-forgot/arcs/shore/README.md).

Patch 0290 is removed: species 224 now uses the native MetalGreymon field programs.
