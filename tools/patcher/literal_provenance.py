#!/usr/bin/env python3
"""Developer-only provenance evidence; category b is conservative original-derived code/data, not authorship clearance."""
import argparse
import bisect
import collections
import functools
import hashlib
import io
import json
import pathlib
import re
import subprocess
import sys
import tarfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import isowriter as iw


def main():
    ap = argparse.ArgumentParser(description='Conservative linker/source provenance of searched DWP3 literals. See docs/patcher.md.')
    ap.add_argument('--evidence', type=pathlib.Path, required=True)
    ap.add_argument('--build', type=pathlib.Path, required=True)
    ap.add_argument('--image', type=pathlib.Path, required=True)
    ap.add_argument('--release', type=pathlib.Path, required=True)
    ap.add_argument('--refined-release', type=pathlib.Path)
    ap.add_argument('--decomp', type=pathlib.Path, required=True)
    ap.add_argument('--decomp-commit', default='83f99c5cf11447e40be173d0e6b0922dd0f7ef7f')
    args = ap.parse_args()
    root = args.evidence
    build = args.build
    import literal_audit as audit
    _, variant, payload = audit.package(args.release)
    if variant['patch_sha1'] != json.load(open(root / 'input.json'))['patch_sha1']:
        raise ValueError('evidence belongs to another release')
    runs = audit.literal_runs(payload)
    B = payload['blob']
    img = iw.Image(str(args.image))
    archive = subprocess.check_output(['git', '-C', str(args.decomp), 'archive', args.decomp_commit, 'src'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        base_text = '\n'.join((tar.extractfile(t).read().decode('utf8', 'replace') for t in tar if t.isfile() and t.name.endswith(('.c', '.h'))))
    ORIGINAL_NAMES = set(re.findall('\\b[A-Za-z_]\\w*\\b', base_text))
    plan = json.load(open(build / 'derived/plan.json'))
    paths = {q: ('en', q) for q in img.files if q.endswith('_REL.BIN') or q == 'SLUS_010.32'}
    for ent in plan['LANG_OVL']:
        lang, orig, target = ent.split(':')
        paths['SCN/' + target] = (lang, orig)

    def maps(lang):
        folder = build / ('exe-' + lang)
        folder = folder if folder.exists() else build / 'exe'
        text = (folder / 'SLUS_010.32.elf.map').read_text()
        out = collections.defaultdict(list)
        output = None
        base = 0
        for line in re.sub('( \\.[\\w.]+)\\n\\s+(0x)', '\\1 \\2', text).splitlines():
            m = re.match('^\\.(\\w+)\\s+0x([\\da-f]+)\\s+0x([\\da-f]+)', line)
            if m:
                section = m[1]
                base = int(m[2], 16)
                output = 'SLUS_010.32' if section in ('main', 'header') else section + '_REL.BIN' if section.isupper() else None
            lm = re.match('\\s+0x([\\da-f]+)\\s+0x([\\da-f]+)\\s+LONG\\b', line)
            if lm and output:
                off = int(lm[1], 16) - (0x80090000 if output == 'SLUS_010.32' else base)
                out[output].append((off, off + int(lm[2], 16), '.linker.LONG', 'linker', str(folder / output)))
            m = re.match(' (\\.[\\w.]+)\\s+0x([\\da-f]+)\\s+0x([\\da-f]+)\\s+(\\S+\\.o)\\s*$', line)
            if not m or not output:
                continue
            sect, addr, n, obj = (m[1], int(m[2], 16), int(m[3], 16), m[4])
            if not n or addr == 0:
                continue
            off = addr - (0x80090000 if output == 'SLUS_010.32' else base)
            if off < 0:
                continue
            file = folder / output
            if not file.exists():
                continue
            out[output].append((off, off + n, sect, obj, str(file)))
        return out
    M = {l: maps(l) for l in ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')}
    BANKS = {l: json.load(open(build / f'text-bank-{l}.json'))['text'] for l in M}

    @functools.lru_cache(None)
    def original(path):
        r = subprocess.run(['git', '-C', str(args.decomp), 'show', args.decomp_commit + ':' + path], capture_output=True)
        return r.stdout.decode('utf8', 'replace') if r.returncode == 0 else None

    artifacts = {}

    @functools.lru_cache(None)
    def built(path):
        data = pathlib.Path(path).read_bytes()
        artifacts[path] = hashlib.sha1(data).hexdigest()
        return data

    def classify(q, a, b):
        if q.startswith('SCN/LANG') and (build / 'lang' / pathlib.Path(q).name).read_bytes() == img.read(q):
            return [(a, b, 'a', 'tools/langpatch.py:write_patch; authored language-bank strings and generated DWLP records')]
        if q not in paths:
            return [(a, b, 'd', 'No verified linker/source provenance')]
        lang, orig = paths[q]
        secs = M[lang].get(orig, [])
        D = img.read(q)
        out = []
        p = a
        for lo, hi, sect, obj, path in sorted(secs):
            lo = max(a, lo, p)
            hi = min(b, hi)
            if hi <= lo:
                continue
            if lo > p:
                out.append((p, lo, 'd' if any(D[p:lo]) else 'a', 'Linker padding or unmapped data' if any(D[p:lo]) else 'Linker-generated zero alignment padding'))
            data = built(path)
            if sect == '.linker.LONG':
                cat = 'a'
                ev = 'Linker-generated startup address/size metadata'
            elif 'MOD_VERSION_TEXT' in sect:
                cat = 'a'
                ev = 'Authored release version label (patch 0257 / tools/version.py)'
            elif 'FILE_OFFSET_TABLE' in sect:
                cat = 'a'
                ev = 'Generated disc layout table, rewritten by tools/build-disc.py / tools/isowriter.py'
            elif D[lo:hi] != data[lo:hi]:
                cat = 'd'
                ev = 'Post-link bytes differ from mapped artifact: ' + sect
            else:
                source = obj.split('/gcc/')[-1][:-2]
                sym = sect.split('.', 2)[-1]
                old = original(source) if source.startswith('src/') else None
                if sect.startswith('.text'):
                    if source.startswith('asm/') or sym.split('.')[0] in ORIGINAL_NAMES or sect == '.text':
                        cat = 'b'
                        ev = 'Original-derived program code (may include our modifications): ' + source + ':' + sect
                    elif source.startswith('src/') and (old is None or not re.search('\\b' + re.escape(sym.split('.')[0]) + '\\b', old)):
                        cat = 'a'
                        ev = 'New patch function absent from pinned decomp source identifiers: ' + source + ':' + sect
                    else:
                        cat = 'd'
                        ev = 'Unresolved compiled code: ' + obj + ':' + sect
                elif source == 'asm/main/data/header.data.s':
                    import headermeta
                    object_path = args.decomp / obj
                    header = next((x for x in secs if x[2] == sect and x[3] == obj), None)
                    ranges = headermeta.word_relocations(str(object_path), sect) if object_path.exists() else ()
                    if header and object_path.exists() and headermeta.generated(D[lo:hi], lo - header[0], ranges):
                        cat = 'a'
                        ev = 'Linker-generated PS-X header addresses/sizes and zero format padding: ' + sect
                        artifacts[str(object_path)] = audit.digest(object_path)
                    else:
                        cat = 'd'
                        ev = 'Inherited header bytes outside verified linker relocations: ' + sect
                elif source == 'src/main/font.c' and sect.startswith('.rodata.JAPANESE_'):
                    cat = 'e'
                    ev = 'Licensed third-party Fusion Pixel font / generated encoding tables: tools/font/japanese.txt; tools/font/japanese-license/:' + sect
                elif source == 'src/main/font.c' and sect.startswith(('.rodata.LATIN_GLYPH_', '.rodata.LATIN_ROW_')):
                    cat = 'd'
                    ev = 'Known mixed original-game and authored font data, Huffman encoded: patch 0245 src/main/font_compact.h:' + sect
                elif any((k.split('.', 1)[-1] == sym or k.split('.', 1)[-1].startswith(sym + '.') for k in BANKS[lang])):
                    cat = 'a'
                    ev = 'Authored text-bank replacement compiled by gen_text.py: ' + source + ':' + sect
                elif source.startswith('src/') and sym.split('.')[0] not in ORIGINAL_NAMES and (old is None or re.match('[A-Za-z_]\\w*$', sym)) and (not sect.endswith(('.rodata', '.data'))):
                    cat = 'a'
                    ev = 'New patch data symbol absent from pinned decomp source identifiers: ' + source + ':' + sect
                elif source.startswith('src/') and '_bss_' not in source:
                    cat = 'b'
                    ev = 'Original-derived C program data (may include modified tables): ' + source + ':' + sect
                elif source.startswith('asm/main/data/psyq/'):
                    cat = 'b'
                    ev = 'Original PsyQ library data assembled from reconstruction: ' + source + ':' + sect
                else:
                    cat = 'd'
                    ev = 'Inherited data/residue needs source review: ' + source + ':' + sect
            out.append((lo, hi, cat, ev))
            p = max(p, hi)
        if p < b:
            out.append((p, b, 'd' if any(D[p:b]) else 'a', 'Linker padding or unmapped data' if any(D[p:b]) else 'Linker-generated zero alignment padding'))
        return out
    C = json.load(open(root / 'segments-all.json'))
    starts = [s[0] for s in C]
    tot = collections.Counter()
    evs = collections.Counter()
    rows = []
    for r in runs:
        a = r['blob_offset']
        end = a + r['length']
        p = a
        i = max(0, bisect.bisect_right(starts, a) - 1)
        seg = []
        while i < len(C) and C[i][0] < end:
            lo, hi, s, o = C[i]
            lo = max(lo, a)
            hi = min(hi, end)
            if hi > lo:
                seg.append((lo, hi, s, o + lo - C[i][0]))
            i += 1

        def remaining(lo, hi):
            for x, y, cat, ev in classify(r['file'], r['offset'] + lo - a, r['offset'] + hi - a):
                rows.append(dict(file=r['file'], offset=x, length=y - x, operation=r['operation'], blob_offset=a + x - r['offset'], category=cat, evidence=ev))
                tot[cat] += y - x
                evs[cat, ev] += y - x
        for lo, hi, s, o in seg:
            if p < lo:
                remaining(p, lo)
            rows.append(dict(file=r['file'], offset=r['offset'] + lo - a, length=hi - lo, operation=r['operation'], blob_offset=lo, category='c', source_row=s, source_offset=o, evidence='Exact disc-file match (16-byte seed, extended bytewise)'))
            tot['c'] += hi - lo
            p = hi
        if p < end:
            remaining(p, end)
    assert sum(tot.values()) == len(B), (tot, len(B))
    (root / 'provenance.json').write_text(json.dumps(rows, indent=2) + '\n')
    (root / 'provenance-totals.json').write_text(json.dumps(tot, indent=2) + '\n')
    audit.write_json(root / 'provenance-inputs.json', dict(decomp_commit=args.decomp_commit, build=str(build.resolve()), image_sha1=audit.digest(args.image), maps={str(path): audit.digest(path) for path in sorted(build.glob('exe*/SLUS_010.32.elf.map'))}, artifacts=artifacts, text_banks={str(path): audit.digest(path) for path in sorted(build.glob('text-bank-*.json'))}, plan_sha1=audit.digest(build/'derived/plan.json')))
    print(tot)
    for k, n in evs.most_common(40):
        print(n, *k)
    if args.refined_release:
        _, _, refined = audit.package(args.refined_release)
        if any((payload[k] != refined[k] for k in ('layout', 'sha1', 'table'))):
            raise ValueError('refined target description changed')
        by_file = collections.defaultdict(list)
        for row in rows:
            by_file[row['file']].append(row)
        after = []
        after_totals = collections.Counter()
        for run in audit.literal_runs(refined):
            records = by_file[run['file']]
            ss = [r['offset'] for r in records]
            i = max(0, bisect.bisect_right(ss, run['offset']) - 1)
            pos = run['offset']
            end = pos + run['length']
            while pos < end:
                old = records[i]
                lo = max(pos, old['offset'])
                hi = min(end, old['offset'] + old['length'])
                if lo != pos or hi <= lo:
                    raise ValueError('remaining literal is not in original provenance')
                new = dict(old, offset=lo, length=hi - lo, operation=run['operation'], blob_offset=run['blob_offset'] + lo - run['offset'], old_blob_offset=old['blob_offset'] + lo - old['offset'])
                if 'source_offset' in new:
                    new['source_offset'] += lo - old['offset']
                after.append(new)
                after_totals[new['category']] += hi - lo
                pos = hi
                i += 1
        assert sum(after_totals.values()) == len(refined['blob'])
        assert all((after_totals[k] == tot[k] for k in 'abde')), (tot, after_totals)
        audit.write_json(root / 'provenance-after.json', after)
        audit.write_json(root / 'provenance-after-totals.json', after_totals)
        print('AFTER', after_totals)


if __name__ == "__main__":
    main()
