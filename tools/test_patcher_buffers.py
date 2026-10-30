"""Short records use fresh linker extents and complete input bytes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
import types
sys.path.insert(0,str(Path(__file__).resolve().parent/'patcher'))
import bufferdata
import codecopy
import dwpatch


class BufferCopyTests(unittest.TestCase):
    def fixture(self, source='OVERLAY'):
        obj = dict(offset=2, length=20, section='.data.BUFFER', source='src/test/test_bss_us.c')
        policy = dict(version=1, objects={'BUFFER': dict(file='OVERLAY', length=20, copy_length=20,
                                                        offsets={'us': 4, 'eu': 8})})
        usa = b'head' + bytes(range(20))
        eu = b'own head' + bytes(range(40, 60))
        target = b'CC' + usa[4:] + b'TT'
        return obj, policy, usa, eu, target

    def test_whole_player_buffer_discards_diff_and_preserves_other_fields(self):
        obj, policy, usa, eu, target = self.fixture()
        image = types.SimpleNamespace(read=lambda _: eu)
        regional, combined, added, copies, changes = bufferdata.player_buffers(
            [obj], target, 'eu', image, 'OVERLAY', eu, policy=policy)
        self.assertEqual(regional, b'CC' + eu[8:] + b'TT')
        self.assertEqual(copies, [[2, 20, 8]])
        self.assertEqual(added, [])
        self.assertEqual(changes[0]['offset'], 2)
        control, diff, extra = codecopy.make_delta(eu, target, native=False)
        control, diff, extra = codecopy.generate_linker_words(control, diff, extra, len(combined), [], copies)
        entry = dict(size=len(target), sha1=hashlib.sha1(regional).hexdigest(), bases={'eu': dict(
            source='OVERLAY', source_sha1=hashlib.sha1(eu).hexdigest(), control=control,
            diff=[0, len(diff)], extra=[len(diff), len(extra)])})
        self.assertEqual(dwpatch.apply_binary_delta(entry, 'eu', image.read, diff + extra), regional)

    def test_separate_overlay_is_pinned_and_usa_stays_identical(self):
        obj, policy, usa, eu, target = self.fixture()
        regional, combined, added, copies, changes = bufferdata.player_buffers(
            [obj], target, 'us', types.SimpleNamespace(read=lambda _: usa), 'MAIN', b'code', policy=policy)
        self.assertEqual(regional, target)
        self.assertEqual(changes, [])
        self.assertEqual(combined, b'code' + usa)
        self.assertEqual(copies, [[2, 20, 8]])
        self.assertEqual(added, [dict(file='OVERLAY', size=len(usa), sha1=hashlib.sha1(usa).hexdigest())])

    def test_stale_usa_layout_and_out_of_bounds_sources_fail(self):
        obj, policy, usa, eu, target = self.fixture()
        image = types.SimpleNamespace(read=lambda _: usa)
        with self.assertRaisesRegex(ValueError, 'USA buffer no longer matches'):
            bufferdata.player_buffers([obj], b'X'*len(target), 'us', image, 'OVERLAY', usa, policy=policy)
        obj['length'] += 4
        with self.assertRaisesRegex(ValueError, 'layout changed'):
            bufferdata.player_buffers([obj], target, 'us', image, 'OVERLAY', usa, policy=policy)
        obj['length'] -= 4
        policy['objects']['BUFFER']['offsets']['us'] += 1
        with self.assertRaisesRegex(ValueError, 'outside its file'):
            bufferdata.player_buffers([obj], target, 'us', image, 'OVERLAY', usa, policy=policy)

    def test_unknown_buffer_cannot_gain_an_invented_source_or_zero_extension(self):
        obj, policy, usa, eu, target = self.fixture()
        image = types.SimpleNamespace(read=lambda _: eu)
        unknown = dict(obj, section='.data.UNKNOWN')
        self.assertEqual(bufferdata.player_buffers([unknown], target, 'eu', image, 'OVERLAY', eu,
                                                  policy=policy)[3], [])
        policy['objects']['BUFFER']['copy_length'] = 16
        with self.assertRaisesRegex(ValueError, 'unreviewed.*zero extension'):
            bufferdata.player_buffers([obj], target, 'eu', image, 'OVERLAY', eu, policy=policy)

    def test_duplicate_objects_keep_distinct_coordinates_at_a_sector_join(self):
        record = bytes(range(1, 13))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'derived').mkdir(); (root/'exe').mkdir()
            (root/'derived/plan.json').write_text(json.dumps({'LANG_OVL': []}))
            (root/'exe/SLUS_010.32.elf.map').write_text(
                '.EAB 0x80060000 0x100\n'
                ' .data.ONE 0x80060004 0xc build/src/eab_bss_us.c.o\n'
                ' .data.TWO 0x80060010 0xc build/src/eab_bss_us.c.o\n')
            logical = bytearray(4096); logical[2043:2055] = record
            raw = bytearray(2352*2); raw[24:2072] = logical[:2048]; raw[2376:4424] = logical[2048:]
            (root/'us.bin').write_bytes(raw)
            runs = [dict(file='EAB_REL.BIN', offset=4, length=24)]
            spans, objects = bufferdata.supplemental(bytes(4)+record*2, {'EAB_REL.BIN': 0}, runs,
                {'us': []}, {'us': root/'us.bin'}, {}, root)
            self.assertEqual(spans['us'], [[4,16,'@userdata',2043], [16,28,'@userdata',2043]])
            self.assertTrue(all(obj['hits'] == [['us','@userdata',2043]] for obj in objects))

    def test_moved_whole_object_and_sector_join(self):
        record=bytes(range(1,13))
        with tempfile.TemporaryDirectory()as td:
            root=Path(td);(root/'derived').mkdir();(root/'exe').mkdir()
            (root/'derived/plan.json').write_text(json.dumps({'LANG_OVL':[]}))
            raw=bytearray(2352*2);raw[100:112]=record
            (root/'us.bin').write_bytes(raw);(root/'eu.bin').write_bytes(bytes(len(raw)))
            logical=bytearray(4096);logical[2043:2055]=record
            shared=bytearray(2352*2);shared[24:2072]=logical[:2048];shared[2376:4424]=logical[2048:]
            (root/'dw2.bin').write_bytes(shared)
            for offset in (4,12):
                (root/'exe/SLUS_010.32.elf.map').write_text(
                    '.EAB 0x80060000 0x100\n'
                    f' .data.RECORD\n 0x{0x80060000+offset:x} 0xc build/src/eab_bss_us.c.o\n'
                    f' .data.TOO_SMALL 0x{0x80060000+offset+12:x} 0x4 build/src/eab_bss_us.c.o\n')
                blob=bytes(offset)+record+bytes(4)
                runs=[dict(file='EAB_REL.BIN',offset=offset,length=12)]
                spans,objects=bufferdata.supplemental(blob,{'EAB_REL.BIN':0},runs,{'us':[],'eu':[]},
                    {'us':root/'us.bin','eu':root/'eu.bin'},{'dw2':root/'dw2.bin'},root)
                self.assertEqual(len(objects),1)
                self.assertEqual(objects[0]['offset'],offset)
                self.assertEqual(spans['us'][0],[offset,offset+12,'@raw',100])
                self.assertEqual(spans['eu'],[[offset,offset+12,'@disc:dw2:@userdata',2043]])
                # A partial prefix is never accepted as the complete object.
                (root/'eu.bin').write_bytes(b'prefix'+record[:8]+bytes(len(raw)-14))
                missing,_=bufferdata.supplemental(blob,{'EAB_REL.BIN':0},runs,{'us':[],'eu':[]},
                    {'us':root/'us.bin','eu':root/'eu.bin'},{},root)
                self.assertEqual(missing['eu'],[])

    def test_missing_build_metadata_does_not_invent_records(self):
        with tempfile.TemporaryDirectory()as td:
            self.assertEqual(bufferdata.objects(td,{'EAB_REL.BIN':0},[]),[])


if __name__=='__main__':unittest.main()
