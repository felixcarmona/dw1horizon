"""Characterize story copy policy before relocating it into DWS."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.dws import variants as V


class StoryVariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.disc = self.root / 'extracted'
        (self.disc / 'MAP/ZONE').mkdir(parents=True)
        self.out = self.root / 'copies'
        self.enterContext(patch.object(V, 'EXTRACTED', str(self.disc)))

    def file(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def test_last_override_sorted_copies_and_new_file_exclusion(self):
        self.file('extracted/MAP/ZONE/ALPHA.MAP', b'original map')
        self.file('extracted/MAP/ZONE/BRAVO.TFS', b'original textures')
        old = self.file('old', b'old override')
        final = self.file('final', b'final override')
        ext = V.pairs(['MAP/ZONE/BRAVO.TFS=' + old, 'MAP/ZONE/ALPHA.MAP=' + old,
                       'MAP/ZONE/ALPHA.MAP=' + final, 'MAP/NEW/CHARLIE.MAP=' + final])
        rows = V.plan(str(self.out), ext, {})
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [('MAP/ZONE/ALPHA.MAP', '_LPHA.MAP'), ('MAP/ZONE/BRAVO.TFS', '_RAVO.TFS')])
        self.assertEqual(rows[0][2], final)
        self.assertEqual((self.out / '_LPHA.MAP').read_bytes(), b'original map')
        self.assertEqual(V.plan_lines(str(self.out), rows)[0],
                         '--add\tMAP/ZONE/_LPHA.MAP=' + str(self.out / '_LPHA.MAP'))
        replacement = self.file('balanced', b'balanced base')
        self.assertEqual(V.finish(str(self.out), rows, {'MAP/ZONE/ALPHA.MAP': replacement}), 1)
        self.assertEqual((self.out / '_LPHA.MAP').read_bytes(), b'balanced base')
        self.assertEqual(V.finish(str(self.out), rows, {'MAP/ZONE/ALPHA.MAP': replacement}), 0)

    def test_equal_bytes_and_non_maps_have_no_copies(self):
        original = self.file('extracted/MAP/ZONE/ALPHA.MAP', b'same')
        other = self.file('other', b'same')
        self.assertEqual(V.plan(str(self.out), {'MAP/ZONE/ALPHA.MAP': other, 'DG.SCN': original}, {}), [])

    def test_collision_checks_all_disc_folders(self):
        self.file('extracted/MAP/ZONE/ALPHA.MAP', b'original')
        self.file('extracted/OTHER/_LPHA.MAP', b'occupied')
        different = self.file('different', b'changed')
        with self.assertRaisesRegex(SystemExit, 'taken'):
            V.plan(str(self.out), {'MAP/ZONE/ALPHA.MAP': different}, {})

    def test_two_copies_cannot_share_a_basename(self):
        for name in ['ALPHA.MAP', 'BLPHA.MAP']:
            self.file('extracted/MAP/ZONE/' + name, b'original')
        changed = self.file('changed', b'changed')
        with self.assertRaisesRegex(SystemExit, 'taken'):
            V.plan(str(self.out), {f'MAP/ZONE/{n}': changed for n in ['ALPHA.MAP', 'BLPHA.MAP']}, {})


if __name__ == '__main__':
    unittest.main()


class NewSlotsNeedNoCopy(unittest.TestCase):
    """A .MAP the extended story only appends placed Digimon to is read as it is by the original story (prune)."""

    def setUp(self):
        import glob
        from tools import dwmap
        self.dwmap = dwmap
        maps = sorted(glob.glob(str(Path(V.ROOT) / 'extracted/MAP/*/*.MAP')))
        if not maps:
            self.skipTest('no extracted disc')
        self.src = next(p for p in maps if 0 < len(dwmap.MapFile(open(p, 'rb').read()).digimon) < 6)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        p = Path(self.tmp.name) / name; p.write_bytes(data); return str(p)

    def test_appended_slot_only(self):
        base = open(self.src, 'rb').read()
        m = self.dwmap.MapFile(base)
        m.digimon.append(dict(m.digimon[0])); m.digimon_count += 1
        ext = self.write('X.MAP', m.build()); b = self.write('_X.MAP', base)
        self.assertTrue(V.only_new_slots(ext, b))
        m.digimon[0] = dict(m.digimon[0], posX=m.digimon[0]['posX'] + 10)      # a native slot moved: a copy is needed
        self.assertFalse(V.only_new_slots(self.write('Y.MAP', m.build()), b))
        self.assertFalse(V.only_new_slots(b, b))

    def test_original_story_never_spawns_past_its_map(self):
        """The ground prune stands on: no MAPHEAD setup and no script of the original story (story/base) puts a Digimon
        in a slot its screen's .MAP does not have, on any screen with a .MAP."""
        import glob, os, re
        from tools.dws.py import naming
        from tools.dws import backend as BE
        facts = naming.maphead_facts()
        spawn = re.compile(r'\bspawn\(([^,]+), slot=([^,)]+)|\bset_digimon\(([^,]+(?:\([^)]*\))?), ([^,]+), ')
        scripts = {}
        for d in glob.glob(str(Path(V.ROOT) / 'story/base/zones/*/s*')):
            m = re.match(r's(\d+)', os.path.basename(d))
            scripts.setdefault(int(m.group(1)), []).append(''.join(open(p).read() for p in glob.glob(d + '/*.py')))
        jump = re.compile(r'\bjump_to_(?:script|file)\((\d+)')
        reach = {sid: {sid} for sid in scripts}               # a script and every script it jumps into, on its screen
        for _ in range(4):
            for sid in reach:
                reach[sid] |= {int(j) for r in list(reach[sid]) for t in scripts.get(r, []) for j in jump.findall(t)}
        bad = []
        for screen, (sids, digs) in facts.items():
            if not BE.map_path(BE.MAP_FILES.get(screen)):
                continue
            n = BE.next_free_slot(screen)
            bad += [(screen, 'MAPHEAD', slot) for _, slot, _ in digs if slot >= n]
            for sid in {r for s in sids for r in reach.get(s, {s})}:
                for t in scripts.get(sid, []):
                    for m in spawn.finditer(t):
                        slot = int(m.group(2) or m.group(4))
                        if slot >= n:
                            bad.append((screen, sid, slot))
        self.assertEqual(bad, [])
