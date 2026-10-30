"""Header address fields are generated; adjacent opaque data must not be cleared."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent/'patcher'))
import headermeta


def object_fixture():
    names = b'\0.shstrtab\0.header\0.rel.header\0'
    payload = bytes(32)
    rel = struct.pack('<4I',4,2,12,4)  # .word relocation; instruction relocation
    start = 52
    data_start = start + len(names)
    rel_start = data_start + len(payload)
    sections_start = rel_start + len(rel)
    header = struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01\x01'+bytes(9),1,8,1,0,0,
                         sections_start,0,52,0,0,40,4,1)
    sections = [bytes(40),struct.pack('<10I',names.index(b'.shstrtab'),3,0,0,start,len(names),0,0,1,0),
        struct.pack('<10I',names.index(b'.header'),1,0,0,data_start,len(payload),0,0,4,0),
        struct.pack('<10I',names.index(b'.rel.header'),9,0,0,rel_start,len(rel),0,2,4,8)]
    return header + names + payload + rel + b''.join(sections)


class HeaderMetadataTests(unittest.TestCase):
    def test_only_word_relocations_clear_nonzero_data(self):
        with tempfile.TemporaryDirectory()as td:
            path=Path(td)/'header.o';path.write_bytes(object_fixture())
            ranges=headermeta.word_relocations(str(path),'.header')
        self.assertEqual(ranges,((4,8),))
        self.assertTrue(headermeta.generated(bytes(4)+struct.pack('<I',0x80123456)+bytes(4),0,ranges))
        self.assertFalse(headermeta.generated(b'opaque',0,ranges))
        self.assertFalse(headermeta.generated(struct.pack('<I',0x80123456),12,ranges))

    def test_invalid_object_fails_instead_of_clearing_bytes(self):
        with tempfile.TemporaryDirectory()as td:
            path=Path(td)/'header.o';path.write_bytes(b'not an object')
            with self.assertRaises(ValueError):headermeta.word_relocations(str(path),'.header')


if __name__=='__main__':unittest.main()
