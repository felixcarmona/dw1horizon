"""Additional partner area profiles, shared by native maps and story map recipes."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def profiles():
    return json.loads((Path(__file__).resolve().parent.parent / 'content/map-regions.json').read_text())


def apply(m, name):
    """Add profile entries without changing any existing region's response or map size."""
    for key, profile in profiles().items():
        region = int(key)
        if not 9 <= region <= 127:
            raise ValueError(f'additional map region {region}: expected 9..127')
        liked, disliked = name in profile['pleased'], name in profile['displeased']
        if liked and disliked:
            raise ValueError(f'{name}: region {region} is both pleased and displeased')
        if not (liked or disliked):
            continue
        target, other = (m.regionA, m.regionB) if liked else (m.regionB, m.regionA)
        if region in other:
            raise ValueError(f'{name}: region {region} already has the opposite response')
        if region not in target:
            if -1 not in target:
                raise ValueError(f'{name}: no spare region entry for {region}')
            target[target.index(-1)] = region
