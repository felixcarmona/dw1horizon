"""Equipment visibility and hit timing survive encoding and playback."""
import copy
import unittest

import mmd
import animsheet
from tools.models.field_animations.imported_equipment import repair, build
from tools.models.audit_animations import audit


def model(clips, table=None):
    result = mmd.MMD()
    result.tmd = mmd.TMD()
    result.anims = mmd.AnimSection()
    result.anims.anims = clips
    result.anims.table = table or list(range(len(clips)))
    return result


def clip():
    pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0] for _ in range(3)]
    poses = [copy.deepcopy(pose) for _ in range(20)]
    for tick, p in enumerate(poses):
        p[0][8] = tick * 2
        p[1][3] = tick * 3
    return mmd.encode_anim(poses, 3, repeats=False, tol=0)


class ImportedEquipment(unittest.TestCase):
    def test_donor_visibility_keeps_motion_events_and_aliases(self):
        donor = clip()
        donor.instrs.insert(-1, dict(op='sound', frame=5, bank=4, note=2))
        native = copy.deepcopy(donor)
        native.has_scale = True
        native.pose = [[4096, 4096, 4096] + p for p in native.pose]
        native.pose[1][:3] = [0, 0, 0]
        source = model([donor, native], [0, 0, 1])
        fixed = repair(source, [2])
        before, loop, events = animsheet.slot_frames(source, 3, 0)
        after, new_loop, new_events = animsheet.slot_frames(fixed, 3, 0)
        self.assertEqual((len(before), loop, events), (len(after), new_loop, new_events))
        for a, b in zip(before, after):
            self.assertEqual(a[0], b[0])
            self.assertEqual(a[1], b[1])
            self.assertEqual(a[2][3:], b[2][3:])
            self.assertEqual(b[2][:3], [0, 0, 0])
        self.assertEqual(fixed.anims.table[0], fixed.anims.table[1])
        self.assertEqual(fixed.anims.anims[fixed.anims.table[2]].build(), native.build())

    def test_hit_recoils_early_recovers_and_keeps_root_and_duration(self):
        hit = clip()
        hit.instrs = [dict(op='key', frame=1, bones=[dict(bone=0, div=19, vals={'tz': 38})]),
                      dict(op='key', frame=11, bones=[dict(bone=1, div=1, vals={'rx': 300})]),
                      dict(op='sound', frame=11, bank=1, note=2),
                      dict(op='key', frame=12, bones=[dict(bone=1, div=8, vals={'rx': 0})]),
                      dict(op='end')]
        source = model([hit], [0] * 42)
        fixed = repair(source, [], True)
        for slot in (40, 41):
            before, _, events = animsheet.slot_frames(source, 3, slot)
            after, _, new_events = animsheet.slot_frames(fixed, 3, slot)
            self.assertEqual(len(after), 20)
            self.assertEqual([p[0] for p in before], [p[0] for p in after])
            self.assertGreater(abs(after[2][1][3] - after[0][1][3]), 0)
            self.assertEqual(after[-1][1], after[0][1])
            self.assertEqual([(k, e['bank'], e['note']) for _, k, e in events],
                             [(k, e['bank'], e['note']) for _, k, e in new_events])
            self.assertEqual(new_events[0][0], 0)
        self.assertEqual(source.anims.anims[0].build(), hit.build())

    def test_audit_counts_meshes_hidden_by_an_ancestor(self):
        donor = clip()
        native = copy.deepcopy(donor)
        native.has_scale = True
        native.pose = [[4096, 4096, 4096] + p for p in native.pose]
        native.pose[0][:3] = [0, 0, 0]
        source = model([donor, native])
        result = audit(source.build(), [(-1, -1), (-1, 0), (0, 1)])
        helper = next(v for v in result['variable_visibility'] if v['bone'] == 1)
        self.assertEqual(helper['mesh_object'], -1)
        self.assertEqual(helper['mesh_bones'], [2])

    def test_unreviewed_source_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'reviewed imported source'):
            build(b'unreviewed', [])


if __name__ == '__main__':
    unittest.main()
