"""Run the shipped USA writer with already verified derive holes, outside checkout.

The reuse orchestrator runs this in an empty Python 3.10 container. The browser
independently derives the holes again; this gate isolates executable deltas/writer.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def main():
    if sys.version_info[:2] != (3, 10):
        raise RuntimeError('reuse writer gate requires Python 3.10')
    package, original, retained, output = map(Path, sys.argv[1:5])
    sys.path.insert(0, str(package))
    import dwpatch as dw
    manifest = json.loads((package / 'manifest.json').read_text())
    variant = manifest['variants'][manifest['default']]
    key, source, _ = dw.identify_base(str(original), manifest['bases'])
    if key != 'us':
        raise RuntimeError('USA base required')
    payload = dw.read_payload3(dw.read_patch_file(str(package), variant))
    image = dw._iw().Image(str(retained))
    try:
        holes = {}
        for hole in variant['holes']:
            data = image.read(hole['file'])
            if len(data) != hole['size'] or hashlib.sha1(data).hexdigest() != hole['sha1']:
                raise RuntimeError('retained hole differs: ' + hole['file'])
            holes[hole['id']] = data
        with tempfile.TemporaryDirectory() as work:
            base = dw.BaseDisc(key, source, None, tool_root=str(package / 'bundle'), work=work,
                               source_discs=sys.argv[5:])
            dw.build_disc3(payload, base, holes, str(output), variant['outputs'][key]['sha1'])
    finally:
        image.f.close()


if __name__ == '__main__':
    main()
