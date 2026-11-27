# Horizon Play

Horizon Play lets players start the game without installing or setting up an emulator. It is a small program
(`tools/player/horizon_play.c`, SDL2 + OpenGL) that loads the [SwanStation](https://github.com/libretro/swanstation)
libretro core and boots the patched disc with the free OpenBIOS. Its settings are fixed:

| Setting | Value | Why |
|---|---|---|
| RAM | 8 MB | extra heap headroom; the game still runs in 2 MB ([real hardware](../README.md)) |
| CPU | 250 % | smoother play; the title screen's settings panel detects both and hides itself |
| Renderer | OpenGL (GLES 3 on Android), internal resolution = display height / 240 (2x-8x, Android 2x-3x; the menu's settings or `--scale N`) | sharp 3D at full screen |
| BIOS | OpenBIOS (`system/openbios.bin`), no fast-boot patch | no Sony BIOS is needed or shipped |
| CD | reads 8x, seeks 10x (`CDROM_ReadSpeedup` 4, `CDROM_SeekSpeedup` 10) | loads take about half the time; the core keeps music and movie sound at 1x |
| Memory card | slot 1, `duckstation_shared_card_1.mcd` in the user's data folder, written by the program each second it changed and when the app goes to the background | survives updates of the app |
| Screen | a resizable 4:3 window with the mouse cursor shown (a left click shows the touch pad and presses what is under the cursor; a Mac trackpad's touches are not taps); F11 / Alt+Enter toggles full screen (`--fullscreen` starts in it); Android: full screen | |
| Pace | the screen's refresh (vsync); near the console's 59.82 Hz the sound is stretched by under half a percent to follow it, steering its queue to 60 ms. A frame the machine was too slow for (heavy loads) is caught up: the next one runs without being shown | no stutter in the music, no missed refreshes |

The program carries no game data. It plays the disc that the patcher builds from the player's own disc.

## Where players get it

- **Windows and macOS:** inside the desktop patcher (on Windows with the Visual C++ runtime's three DLLs beside
  `horizon-play.exe`, which the core needs and a clean Windows lacks) (`desktop.yml` builds it and passes `--player` to
  `tools/patcher/app/build.py`). The patcher uses it for the installers it makes (no Play button: the player
  installs the game with one of them, or plays the disc image in an emulator).
- **Linux:** `Horizon-Play-Linux-x86_64.tar.gz` (`player.yml`), built on Ubuntu 22.04. Run
  `./horizon-play DISC.cue` once. With no argument it opens the last disc it played.
- **Android:** after a build, the desktop patcher's **Android app (.apk)** button writes `<disc>.apk` next to the disc
  (`desktop.make`, `tools/patcher/apk.py`; the template is the release asset `Horizon-Play.apk`, downloaded on demand). It is Horizon Play for Android (`tools/player/android`, arm64,
  Android 7+) with the built disc added as `assets/horizon.bin`, stored and page aligned. The player copies it to the
  phone and installs it: the game starts at once, with nothing to choose. The app reads the disc in place, through the
  core's VFS (`--embedded APK OFFSET SIZE`), so the phone keeps one copy. The patcher signs it (APK Signature Scheme
  v2, standard library only) with one shared key, `tools/patcher/android-key.json`, public on purpose: it protects
  nothing, it only makes every APK, from any computer, install over any other and keep the saves. An APK signed with
  another key (`apk.py --key`) has to replace the app; Android then offers to keep its data (`hasFragileUserData`). Saves, logs and options live in
  `Android/data/com.dw1horizon.play/files/saves`. Each time the card is written the app also copies it to
  `Documents/Digimon World Horizon/Digimon World Horizon.mcd` (MediaStore, no permission on Android 10+; Android 7-9
  ask once for storage) when it holds a save, which an uninstall leaves on the phone; a new install cannot write over
  the old copy, so its own is `Digimon World Horizon (1).mcd` and so on. Android 11+ gives a new install no access to files
  an old one made, so the copy is not read back on its own: a start with no card in the saves folder first offers
  IMPORT (the file picker, opened at that folder) or NEW GAME, then the touch or controller question. The template APK alone (`desktop.yml`'s `horizon-play-apk`
  artifact) asks once for a patched `.bin` and copies it into the app's folder.

OpenBIOS needs about 940 frames to reach the game's first picture (1800 without the fast CD). Horizon Play runs those
frames as fast as the machine can, with no sound and the screen refreshed now and then, and returns to normal speed at
the first lit picture after frame 400 (frame 3000 at the latest): about 3 seconds on a PC, 8-9 on a mid-range Android
handheld. `--no-fast-start` boots at normal speed.

## Building

```
python3 tools/player/build.py --out build/player/bundle            # Linux (needs gcc-mipsel-linux-gnu for OpenBIOS)
python tools/player/build.py --openbios openbios.bin --out ...      # Windows / macOS (an OpenBIOS built on Linux)
python3 tools/player/build.py --universal2 --openbios ... --out ... # macOS, Apple silicon + Intel
python3 tools/player/android/build_apk.py --out Horizon-Play.apk  # Android template (ANDROID_HOME, NDK, JDK 17; no Gradle)
python3 tools/patcher/apk.py Horizon-Play.apk DISC.bin OUT.apk   # the template with a disc inside
```

It checks out SwanStation and OpenBIOS (PCSX-Redux's `nugget`) at the commits pinned in `build.py`. It builds the
core, OpenBIOS (with `OPENBIOS_SHELL=shell`: the default shell gave a black screen) and the program, with SDL2
fetched by CMake at a pinned hash and linked statically.

Test flags: `--windowed` (the default; kept for old launchers), `--frames N` (stop after N frames), `--press "frame:button:len,..."` (libretro joypad ids),
`--screenshot FILE.ppm`, `--no-disc` (boot the BIOS alone), `--set KEY=VALUE` (override a core option),
`--touch` (the touch pad from the start), `--first-start` (ask touch, controller or keyboard again), `--ask-card` (the new install's IMPORT / NEW GAME
question), `--window WxH` (a window
of that size), `--no-fast-start`.
`HORIZON_PLAY_DEBUG=1` prints the core's log. The saves folder also gets `horizon-play.log` (the core's log, the
OpenGL version and the speed every 30 seconds) and reads `options.txt` (`KEY=VALUE` lines, core options to override).

## Controls

Keyboard: one of three layouts, chosen on the keyboard screen of the menu (below), or the player's own:

- **RetroArch** (the default): arrows, Z Cross, X Circle, A Square, S Triangle, Q/W L1/R1, E/R L2/R2, Enter START,
  Backspace or Right Shift SELECT.
- **DuckStation** (its default keys; its left stick's W/A/S/D move the D-pad here): arrows or W/A/S/D, K Cross,
  L Circle, J Square, I Triangle, Q/E L1/R1, 1/3 L2/R2, Enter START, Backspace SELECT.
- **ePSXe**: arrows, Z Cross, X Circle, S Square, D Triangle, W/E L1/R1, Q/R L2/R2, V START, C SELECT.

Any pad SDL knows is laid out like a PlayStation pad and read by position, whatever its labels say: the bottom face
button is Cross on every pad, a Nintendo-layout one too. The left stick also moves. One Android handheld's built-in
controller (USB 2022:3001), whose buttons SDL reports swapped, gets its own defaults until `controls.txt` has `pad`
lines. Any other joystick works too, read raw: buttons 0-3 Triangle, Circle, Cross, Square, 4-7 L2, R2, L1, R1, 8-9 SELECT, START, the first hat and the
first two axes as the D-pad. The first time such a joystick is connected, the button setup below opens by itself
(after the first start's question) to fit it to its own layout; once set, `joy device=` in `controls.txt` keeps its
SDL GUID and it is not asked about again. A phone's tilt sensor is not taken for a joystick.

**The menu:** SELECT and START pressed together, at any moment (neither reaches the game), the round button at the
top of the touch pad, or on a computer Escape or a right click (F11 or Alt+Enter switch full screen). The game waits under it. It shows big pictures, each with a word in English under it (a 5x7 font drawn into the overlay's texture); a tap, the mouse
or the pad's arrows with Cross, Circle or START choose, Triangle (or Escape) goes back:

- ▶ back to the game.
- 🎮⌨️ the controls: two cards, as at the first start. There is no touch card: a tap anywhere (or a left click on a
  computer) shows the touch pad.
  - **CONTROLLER**: ✔ keep its buttons, or ✎ set them (below).
  - **KEYBOARD**: a drawn PlayStation controller with the key of each of its 14 buttons beside it, and under it the
    cards RETROARCH, DUCKSTATION, EPSXE and CUSTOM. Moving between the cards shows each layout's keys on the
    controller; the card of the layout in use has a check mark and is chosen first (CUSTOM when the keys match no
    layout). Choosing a layout uses it at once and saves it. CUSTOM asks a key for each button in turn, the button lit
    on the controller and a ten-second bar under it; after that, or at any moment, a click or tap on one button (or
    the arrows and Cross) asks a key for that one alone. A key already on another button moves to the button being
    set. Escape and F11 cannot be taken. Escape or the back arrow stops the asking.
- 💾 the memory card: export or import. On Android both open the system's file picker. On a computer, export opens
  the saves folder (the card is `duckstation_shared_card_1.mcd`) and import waits for a card file dropped on the
  window. An import takes any raw 128 KB PlayStation card (`.mcd`, `.mcr`, `.srm`...); the card in use is copied first
  to `duckstation_shared_card_1.backup-DATE.mcd` in the saves folder, then the game starts again to read the new one.
- ⚙ settings. **Resolution**: the 3D's internal resolution, 1X (the console's own, 240 lines) to 4X (8X on a
  computer). It changes at once and goes to `settings.txt` in the saves folder (`scale N`); with no choice the program
  takes the screen's height / 240 (2X-3X on Android, 2X-8X on a computer: 4X is too much for some handheld GPUs while
  the game loads: one tested drops to 41 fps there, 59 at 3X). `--scale N` and `options.txt` still win
  at start. Where there is a touch screen, two more cards set the touch pad: **Button size** (SMALL 75 %, MEDIUM 100 %,
  LARGE 115 %, HUGE 130 %; each control keeps its corner) and **Opacity** (FAINT 25 %, LIGHT 50 %, SOLID 75 %, FULL
  100 %). They go to `settings.txt` too (`touch_size P`, `touch_opacity P`).
- ⏻ quit.

Under the cards the main screen shows the program's version (`tools/version.py`, given to CMake as
`HORIZON_VERSION` by `build.py` and `build_apk.py`; `DEV` when built by hand).

**A newer release:** at each start the program asks GitHub's API for the latest release of its repository (Android:
`assets/releases.txt`, written by `build_apk.py`; Windows, macOS and Linux: `HORIZON_REPOSITORY`, given to CMake by
`build.py`; both take `--repository`, else `GITHUB_REPOSITORY`, else the checkout's origin, and `none` for no check).
When that release's X.Y.Z is higher than the program's own, a screen says "NEW VERSION V… AT DW1HORIZON.COM" once,
as soon as the game is past its start and no other screen is open, with two cards: DOWNLOAD opens the website (the
patcher there makes the new version from the player's disc; a full-screen window is minimised first) and LATER goes
back to the game. The line also stays in the menu above the version. Offline or refused, nothing shows. This is the
program's only use of the network: Android in Java (`INTERNET` permission), Windows with WinHTTP, macOS and Linux
with the system's `curl` (without it, no notice). `--new-version TAG` shows the screen in tests (no check is made
with `--frames` or `--press`).

**Where the player left off:** Android may end an app it has sent to the background, and the game would lose what
was played since its last save. So when the app goes to the background the whole machine is written to `resume.state`
in the saves folder (about 11 MB, through a `.new` file), and a start that finds it goes on from that moment, without
the start's black screens. The file lives only while the app is away: it is deleted when the app comes back by itself,
as soon as it has been loaded, on QUIT and when a memory card is imported, so an old moment never comes back over a
newer save. Its header ties it to this program's version and this disc's size, and the memory card stays the one on
file (the snapshot's copy of the card is not used). `--suspend-at N` keeps it at frame N and ends, as Android would.

**The first start** asks CONTROLLER or KEYBOARD before the game (`--first-start` asks it again), with the
same screens as the menu's controls. The
answer goes to `controls.txt` (`mode pad`; an older `mode touch` still starts with the touch pad shown).

**Setting the buttons** (✎): the game waits and the drawn PlayStation controller lights each of its buttons in turn
(the pad's four directions, Cross, Circle, Square, Triangle, L1, R1, L2, R2, SELECT, START): press the key, controller
button, hat or axis wanted for it. The back arrow at the top left (a click or tap) or Escape stops it and leaves the
buttons as they were. The first press decides whether the keyboard, the controller or the other joystick is being set;
one input cannot take two buttons. Nothing pressed for ten seconds leaves everything as it was. The choice goes to
`controls.txt` in the saves folder (`pad cross=a`, `key cross=Z`, `joy cross=b2` / `h0.1` / `a1-`: SDL's controller and
key names, a raw button, hat direction or axis side), which can also be edited by hand. (`tools/player/controls.c`,
`menu.c`)

**Touch:** with touch chosen, a touch pad is drawn over the picture (a D-pad, the four face buttons, L1/L2/R1/R2,
SELECT, START and the menu button; several fingers at once, the D-pad in eight directions). It steps aside when a
controller button or a key is pressed and comes back at the next touch. `--touch` shows it from the start on any
system. (`tools/player/overlay.c`: drawn at start into one texture, no image files.)

## A setup wizard

A Windows setup program that installs Horizon Play and the game in one go, made the way the Android APK is. CI
publishes an **empty template** as a release asset, `Horizon-Setup.exe` (`desktop.yml`, artifact
`horizon-setup-template`): an NSIS wizard and Horizon Play, **no game data**. On the player's own computer the desktop
patcher downloads it (cached by tag), appends the disc it just built to a copy and writes `<disc>-Setup.exe` next to
the disc (**Windows installer (.exe)** button, `desktop.make`, `tools/patcher/setup_exe.py`). That file holds the player's disc, so it stays on their computer.

```
python3 tools/player/installer.py --player "Horizon Play" --out Horizon-Setup.exe        # the template (makensis)
python3 tools/patcher/setup_exe.py Horizon-Setup.exe DISC.cue DISC-Setup.exe              # the template plus a disc
```

`installer.py` runs `makensis` from the PATH, from `Program Files (x86)\NSIS` (preinstalled on the Windows runner; the
workflow installs it with choco if not), or in a Docker `ubuntu:24.04`. `setup_exe.py` (standard library, streamed,
one `.bin` per disc) copies the template and appends the `.bin`, the cue text (its FILE renamed to
`Digimon World Horizon.bin`) and a fixed 24-byte trailer: bin size (u64), cue size (u32), format version (u32), the
magic `HZSETUP1`, little endian. The template is built with `CRCCheck off`: NSIS reads only the data length its first
header records, so the appended bytes are ignored, but its CRC check covers the whole file and would be the one thing
to object to them.

The wizard (English or Spanish) installs for the current user, without administrator, into
`%LOCALAPPDATA%\Programs\Digimon World Horizon`, adds desktop and Start menu shortcuts that open the disc, and an entry
in Windows' installed apps. NSIS cannot copy 600 MB quickly, so after the player files it runs
`horizon-play.exe --unpack SETUP DIR` (`unpack_setup` in `horizon_play.c`: reads the trailer, writes the `.bin` and `.cue`
through `.new` files, renames them; nonzero exit and a message on stderr when the trailer is missing, wrong or a write
fails), and aborts the install with a message if it fails. A template run with no disc appended says so at the start
(`.onInit` reads the last 8 bytes for the magic) and quits before installing anything. The last page offers **Play now**.
The uninstaller removes the install folder with the disc; the saves stay (`%APPDATA%\Horizon\Horizon`). A silent
`Setup.exe /S /D=DIR` works (the CI check runs it, then `Uninstall.exe /S`). The macOS patcher does not carry the
template (the macOS job would have to wait for the whole Windows job): make the setup on a Windows computer.

## A Mac app, and a Linux installer

On a Mac, the desktop patcher's **Mac app** button (`desktop.make`, `tools/patcher/mac_app.py`) writes
`<disc>-Mac.dmg` next to the disc: a disk image with `Digimon World Horizon.app` and an Applications link to drag it
to (`hdiutil create -format UDZO`). The app is a copy of the Horizon Play .app the patcher carries, with the disc added
in `Contents/Resources` as `Digimon World Horizon.bin` and `.cue`; Info.plist names it "Digimon World Horizon" and the
bundle id stays, so both apps share the saves (`SDL_GetPrefPath("Horizon", "Horizon")`, `~/Library/Application
Support/Horizon/Horizon`, not tied to the bundle). Started with no disc argument, Horizon Play first looks for
`Digimon World Horizon.cue` beside its core (`SDL_GetBasePath`: the Resources folder in a Mac app, the program's own
folder elsewhere) and plays it, and only then falls back to `last-disc.txt`. The CLI
(`python3 tools/patcher/mac_app.py "Horizon Play.app" DISC.cue OUT.zip`) makes a zip that keeps symlinks and execute
bits; a `.dmg` needs a Mac.

Signing: adding files breaks the bundle's seal, so on a Mac the copy is signed again ad hoc (`codesign --force --deep -s
-`, with the quarantine mark removed). That replaces the template's Developer ID signature and its notarization: the
app runs on the Mac that made it, but one copied to another Mac (or made by the CLI elsewhere, which cannot sign at
all) needs `xattr -cr "Digimon World Horizon.app"` once, or right-click then Open. `desktop.yml`'s macOS job makes a
dummy-disc dmg, mounts it, compares the bin, runs `codesign --verify` and tries a short launch.

**Linux:** `python3 tools/patcher/linux_run.py Horizon-Play-Linux-x86_64.tar.gz DISC.cue DISC-Linux.run` writes a self
extracting installer (`tools/patcher/linux_run.py`): a short POSIX sh header and a tar.gz at a recorded byte offset, with
the Linux player bundle (`player.yml`'s tarball) and the disc as `Digimon World Horizon.bin/.cue`. `./DISC-Linux.run`
installs without sudo into `${XDG_DATA_HOME:-~/.local/share}/digimon-world-horizon` (`--target DIR` changes it),
writes `digimon-world-horizon.desktop` in `~/.local/share/applications` with the icon beside the game, copies the
launcher to the desktop folder when `xdg-user-dir DESKTOP` has one (trusted through `gio` where possible), and leaves
`uninstall.sh` (`--uninstall` runs it): it removes only what the installer put in the folder and the launchers, and
keeps the saves (`~/.local/share/Horizon/Horizon`). In a terminal it asks whether to start the game; a double click
starts it (`--no-start` never does). `player.yml` makes one from a dummy disc, installs it, compares the bin, checks
that the player finds the disc with no argument, and uninstalls. The desktop patcher has a **Linux installer (.run)**
button (`desktop.make`) that downloads the release's `Horizon-Play-Linux-x86_64.tar.gz` (attached by `player.yml`) and
builds it. On Windows and Linux the Mac button writes `<disc>-Mac.zip` from the release's `Horizon-Play-macOS.zip`
(`ditto --keepParent`); it cannot be signed there, so on the Mac the first open is right-click then Open.

## Licences

See [THIRD-PARTY.md](../THIRD-PARTY.md). The core is GPL-3.0 and ships as its own library with its source linked in
`NOTICE.txt`. The host is MIT.
