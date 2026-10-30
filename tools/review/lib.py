"""Compatibility import for saved motion provenance; see tools/dev/README.md."""
import importlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules[__name__] = importlib.import_module("tools.dev.models.review.lib")
