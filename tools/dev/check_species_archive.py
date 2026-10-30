#!/usr/bin/env python3
"""Check a derived DIGI.DAT using that build's recorded engine settings."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = Path(sys.argv[1]).resolve()
    facts = json.loads((out / 'derived/exe-facts.json').read_text())
    plan = json.loads((out / 'derived/manifest.json').read_text())['plan']
    env = dict(os.environ, COLD='1' if facts['cold_anim'] else '0',
               PARTNER_MMD_MAX=str(plan['PARTNER_MMD_MAX']),
               SPECIES_RAM_MB='8' if facts.get('partner_mmd_max_8mb') is not None else '2',
               EVL_SHARD_SCRATCH_SIZE=str(facts.get('evl_shard_scratch_size') or 5436))
    print('Archive settings:', {name: env[name] for name in
          ('COLD', 'PARTNER_MMD_MAX', 'SPECIES_RAM_MB', 'EVL_SHARD_SCRATCH_SIZE')}, flush=True)
    return subprocess.call([sys.executable, str(ROOT / 'tools/species.py'), '--content',
                            str(out / 'species'), 'check', str(out / 'DIGI.DAT')], cwd=ROOT, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
