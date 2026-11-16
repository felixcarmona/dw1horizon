"""Final-provider hover, preserved acting and heap checks on reviewed imports."""
import json
import os
from pathlib import Path
import unittest

import animsheet
import mmd
import motionstorage
from motiontailspace import interpolate_pose
from tools.models import audit_field, edit, hover
from tools.models.battle_qa import Rig


@unittest.skipUnless(os.environ.get('HOVER_BUILD'), 'set HOVER_BUILD to a reviewed build')
class ImportedHover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ['HOVER_BUILD']).resolve()
        cls.out = Path('build/hover-qa').resolve()
        catalogue = cls.out / 'species'
        catalogue.mkdir(parents=True, exist_ok=True)
        for p in (cls.source / 'species').glob('*.json'):
            target = catalogue / p.name
            if not target.exists():
                target.symlink_to(p)
        cls.models = {}
        cls.proof = {}
        registry = edit.import_records()
        for sid in (215, 275, 402):
            record = json.loads(next((edit.ROOT / 'content/species').glob(f'{sid}-*.json')).read_text())
            _, sk, path = audit_field.load(cls.source, record)
            before = path.read_bytes()
            base = cls.source / 'imported-models'
            donors = {373: (base / '373.MMD').read_bytes()} if sid == 402 else None
            final, _, effective = edit.provider_output(sid, (base / f'{sid}.MMD').read_bytes(),
                                                        (base / f'{sid}.TIM').read_bytes(), donors)
            modelpath = cls.out / f'{sid}.MMD'
            modelpath.write_bytes(final)
            effective['model']['file'] = str(modelpath)
            target = next(catalogue.glob(f'{sid}-*.json'))
            target.unlink()
            target.write_text(json.dumps(effective))
            cls.models[sid] = (before, final, sk, registry[str(sid)]['field_hover'])

    def test_final_clearance_and_rendered_thirds(self):
        for sid, (_, data, sk, slots) in self.models.items():
            rig = Rig.from_mmd(data, sk, sid)
            mesh = hover.MeshHover(mmd.MMD.parse(data, len(sk)), sk)
            clips = {}
            for slot in slots:
                slot = int(slot)
                with self.subTest(species=sid, slot=slot):
                    floor, ceiling = (30, 50) if slot in (0, 1, 18) else (80, 140)
                    r = audit_field.hover_heights(rig, slot)
                    self.assertGreaterEqual(r['lowest_min'], floor)
                    self.assertLessEqual(r['lowest_peak'], ceiling)
                    self.assertGreater(r['lowest_peak'] - r['lowest_min'], 10)
                    self.assertFalse(r['high_hover'])
                    frames, _, _ = animsheet.slot_frames(mmd.MMD.parse(data, len(sk)), len(sk), slot)
                    heights = [-mesh.floor(interpolate_pose(a, b, alpha))
                               for a, b in zip(frames, frames[1:]) for alpha in (1365, 2730)]
                    self.assertGreaterEqual(min(heights), floor)
                    self.assertLessEqual(max(heights), ceiling)
                    clips[slot] = dict(lowest_min=r['lowest_min'], lowest_peak=r['lowest_peak'],
                                       rendered_min=min(heights), rendered_peak=max(heights))
            self.proof[sid] = clips
        (self.out / 'clearance.json').write_text(json.dumps(self.proof, indent=2) + '\n')

    def test_joint_motion_travel_timing_events_and_other_slots(self):
        for sid, (before, after, sk, slots) in self.models.items():
            old, new = [mmd.MMD.parse(d, len(sk)) for d in (before, after)]
            for slot, index in enumerate(old.anims.table):
                if index is None:
                    self.assertIsNone(new.anims.table[slot])
                    continue
                a, la, ea = animsheet.slot_frames(old, len(sk), slot)
                b, lb, eb = animsheet.slot_frames(new, len(sk), slot)
                self.assertEqual((len(a), la, ea), (len(b), lb, eb), (sid, slot))
                if str(slot) not in slots:
                    self.assertEqual(a, b, (sid, slot))
                    continue
                for fa, fb in zip(a, b):
                    for bone, (pa, pb) in enumerate(zip(fa, fb)):
                        for channel, (va, vb) in enumerate(zip(pa, pb)):
                            if (bone, channel) != (1, 7):
                                self.assertLessEqual(abs(va - vb), 1, (sid, slot, bone, channel))

    def test_storage_keeps_global_peak_and_buffers(self):
        reports = {}
        for sid, (before, after, sk, _) in self.models.items():
            report = motionstorage.require(after, len(sk))
            self.assertEqual(report['resident_limit'], 100352)
            self.assertLessEqual(report['resident_bytes'], 100256)
            reports[sid] = dict(before=motionstorage.require(before, len(sk))['resident_bytes'],
                                after=report['resident_bytes'])
        (self.out / 'storage.json').write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
