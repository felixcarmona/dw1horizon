"""Reserve a complete CD sector in the existing console partner allocation.

Near-capacity imports and archive-backed originals need this storage pass.
Geometry stays exact. Imports re-fit only field/intro locomotion and training
aliases; originals re-fit resident streams with decoded-tick verification. No runtime
memory, new cold slots, or engine changes are required.
"""
import coldsplit
from tools.models import battle_restore

LIMIT = 0x18000  # 48 sectors; the fixed allocation is 49 sectors
SPECIES = frozenset((62, 66, 113, 115, 121, 242, 303, 304))
SLOTS = frozenset((0, 1, 2, 3, 4, 18, 27, 33, 34, 35, 36))


def apply(data, skeleton, sid, cold=True):
    if int(sid) not in SPECIES:
        return data, dict(applied=False)
    nb = len(skeleton)
    def size(raw):
        return len(coldsplit.split(raw, nb)[0]) if cold else len(raw)
    before = size(data)
    if int(sid) not in SPECIES or before <= LIMIT:
        return data, dict(applied=False, resident_bytes=before)
    # Try each tolerance against the original, never accumulate fitting error.
    maximum = 3 if cold else (5 if int(sid) == 115 else 4)
    for tolerance in range(maximum+1):
        output, clips = battle_restore.compact(data, nb, tolerance, slots=SLOTS if cold else None, include_cold=not cold)
        after = size(output)
        if after <= LIMIT:
            return output, dict(applied=True, resident_before=before,
                                resident_after=after, tolerance=tolerance,
                                clips=clips, sector_margin=0x18800-((after+2047)//2048)*2048)
    raise ValueError(f'{sid}: cannot reserve a partner sector within tolerance {maximum}')


def disc_file(path, bones, sid):
    """A private replacement file; keep the authored/pinned input untouched."""
    if int(sid) not in SPECIES:
        return path
    from pathlib import Path
    import hashlib
    import json
    data = Path(path).read_bytes()
    output, proof = apply(data, [None]*bones, sid, cold=False)
    if not proof['applied']:
        return path
    target = Path(__file__).resolve().parents[2]/'build/partner-headroom'/f'{sid}-{hashlib.sha256(data).hexdigest()}.MMD'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    target.with_suffix('.json').write_text(json.dumps(proof, indent=2)+'\n')
    return str(target)
