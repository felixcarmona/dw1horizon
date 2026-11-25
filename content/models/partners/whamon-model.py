#!/usr/bin/env python3
"""Whamon partner model: the player's HOEE.MMD, larger, with its field cycles retimed.

Whamon (type 24, 12 bones) stands about as tall as the tamer on the disc. This
script bakes one uniform size (SCALE) into its mesh and every animation, keeping
the walk and run pace (tools/models/resize.py resize_with_pace), and writes the
replacement HOEE.MMD. The ferry Whamon is another model (EHOE, type 146).

Usage (from the repository root):
  python3 content/models/partners/whamon-model.py [OUT.MMD]
default OUT: build/models/HOEE-partner.MMD
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools')]
import mmd  # noqa: E402
from tools.models import resize  # noqa: E402

TYPE = 24
SCALE = 1.34


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/models/HOEE-partner.MMD')
    data = open(os.path.join(mmd.EXTRACTED, 'CHDAT', f'MMD{TYPE // 30}', 'HOEE.MMD'), 'rb').read()
    skeleton = mmd.exe().skeleton[TYPE]
    try:
        model = resize.resize_with_pace(data, skeleton, TYPE, SCALE)
        how = 'field cycles retimed'
    except ValueError as why:
        if 'repeating field cycle' not in str(why):
            raise
        model = resize.resize(data, len(skeleton), SCALE)
        how = 'clips unchanged in time'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(model)
    print(f'{out}: HOEE x{SCALE}, {how}, {len(model)} bytes')


if __name__ == '__main__':
    main()
