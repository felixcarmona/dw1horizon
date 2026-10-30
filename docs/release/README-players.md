# Digimon World: Horizon - how to install it

This mod changes Digimon World (PlayStation). It does **not** include the game: you supply **your own four discs** and patch your copy of Digimon World, and the patcher makes a new, modded disc image. Your original file is never changed.

The release is the "everything" version: every feature of the mod, the story mod *What the island forgot*, English, Spanish, Brazilian Portuguese, French, German, Italian, Japanese and Catalan, and every new Digimon (the OPTIONS menu chooses).

The browser builder at [dw1horizon.com](https://dw1horizon.com) uses the same four
discs and needs no Python installation. This page describes the command-line release.

## Language beta

The new translations are beta drafts with partial editorial review. They need
contextual linguistic and in-game review. This is our own Japanese adaptation
from our Spanish text; it does not reuse the original Japanese script. Catalan
is translated directly from our Spanish. The first launch asks for a language
with native names and flags when no saved preferences exist. Saving remembers
it; OPTIONS can change it later. Without a saved game it asks again on restart.

## Bring your own disc

You need a copy of one of these discs, dumped from your own disc as a `.bin` + `.cue` (raw image, "MODE2/2352"),
exactly as listed on redump.org. The patcher recognises which one you have and checks it.

| Disc | Serial | redump.org | SHA-1 of the `.bin` |
|---|---|---|---|
| Digimon World (USA) (also the Greatest Hits disc) | SLUS-01032 | http://redump.org/disc/14957/ | `5611645da66183e30d11fb6c11a2784ff47e1fdb` |
| Digimon World (Europe) | SLES-02914 | http://redump.org/disc/4264/ | `9c2922445280309f3d9c62bb70b57d6ad6da015a` |
| Digimon World (France) | SLES-03435 | http://redump.org/disc/28228/ | `adfaa62f6756d1e363c50bd414d60a45f1f864b2` |
| Digimon World (Germany) | SLES-03434 | http://redump.org/disc/3059/ | `408fa08bf1b8a72f421d6caa02f146cf43513133` |
| Digimon World (Spain) | SLES-03436 | http://redump.org/disc/10761/ | `b90a8efa596771ad84f678d64786fcc5fdd65889` |
| Digimon World (Italy) | SLES-03437 | http://redump.org/disc/46143/ | `1478a99829fe3c385d8b342ced861f1fa1be3188` |
| DigimonWorld (Japan) (Rev 1) | SLPS-01797 | http://redump.org/disc/37502/ | `1d10389deee8c9849136623785c256071f2f9473` |

The first Japanese pressing (the disc before Rev 1) does not work: some of its models, effects and maps differ from
every other release. Already-modified copies (another patch or hack applied) and trimmed or converted images do not
work either. The mod's features and selected translations are shared across bases.
Opening movies and some title artwork keep your disc's regional content.

The package contains build tools, authored changes and binary differences applied to
files from your own discs. Models, maps, scripts and sound banks are rebuilt locally;
program files use differences against your regional disc. Every result is checked
against the release hashes. Reconstruction and checksum equality do not establish
copyright provenance: the package's publication audit must pass before distribution.
See the source repository's patcher guide for the audit's scope and remaining limits.

## What you need

1. Your Digimon World `.bin` and `.cue` (see above), plus your **Digital Card Battle**, **Digimon World 2** and
   **European Digimon World 2003 or Japanese World 3** image (USA World 3 is unsupported).
   See the [generated supported-release matrix](../data/source-releases.md). The imported Digimon are generated from these images on your computer.
2. **Python 3.10 or newer** (tested with 3.10, 3.11, 3.12 and 3.14).
   Install it from [python.org](https://www.python.org/downloads/) or your operating
   system's package manager. On Windows, tick **Add python.exe to PATH**.
3. The patcher and bundled replay use only Python's standard library; no
   additional Python packages are required.
4. Several GB of free disk space for the output image and temporary build files,
   plus about 2 GB of memory. Output size depends on the release; temporary files
   are removed after the build.
5. A PlayStation emulator that loads `.cue` files, for example DuckStation or PCSX-Redux.

## Step by step

1. Unzip the release into a folder. It contains `dwpatch.py`, `isowriter.py`, `manifest.json`, `everything.dwp`, the
   `bases` and `bundle` folders, `audit.txt` and this README. Keep them together.
2. Open a terminal in that folder:
   - Windows: open the folder, click the address bar, type `cmd` and press Enter.
   - macOS: right-click the folder in Finder, "New Terminal at Folder".
   - Linux: right-click, "Open in Terminal".
3. Run (put the path to **your** `.cue` between the quotes; you can drag the file into the terminal window to paste
   its path):

   ```
   py dwpatch.py apply "C:\Games\Digimon World (USA).cue" --source-disc "dcb=C:\Games\Card Battle.bin" --source-disc "dw2=C:\Games\World 2.bin" --source-disc "dw2003=C:\Games\World 2003.bin"
   ```

   On macOS and Linux type `python3` instead of `py`.

   Replace all four paths with your own files. Keep the three `--source-disc` options: the patch contains our model
   edits, and the patcher applies them to models converted from your own discs.
4. Wait. A progress bar shows what is being done and about how long is left:

   ```
   Digimon World Mod (everything): patching Digimon World (USA).bin
   [############..................]  41%  building the new maps  1:12 so far, about 1:45 left
   ```

   It checks your disc, reads the files it needs from it, builds the modded files (the Digimon models, the maps, the
   story, the translated images...), writes the new disc and checks it. How long it takes depends on your processor;
   converting the 175 imported Digimon adds several minutes to the earlier releases' build time. At the end:

   ```
   [##############################] 100%  done in 2:55

   Done. Load this file in your emulator:
     C:\Games\patched\Digimon World Mod (everything).cue
   (and keep Digimon World Mod (everything).bin next to it; what was done is in Digimon World Mod (everything).log)
   ```

5. Open that `.cue` in your emulator. Keep the `.bin` next to the `.cue`.

The modded disc goes into a `patched` folder next to your disc. Want it somewhere else? Add `-o FOLDER`:
add `-o "C:\Games\Modded"` to the command above.

Every detail of what was done (each step, its time, the checks) is written to a `.log` file next to the modded disc.
`--verbose` shows those details on the screen instead of the bar.

## If something goes wrong

The patcher stops, says why, and says where the log is. Nothing is written over your disc, and a modded disc is only
written once every file has been checked.

| Message says | What to do |
|---|---|
| "is not a clean ... disc" | Your copy was changed (another patch or hack, a save or cheat tool) or is a bad dump. Use an untouched dump of your disc; it must match its redump.org page (table above). |
| "has ... bytes" / "looks like the right game but a different or modified dump" | The image was trimmed, padded or patched. Make a clean dump. |
| "the first pressing of SLPS-01797" | That Japanese disc cannot be used (see "Bring your own disc"); any other release can. |
| "is Digimon World 2" / another game, or "This release needs one of: ..." | Use one of the discs in the table above. |
| "is a 2048-byte-per-sector ISO" | Dump the disc again as `.bin`/`.cue` (raw, 2352 bytes per sector). |
| "is a CHD" / "is a 7z archive" / "is a zip archive" ... | Extract or convert it to `.bin`/`.cue` first (for CHD: `chdman extractcd -i game.chd -o game.cue`). |
| "the cue sheet names 2 files" | Digimon World is one data track: use a redump-style single `.bin`. |
| "points to ..., which does not exist" | The `.cue` names a `.bin` that is not there: rename the `.bin` back, or edit the `.cue`. |
| "needs Python 3.10 or newer" | Install a newer Python from python.org or your operating system's package manager. |
| "is damaged" (about `everything.dwp`) | Download the release again. |
| "came out different from the release" / "building the files from your disc failed" | The `bundle` folder was changed or is incomplete: unzip the release again and use the `dwpatch.py` that came with it. If it happens again, send us the `.log` file. |
| "the output would overwrite your original disc" | Choose another folder with `-o`. |
| "No space left on device" | Free some disk space (see step 4 of "What you need") and run it again. |
| `py` / `python3` is not recognised | Install Python (step 2 of "What you need") and, on Windows, tick "Add python.exe to PATH". |

To check your disc without patching: `py dwpatch.py check "Digimon World (USA).cue"`.

## Saves

Use the emulator's memory cards as usual. Published Horizon saves are checked for compatibility during release packaging.
Keep a copy of your memory card before switching builds. Emulator save states
hold the old executable and cached disc offsets; boot the new disc and load a
memory-card save instead.
