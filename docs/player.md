# Horizon Play

Horizon Play lets players start the game without installing or setting up an emulator. It is a small program
(`tools/player/horizon_play.c`, SDL2 + OpenGL) that loads the [SwanStation](https://github.com/libretro/swanstation)
libretro core and boots the patched disc with the free OpenBIOS. Its settings are fixed:

| Setting | Value | Why |
|---|---|---|
| RAM | 8 MB | extra heap headroom; the game still runs in 2 MB ([real hardware](../README.md)) |
| CPU | 250 % | smoother play; the title screen's settings panel detects both and hides itself |
| Renderer | OpenGL (GLES 3 on Android), internal resolution = display height / 240 (2x-8x, Android 2x-4x; `--scale N`) | sharp 3D at full screen |
| BIOS | OpenBIOS (`system/openbios.bin`), no fast-boot patch | no Sony BIOS is needed or shipped |
| Memory card | slot 1, `duckstation_shared_card_1.mcd` in the user's data folder, written by the program each second it changed and when the app goes to the background | survives updates of the app |
| Screen | full screen, 4:3, F11 / Alt+Enter toggles | |

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
  `Android/data/com.dw1horizon.play/files/saves`. The template APK alone (`desktop.yml`'s `horizon-play-apk`
  artifact) asks once for a patched `.bin` and copies it into the app's folder.

OpenBIOS takes about 25-30 seconds to reach the game's first picture: the screen stays black until then.

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
`--screenshot FILE.ppm`, `--no-disc` (boot the BIOS alone), `--set KEY=VALUE` (override a core option).
`HORIZON_PLAY_DEBUG=1` prints the core's log. The saves folder also gets `horizon-play.log` (the core's log, the
OpenGL version and the speed every 30 seconds) and reads `options.txt` (`KEY=VALUE` lines, core options to override).

## Controls

Keyboard: arrows, Z Cross, X Circle, A Square, S Triangle, Q/W L1/R1, E/R L2/R2, Enter Start, Backspace Select.
Any pad SDL knows is laid out like a PlayStation pad, and the left stick also moves.

## Licences

See [THIRD-PARTY.md](../THIRD-PARTY.md). The core is GPL-3.0 and ships as its own library with its source linked in
`NOTICE.txt`. The host is MIT.
