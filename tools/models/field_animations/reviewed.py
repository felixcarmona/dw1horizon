"""The reviewed source a field overlay's input stands for.

The overlays (chibi.py, gaits.py, pace.py ...) are reviewed on one model each and pin it by SHA-256. When a source disc
of another release gives another import of the same species (content/modeldelta/variants/<release>.json, made by
tools/models/variants.py), the overlay runs on that release's model with the reviewed parameters: the variant file
lists, per overlay input, the reviewed input it stands for ("reviewed_as": {its SHA-256: the reviewed SHA-256}).
Only inputs our own tool made from that release's model are listed, so nothing unreviewed passes.
"""
import json
from pathlib import Path

VARIANTS = Path(__file__).resolve().parents[3] / 'content/modeldelta/variants'
_table = None


def reviewed(digest):
    """The SHA-256 of the reviewed input that `digest` (an overlay input's SHA-256) stands for: itself unless a
    variant lists it."""
    global _table
    if _table is None:
        _table = {}
        for path in sorted(VARIANTS.glob('*.json')) if VARIANTS.is_dir() else ():
            _table.update(json.loads(path.read_text()).get('reviewed_as', {}))
    return _table.get(digest, digest)
