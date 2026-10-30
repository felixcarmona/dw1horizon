#!/usr/bin/env python3
"""Prepare disposable code/story edits and prove fresh changed-package identity.

`prepare` edits only explicitly supplied scratch source trees under this checkout's
build directory. `prove` scans that build afresh and streams every base through
the production writer, comparing every file (and the license) with independent
changed-build reference images. Neither mode writes original bytes to evidence.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

import literal_audit as audit
import literal_gate

ROOT = Path(__file__).resolve().parents[2]


def functions(build):
    text = (Path(build) / 'exe/SLUS_010.32.elf.map').read_text()
    text = re.sub(r'( \.[\w.]+)\n\s+(0x)', r'\1 \2', text)
    out = {}
    output = 'SLUS_010.32'
    for line in text.splitlines():
        section = re.match(r'^\.(\w+)\s+0x[\da-f]+\s+0x[\da-f]+', line)
        if section:
            name = section[1]
            output = 'SLUS_010.32' if name in ('main', 'header') else name + '_REL.BIN' if name.isupper() else None
        match = re.match(r'^ (\.text\.([\w.]+))\s+0x([\da-f]+)\s+0x([\da-f]+)\s+(\S+\.o)\s*$', line)
        if not match or not output:
            continue
        _, name, address, size, obj = match.groups()
        source = obj.split('/gcc/')[-1][:-2]
        if source.startswith('src/') and int(size, 16):
            out[name] = dict(address=int(address, 16), size=int(size, 16), source=source, file=output)
    return out


def scratch(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / 'build').resolve()) or path == (ROOT / 'build').resolve():
        raise ValueError(f'{path}: supply a private scratch tree below {ROOT / "build"}')
    return path


def prepare(args):
    decomp, story = scratch(args.decomp), scratch(args.story)
    pin = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD:decomp'], text=True).strip()
    edit = None
    for name, info in sorted(functions(args.build).items()):
        path = decomp / info['source']
        if not path.is_file() or not path.resolve().is_relative_to(decomp):
            continue
        original = subprocess.run(['git', '-C', str(decomp), 'show', pin + ':' + info['source']],
                                  capture_output=True, text=True)
        expression = r'\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{'
        if original.returncode or not re.search(expression, original.stdout):
            continue
        text = path.read_text()
        match = re.search(expression, text)
        if match:
            before = hashlib.sha1(path.read_bytes()).hexdigest()
            # A short block cannot disappear into an existing delay slot or
            # ordinary function alignment padding. It moves later functions
            # without a frozen symbol list and has no runtime behaviour.
            padding = '; '.join(['nop'] * 16)
            text = text[:match.end()] + f'\n    __asm__ volatile ("{padding}"); /* literal-gate disposable proof */\n' + text[match.end():]
            path.write_text(text)
            edit = dict(symbol=name, source=info['source'], before=before,
                        after=hashlib.sha1(path.read_bytes()).hexdigest(), baseline=info)
            break
    if edit is None:
        raise ValueError('no original C function located automatically from the current linker map')
    story_edit = None
    for path in sorted(story.rglob('*.py')):
        if not path.resolve().is_relative_to(story):
            continue
        text = path.read_text()
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'say'
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                value = node.args[0]
                lines = text.splitlines(keepends=True)
                start = sum(len(line) for line in lines[:value.lineno - 1]) + len(lines[value.lineno - 1].encode()[:value.col_offset].decode())
                end = sum(len(line) for line in lines[:value.end_lineno - 1]) + len(lines[value.end_lineno - 1].encode()[:value.end_col_offset].decode())
                before = hashlib.sha1(path.read_bytes()).hexdigest()
                path.write_text(text[:start] + repr('A fresh tale begins here.') + text[end:])
                story_edit = dict(source=str(path.relative_to(story)), before=before,
                                  after=hashlib.sha1(path.read_bytes()).hexdigest())
                break
        if story_edit:
            break
    if story_edit is None:
        raise ValueError('no authored say(string) found in the scratch story tree')
    audit.write_json(args.output, dict(code=edit, story=story_edit, pin=pin))


class Sink:
    def __init__(self):
        self.size = 0

    def write(self, data):
        self.size += len(data)
        return len(data)


def image_sums(image):
    rows = {q: dict(size=len(data), sha1=hashlib.sha1(data).hexdigest())
            for q in image.files for data in [image.read(q)]}
    data = image.license()
    rows['license_data.dat'] = dict(size=len(data), sha1=hashlib.sha1(data).hexdigest())
    return rows


def emitted_sums(writer, layout, files, license):
    """Hash file views as emitted, including the writer's XA/EDC rules.

    EU movies contain nonzero Form-2 EDC fields; the output writer zeroes those.
    Use the actual sector encoder rather than ignoring arbitrary source bytes.
    """
    lay = layout if hasattr(layout, 'entries') else writer.Layout(layout)
    sources = {q: writer.as_source(value) for q, value in files.items()}
    writer.plan(lay, {q: source.size for q, source in sources.items()})
    result = {}
    for entry in lay.entries:
        if entry.kind != 'file':
            continue
        h = hashlib.sha1()
        size = 0
        if entry.xa:
            for sector in writer._file_sectors(entry, sources[entry.path], entry.lba):
                data = sector[16:]
                h.update(data)
                size += len(data)
        else:
            data = sources[entry.path].read()
            h.update(data)
            size = len(data)
        result[entry.path] = dict(size=size, sha1=h.hexdigest())
    data = b''.join(sector[16:] for i, sector in enumerate(writer._license_sectors(license)) if i < 12)
    result['license_data.dat'] = dict(size=len(data), sha1=hashlib.sha1(data).hexdigest())
    return result


def load_player_reader(release):
    """Use the emitted standalone reader/writer, not this checkout's copies."""
    def module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[name] = loaded
        spec.loader.exec_module(loaded)
        return loaded
    writer = module('isowriter', release / 'isowriter.py')
    reader = module('literal_proof_player', release / 'dwpatch.py')
    return reader, writer


