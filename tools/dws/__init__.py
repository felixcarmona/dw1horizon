"""DWS: the Digimon World story language (docs/mods/dws.md). Compiles a typed braces
language to the game's script assembly (tools/dws/bytecode/__main__.py), original: original opcodes only."""
import os, sys
VERSION = '0.1'
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # tools/: bytecode, fontgen, dwmap, species...
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
