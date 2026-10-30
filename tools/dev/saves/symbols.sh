# sym ELF NAME[+OFF] -> 0xADDR (nm, local symbols too)
sym() { local n=${2%%+*} o=0; [ "$2" != "$n" ] && o=${2#*+}; printf '0x%x' $(( 0x$(nm "$1" | awk -v n="$n" '$3==n{print $1; exit}') + o )); }