def prove(args):
    release = args.release.resolve()
    manifest = json.loads((release / 'manifest.json').read_text())
    bases = json.loads(args.bases.read_text())
    references = json.loads(args.references.read_text())
    if set(bases) != set(manifest['bases']) or set(references) != set(bases):
        raise ValueError('every advertised base needs its own player disc and independent reference image')
    edits = json.loads(args.edits.read_text())
    before, after = functions(args.baseline_build), functions(args.build)
    symbol = edits['code']['symbol']
    if symbol not in before or symbol not in after:
        raise ValueError('proof function missing from a build')
    if before[symbol] == after[symbol] or not any(before[k]['address'] != after[k]['address'] for k in before.keys() & after.keys()):
        raise ValueError('changed build must edit an original function and move linked functions')
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        gate = literal_gate.check_release(release, manifest, bases, args.source_disc,
                                         {name: args.build for name in manifest['variants']})
    except literal_gate.GateFailure:
        if not args.expect_blocked:
            raise
        gate = json.loads((release / 'literal-gate.json').read_text())
        if gate['passed']:
            raise ValueError('expected a fresh publication failure')
    else:
        if args.expect_blocked:
            raise ValueError('publication unexpectedly passed the negative regression')
    player, writer = load_player_reader(release)
    variant = manifest['variants'][manifest['default']]
    payload = player.read_payload3(player.read_patch_file(str(release), variant))
    results = {}
    baseline = audit.iw.Image(str(args.baseline_image))
    try:
        for key, path in bases.items():
            ref = audit.iw.Image(references[key])
            try:
                if key == 'us':
                    program = after[symbol]['file']
                    destinations = {program}
                    plan = json.loads((args.build / 'derived/plan.json').read_text())
                    for item in plan.get('LANG_OVL', []):
                        _, original, target = item.split(':')
                        if original == program:
                            destinations.add('SCN/' + target)
                    if not any(ref.read(q) != baseline.read(q) for q in destinations if q in ref.files and q in baseline.files):
                        raise ValueError('edited program file and its language copies are identical to baseline')
                    changed = [q for q in ref.files if q in baseline.files and q.startswith('SCN/') and q.endswith('.SCN')
                               and ref.read(q) != baseline.read(q)]
                    if not changed:
                        raise ValueError('no changed story containers relative to baseline')
                if audit.digest(Path(references[key])) != variant['outputs'][key]['sha1']:
                    raise ValueError(f'{key}: reference differs from changed release target')
                expected = image_sums(ref)
                mapping = json.loads((release / manifest['bases'][key]['mapping']).read_text()) if manifest['bases'][key].get('mapping') else None
                work = args.output / key; work.mkdir()
                base = player.BaseDisc(key, path, mapping, tool_root=str(release / 'bundle'), work=str(work), source_discs=args.source_disc)
                try:
                    holes = {}
                    for hole in variant['holes']:
                        data = ref.read(hole['file'])
                        want = hole.get('sha1_by_base', {}).get(key, hole['sha1'])
                        if hashlib.sha1(data).hexdigest() != want:
                            raise ValueError(f'{key}: reference hole mismatch: {hole["file"]}')
                        holes[hole['id']] = data
                    real_write = writer.write
                    captured = {}

                    def checked_write(layout, files, out, license=None, **kw):
                        captured.update(emitted_sums(writer, layout, files, license))
                        if captured != expected:
                            raise ValueError(f'{key}: per-file reconstruction differs from independent changed build')
                        return real_write(layout, files, out, license=license, **kw)

                    sink = Sink()
                    with patch.object(writer, 'write', checked_write):
                        sha, _ = player.build_disc3(payload, base, holes, sink, progress=False)
                    if sha != variant['outputs'][key]['sha1'] or sink.size != variant['outputs'][key]['size']:
                        raise ValueError(f'{key}: changed whole-disc mismatch')
                    audit.write_json(args.output / f'{key}-sums.json', captured)
                    results[key] = dict(sha1=sha, size=sink.size, files=len(captured))
                    audit.write_json(args.output / 'results.json', dict(bases=results, gate=gate,
                        edits=edits, baseline=before[symbol], changed=after[symbol],
                        runtime=dict(python=sys.version, reader_sha1=audit.digest(release/'dwpatch.py'),
                                     writer_sha1=audit.digest(release/'isowriter.py'))))
                finally:
                    base.img.f.close()
                    for image in getattr(base, '_copy_images', {}).values():
                        image.f.close()
            finally:
                ref.f.close()
    finally:
        baseline.f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--decomp', type=Path, required=True)
    p.add_argument('--story', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    q = commands.add_parser('prove')
    for name in ('release', 'bases', 'references', 'edits', 'baseline-build', 'baseline-image', 'output'):
        q.add_argument('--' + name, type=Path, required=True)
    q.add_argument('--source-disc', action='append', default=[])
    q.add_argument('--expect-blocked', action='store_true',
                   help='negative gate regression: require a fresh refusal, then test byte identity; never clears publication')
    for command in (p, q):
        command.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else prove)(args)


if __name__ == '__main__':
    main()
