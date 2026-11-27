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
| Screen | full screen, 4:3, F11 / Alt+Enter toggles | |
| Pace | the screen's refresh (vsync); near the console's 59.82 Hz the sound is stretched by under half a percent to follow it, steering its queue to 60 ms. A frame the machine was too slow for (heavy loads) is caught up: the next one runs without being shown | no stutter in the music, no missed refreshes |

The program carries no game data. It plays the disc that the patcher builds from the player's own disc.

## Where players get it

- **Windows and macOS:** inside the desktop patcher (`desktop.yml` builds it and passes `--player` to
  `tools/patcher/app/build.py`). After a build, and when the app opens again, a **Play** button starts it on the
  disc (`desktop.play`).
- **Linux:** `Horizon-Play-Linux-x86_64.tar.gz` (`player.yml`), built on Ubuntu 22.04. Run
  `./horizon-play DISC.cue` once. With no argument it opens the last disc it played.
- **Android:** after a build, the desktop patcher's **Android app (.apk)** button writes `<disc>.apk` next to the disc
  (`desktop.make_apk`, `tools/patcher/apk.py`). It is Horizon Play for Android (`tools/player/android`, arm64,
  Android 7+) with the built disc added as `assets/horizon.bin`, stored and page aligned. The player copies it to the
  phone and installs it: the game starts at once, with nothing to choose. The app reads the disc in place, through the
  core's VFS (`--embedded APK OFFSET SIZE`), so the phone keeps one copy. The patcher signs it (APK Signature Scheme
  v2, standard library only) with a key made on first use and kept in its settings folder (`android-key.json`), so
  the next APK from that computer installs over it and keeps the saves. An APK signed with another key has to replace
  the app; Android then offers to keep its data (`hasFragileUserData`). Saves, logs and options live in
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
python3 tools/patcher/apk.py Horizon-Play.apk DISC.bin OUT.apk --key key.json   # the template with a disc inside
```

It checks out SwanStation and OpenBIOS (PCSX-Redux's `nugget`) at the commits pinned in `build.py`. It builds the
core, OpenBIOS (with `OPENBIOS_SHELL=shell`: the default shell gave a black screen) and the program, with SDL2
fetched by CMake at a pinned hash and linked statically.

Test flags: `--windowed`, `--frames N` (stop after N frames), `--press "frame:button:len,..."` (libretro joypad ids),
`--screenshot FILE.ppm`, `--no-disc` (boot the BIOS alone), `--set KEY=VALUE` (override a core option),
`--touch` (the touch pad from the start), `--first-start` (ask touch or controller again), `--ask-card` (the new install's IMPORT / NEW GAME
question), `--window WxH` (a window
of that size), `--no-fast-start`.
`HORIZON_PLAY_DEBUG=1` prints the core's log. The saves folder also gets `horizon-play.log` (the core's log, the
OpenGL version and the speed every 30 seconds) and reads `options.txt` (`KEY=VALUE` lines, core options to override).

## Controls

Keyboard: arrows, Z Cross, X Circle, A Square, S Triangle, Q/W L1/R1, E/R L2/R2, Enter Start, Backspace Select.
Any pad SDL knows is laid out like a PlayStation pad, and the left stick also moves. Any other joystick works too,
read raw: buttons 0-3 Triangle, Circle, Cross, Square, 4-7 L2, R2, L1, R1, 8-9 SELECT, START, the first hat and the
first two axes as the D-pad. The first time such a joystick is connected, the button setup below opens by itself
(after the first start's question) to fit it to its own layout; once set, `joy device=` in `controls.txt` keeps its
SDL GUID and it is not asked about again. A phone's tilt sensor is not taken for a joystick.

**The menu:** SELECT and START pressed together, at any moment (neither reaches the game), the round button at the
top of the touch pad, or on a computer Escape or a right click (F11 or Alt+Enter switch full screen). The game waits under it. It shows big pictures, each with a word in English under it (a 5x7 font drawn into the overlay's texture); a tap, the mouse
or the pad's arrows with Cross, Circle or START choose, Triangle (or Escape) goes back:

- ▶ back to the game.
- 🎮⌨️ the controller and keyboard buttons: ✔ keep them, or ✎ set them. (The touch pad needs no choice here: it
  comes back at any touch.)
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

**Where the player left off:** Android may end an app it has sent to the background, and the game would lose what
was played since its last save. So when the app goes to the background the whole machine is written to `resume.state`
in the saves folder (about 11 MB, through a `.new` file), and a start that finds it goes on from that moment, without
the start's black screens. The file lives only while the app is away: it is deleted when the app comes back by itself,
as soon as it has been loaded, on QUIT and when a memory card is imported, so an old moment never comes back over a
newer save. Its header ties it to this program's version and this disc's size, and the memory card stays the one on
file (the snapshot's copy of the card is not used). `--suspend-at N` keeps it at frame N and ends, as Android would.

**The first start** asks touch or controller and keyboard before the game (`--first-start` asks it again). The
answer goes to `controls.txt` (`mode touch` or `mode pad`).

**Setting the buttons** (✎): the game waits and the screen shows each PlayStation button in turn (the pad's four
directions, Cross, Circle, Square, Triangle, L1, R1, L2, R2, SELECT, START): press the key, controller button, hat or
axis wanted for it. The first press decides whether the keyboard, the controller or the other joystick is being set;
one input cannot take two buttons. Nothing pressed for ten seconds leaves everything as it was. The choice goes to
`controls.txt` in the saves folder (`pad cross=a`, `key cross=Z`, `joy cross=b2` / `h0.1` / `a1-`: SDL's controller and
key names, a raw button, hat direction or axis side), which can also be edited by hand. (`tools/player/controls.c`,
`menu.c`)

**Touch:** with touch chosen, a touch pad is drawn over the picture (a D-pad, the four face buttons, L1/L2/R1/R2,
SELECT, START and the menu button; several fingers at once, the D-pad in eight directions). It steps aside when a
controller button or a key is pressed and comes back at the next touch. `--touch` shows it from the start on any
system. (`tools/player/overlay.c`: drawn at start into one texture, no image files.)

## Licences

See [THIRD-PARTY.md](../THIRD-PARTY.md). The core is GPL-3.0 and ships as its own library with its source linked in
`NOTICE.txt`. The host is MIT.
