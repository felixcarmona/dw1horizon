"""The shared numeric backend for both direct tool CLIs and derive imports."""
from pathlib import Path
import sys

root = str(Path(__file__).resolve().parent.parent)
if root not in sys.path:
    sys.path.insert(0, root)
from tools.derive import arraymath

# Preserve one Array class and dtype set when a CLI imports from tools/ alone.
sys.modules[__name__] = arraymath
