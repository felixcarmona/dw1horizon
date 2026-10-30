#!/usr/bin/env bash
# tagged.sh: patch 0129 (save v4, the tagged extension) in the emulator. Set DISC and ELF to a tagged-save executable without expanded story state.
#   1. migration: a v1 file and v2 files load as before (check.sh prints screen, money, partner type, error, menu)
#   2. a v3 file (expanded-story engine) is refused by this build, as before
#   3. the round trip: Continue from a v1 card, save at Jijimon (capture_save.sh), the card holds a v4 file (memory_card.py save shows its
#      records), Continue from it gives the same state
#   4. the point of the format: a record no build knows is skipped; a required one makes the file unreadable ("Data Error");
#      a record cut short covers fewer elements and the rest keep their v1 value
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
: "${DISC:?Set DISC to a tagged-save test disc}"; : "${ELF:?Set ELF to its matching executable}"; D=${D:-build/dev/saves/tagged}
mkdir -p $D
. $T/symbols.sh
N=BASLUS-01032DMR0
pk() { tools/dev/emulator.py peek $(sym $ELF $1) $2 | cut -d' ' -f2- | tr -d ' ' | head -1; }
# Continue from a card, wait (the machine may be busy: poll, no fixed wait) until the game is loaded (menu ffffffff) or refused
# (error 2), and print what the loaded game holds: screen, money, partner type, the first species-raised bits and inventory ids, error
state() {
  export EMU_PORT=${PORT:-38203}; cp "$1" "$D/$2.run.mcd"; tools/dev/emulator.py start $DISC --card "$D/$2.run.mcd" >/dev/null
  tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null
  for i in $(seq 1 90); do [ "$(pk CURRENT_MENU 4)" = ffffffff -o "$(pk MEMORY_CARD_ERROR 4)" != 00000000 ] && break; tools/dev/emulator.py wait 2 >/dev/null; done
  tools/dev/emulator.py wait 2 >/dev/null
  echo "$2: screen=$(pk CURRENT_SCREEN 2) money=$(pk MONEY 4) type=$(pk PARTNER_ENTITY 4) raised=$(pk SPECIES_RAISED_BITS 8) inv=$(pk INVENTORY 16) err=$(pk MEMORY_CARD_ERROR 4)"; tools/dev/emulator.py stop >/dev/null
}
chk() { state "$1" "$2"; }
echo "== 1. old files (v1, v2): they load"
chk build/ids-saved.mcd v1
chk build/expanded-story/v2-card.mcd v2
chk build/species/card-v2.mcd v2b
echo "== 2. a v3 file with story state (expanded-story engine): refused, error 2 = Data Error"
chk build/expanded-story/v3-card.mcd v3
echo "== 3. the round trip: Continue from a v1 card, save at Jijimon; the card then holds a v4 file"
bash $T/capture_save.sh $DISC $ELF 38202 build/ids-saved.mcd $D/rt 00001234 2>&1 | tail -1
python3 tools/dev/memory_card.py save $D/rt/out.mcd | grep -E "ext0" | cut -c1-260
state $D/rt/out.mcd rt
echo "== 4. records: all given content; a record no build knows (loads the same); a required one (refused: err 2);"
echo "==    a record cut short (the first 5 of 30 inventory ids, the species bits emptied: the rest keeps the v1 value);"
echo "==    a bit array longer than this build has room for (loads, the surplus is dropped)"
inv=$(python3 -c "import struct;print(struct.pack('<30h',*range(1,31)).hex())"); raised=$(python3 -c "print(bytes([0x28]+[0]*127).hex())")
cp $D/rt/out.mcd $D/full.mcd; python3 tools/dev/memory_card.py settag $D/full.mcd $N 0x0002 $inv >/dev/null; python3 tools/dev/memory_card.py settag $D/full.mcd $N 0x0007 $raised >/dev/null
state $D/full.mcd full
cp $D/full.mcd $D/unknown.mcd; python3 tools/dev/memory_card.py addtag $D/unknown.mcd $N 0x00FE deadbeef >/dev/null; state $D/unknown.mcd unknown
cp $D/full.mcd $D/required.mcd; python3 tools/dev/memory_card.py addtag $D/required.mcd $N 0x80FE deadbeef >/dev/null
export EMU_PORT=38204; cp $D/required.mcd $D/required.run.mcd; tools/dev/emulator.py start $DISC --card $D/required.run.mcd >/dev/null; tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null
for i in $(seq 1 90); do e=$(pk MEMORY_CARD_ERROR 4); [ "$(pk CURRENT_MENU 4)" = ffffffff -o "$e" != 00000000 ] && break; tools/dev/emulator.py wait 2 >/dev/null; done
echo "required: err=$e money=$(pk MONEY 4) (refused: error 2, nothing loaded)"; tools/dev/emulator.py stop >/dev/null
cp $D/full.mcd $D/cut.mcd; python3 tools/dev/memory_card.py cuttag $D/cut.mcd $N 0x0002 10 >/dev/null; python3 tools/dev/memory_card.py cuttag $D/cut.mcd $N 0x0007 0 >/dev/null; state $D/cut.mcd cut
cp $D/full.mcd $D/long.mcd; python3 tools/dev/memory_card.py settag $D/long.mcd $N 0x0007 $(python3 -c "print(bytes([0x28]+[0]*127+[0xff]*40).hex())") >/dev/null; state $D/long.mcd long
