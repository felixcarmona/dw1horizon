"""Assembler/disassembler command for the DWS bytecode backend."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if __package__:
    from . import main
else:
    from dws.bytecode import main

if __name__ == '__main__':
    main()
