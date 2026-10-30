#!/usr/bin/env bash
# Save and load DuckStation save states on an Android handheld, over wireless adb
# (tools/dev/device.sh sets the device up). The states stay on the device, in savestates/named/ of DuckStation's folder.
#
#   tools/dev/device-state.sh save NAME     Quick Save in the running game, kept as NAME
#   tools/dev/device-state.sh load NAME     restarts the game and loads NAME
#   tools/dev/device-state.sh start         starts the game from the beginning
#   tools/dev/device-state.sh list          the saved states
#   tools/dev/device-state.sh delete NAME   removes one
#   tools/dev/device-state.sh shot [FILE]   screenshot of the device (default build/device-state.png)
#
# One time, in DuckStation (Controller Settings > Hotkeys): bind Quick Save and Quick Load to two buttons of the
# device's built-in controller that nothing else uses, and give their evdev codes and the controller's input device
# here: KEY_SAVE, KEY_LOAD and INPUT_DEV (find them
# with `adb shell getevent -l` while pressing a button). DuckStation's own pause menu is not reachable
# without the touch overlay, so the hotkeys are the way in; they are pressed with sendevent on the real controller
# (a press from `adb shell input` would register as a "Virtual" device).
#
# How it works: Quick Save writes slot 0 (SLUS-01032_0.sav), a file only the app can read (mode 0600), so adb cannot
# pull it; but the folder is writable by the shell group, so the file is *renamed* into named/NAME.sav. Loading
# renames it back to slot 0, restarts the game, presses Quick Load and puts the file back under its name. A state
# belongs to the disc it was made with (the executable is in RAM): load it only on the same build/device.cue.
# DuckStation ignores a boot path given by intent (it boots the BIOS with no disc), so the game is started by
# tapping its row in the list: the only game there is build/device.cue.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${DEVICE:?Set DEVICE to an authorized adb serial or HOST:PORT}"
DEV=$DEVICE
APP=com.github.stenzek.duckstation
SS=/sdcard/Android/data/$APP/files/savestates
SLOT=$SS/SLUS-01032_0.sav
NAMED=$SS/named
adbd() { adb -s "$DEV" "$@"; }

connect() {
  case $DEV in *:*) adb connect "$DEV" >/dev/null;; esac
  adbd get-state 2>/dev/null | grep -q device || { echo "$DEV: not connected or not authorized" >&2; exit 1; }
  adbd shell "mkdir -p $NAMED"
}
running() { adbd shell dumpsys activity activities | grep -q "topResumedActivity=.*$APP/.EmulationActivity"; }
# a real button press on the controller (an evdev key code)
press() { : "${INPUT_DEV:?Set INPUT_DEV to the controller event device}"; adbd shell "sendevent $INPUT_DEV 1 $1 1; sendevent $INPUT_DEV 0 0 0; sleep 0.1; sendevent $INPUT_DEV 1 $1 0; sendevent $INPUT_DEV 0 0 0"; }
stamp() { adbd shell "stat -c %Y $SLOT 2>/dev/null || echo 0"; }
name_ok() { [[ "${1:-}" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "name: letters, digits, _ . - only" >&2; exit 1; }; }
launch() {
  adbd shell am force-stop $APP
  adbd shell monkey -p $APP -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
  sleep 7; adbd shell input tap ${TAP:?Set TAP to the game row coordinates, X Y}
  for _ in $(seq 20); do running && break; sleep 1; done
}

case "${1:-}" in
  save)
    name=${2:-}; name_ok "$name"
    connect; running || { echo "DuckStation is not running a game" >&2; exit 1; }
    before=$(stamp); saved=0
    for _ in 1 2 3; do   # a press now and then is lost
      press "${KEY_SAVE:?Set KEY_SAVE to the Quick Save evdev code}"
      for _ in $(seq 10); do sleep 0.5; [ "$(stamp)" != "$before" ] && saved=1 && break; done
      [ $saved = 1 ] && break
    done
    [ $saved = 1 ] || { echo "the Quick Save hotkey did nothing (is it bound? see the header)" >&2; exit 1; }
    sleep 1; adbd shell "mv -f $SLOT $NAMED/$name.sav && ls -la $NAMED/$name.sav" ;;
  load)
    name=${2:-}; name_ok "$name"
    connect; adbd shell "test -f $NAMED/$name.sav" || { echo "no state '$name' (list)" >&2; exit 1; }
    adbd shell "mv -f $NAMED/$name.sav $SLOT"
    launch; sleep "${LOAD_WAIT:-12}"; press "${KEY_LOAD:?Set KEY_LOAD to the Quick Load evdev code}"; sleep 3
    adbd shell "mv -f $SLOT $NAMED/$name.sav"; echo "loaded $name" ;;
  start) connect; launch; echo started ;;
  list) connect; adbd shell "ls -la $NAMED" ;;
  delete) name=${2:-}; name_ok "$name"; connect; adbd shell "rm -f $NAMED/$name.sav"; echo "deleted $name" ;;
  shot) connect; f=${2:-build/device-state.png}; adbd exec-out screencap -p > "$f"; echo "$f" ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
