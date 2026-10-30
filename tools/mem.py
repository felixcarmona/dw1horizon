#!/usr/bin/env python3
"""Compatibility entry point for protected motion recipes; implementation: tools.dev.memory_inspector."""
import importlib
from pathlib import Path
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == '__main__':
    runpy.run_module('tools.dev.memory_inspector', run_name='__main__')
else:
    sys.modules[__name__] = importlib.import_module('tools.dev.memory_inspector')
