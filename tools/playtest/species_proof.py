"""Compatibility import for the frozen technique-proof recipe."""
import importlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if __name__ == '__main__':
    import runpy
    runpy.run_module('tools.dev.playtest.species_proof', run_name='__main__')
else:
    sys.modules[__name__] = importlib.import_module('tools.dev.playtest.species_proof')
