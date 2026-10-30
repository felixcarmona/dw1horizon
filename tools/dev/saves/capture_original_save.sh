# capture_original_save.sh PORT CARD OUTDIR MONEY_HEX8: the ORIGINAL executable continues from CARD, sets the money, saves through the
# sleep prompt ("Save and go"); OUTDIR/out.mcd is the card it leaves.
set -uo pipefail
T=$(cd "$(dirname "$0")" && pwd); cd "$T/../../.."
export EMU_PORT=$1; IN=$2; E=$3; MONEY=$4; mkdir -p $E
H=${EMU_HOME:-$PWD/.tools/emu/home-$EMU_PORT}
emu() { tools/dev/emulator.py "$@" >/dev/null; }
o() { python3 -c "import sys; sys.path.insert(0,'tools'); from tools.dev import symbols as dwsyms; print(hex(dwsyms.resolve('$1','orig')))"; }
pk() { tools/dev/emulator.py peek $(o $1) $2 | cut -d' ' -f2- | tr -d ' '; }
cp $IN $E/in.mcd
emu start "Digimon World (USA).cue" --card $E/in.mcd; emu seq tools/dev/sequences/continue.seq; emu wait 8
echo "original: screen $(pk CURRENT_SCREEN 1) money $(pk MONEY 4)"
emu poke $(o MONEY) $MONEY; emu poke $(o PARTNER_SUB_STATE) 00; emu poke $(o PARTNER_STATE) 03
for i in $(seq 1 30); do emu wait 1; [ "$(pk CURRENT_MENU 4)" = 28000000 ] && break; done
echo "menu $(pk CURRENT_MENU 4) after $i s"; emu press DOWN 4; emu wait 1; emu shot $E/1-prompt.png
for i in $(seq 1 12); do m=$(pk CURRENT_MENU 4); [ "$m" = ffffffff ] && break; emu press CROSS 4; emu wait 2; done
echo "menu $(pk CURRENT_MENU 4)"; emu wait 4; emu stop; cp $H/memcard1.mcd $E/out.mcd
python3 tools/dev/memory_card.py ls $E/out.mcd | head -1
python3 tools/dev/memory_card.py save $E/out.mcd | grep -oE "bytes: [0-9]+|'money': [0-9]+|'checksum_ok': [A-Za-z]+, 'refuses_original': [A-Za-z]+|'version': [0-9], 'size': [0-9]+, 'checksum_ok': [A-Za-z]+, 'matches_v1': [A-Za-z]+" | tr '\n' ' '; echo
