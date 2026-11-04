"""Rebuild the selected-language container from independently checked components.

Virtual components are absent from the ISO layout. Resources are derive holes;
program overlays keep the same binary-delta and regional table checks as other
languages. Container coordinates and checksum are regenerated after replay.
"""
from pathlib import Path
import struct


def metadata(plan):
    result = dict(plan)
    result['LANG_OVL'] = list(plan.get('LANG_OVL', [])) + [
        'zh-hans:' + spec for spec in plan.get('CHINESE_OVL', [])]
    result['authored'] = list(plan.get('authored', [])) + ['@zh/module']
    return result


def components(data, plan, build_dir):
    from tools import chinese_resources as zh
    zh.validate(data)
    _, _, _, module_size, font_size, _, patch_size, _ = zh.HEADER.unpack_from(data)
    pieces = {
        '@zh/module': data[zh.MODULE_OFFSET:zh.MODULE_OFFSET+module_size],
        '@zh/font': data[zh.FONT_OFFSET:zh.FONT_OFFSET+font_size],
        '@zh/names': data[zh.NAMES_OFFSET:zh.NAMES_OFFSET+zh.NAME_COUNT*zh.NAME_SIZE],
        '@zh/writes': data[zh.PATCH_OFFSET:zh.PATCH_OFFSET+patch_size]}
    overlays = {target for spec in plan['CHINESE_OVL'] for _, target in [spec.split(':')]}
    rows = []
    for row in plan['CHINESE_RESOURCES']:
        source = row['source']
        dest = 'SCN/' + Path(source).name if Path(source).name in overlays else '@zh/' + source
        current = (Path(build_dir) / source).read_bytes()
        if dest in pieces and pieces[dest] != current:
            raise ValueError('Chinese resource alias has different bytes')
        pieces[dest] = current
        rows.append(dict(name=row['name'], story=row['story'], signs=row['signs'], source=source, file=dest))
    descriptor = dict(format=1, module='@zh/module', font='@zh/font', names='@zh/names',
                      patch='@zh/writes', resources=rows)
    if rebuild(descriptor, pieces) != data:
        raise ValueError('Chinese component replay differs from the build')
    return descriptor, pieces


def rebuild(descriptor, files, tool_root=None):
    import sys
    if tool_root and str(tool_root) not in sys.path:
        sys.path.insert(0, str(tool_root))
    from tools import chinese_resources as zh
    if descriptor.get('format') != 1:
        raise ValueError('unsupported Chinese component recipe')
    rows = [{**r, 'data': files[r['file']]} for r in descriptor['resources']]
    return zh.build(files[descriptor['module']], files[descriptor['font']], files[descriptor['patch']],
                    rows, files[descriptor['names']])
