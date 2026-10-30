#!/usr/bin/env python3
"""The proof edits must follow current linker/source outputs, not frozen offsets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import changed_build_proof as proof


class ChangedBuildPreparationTests(unittest.TestCase):
    def test_discovers_an_original_function_and_story_line(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build = root / 'build/baseline'; (build / 'exe').mkdir(parents=True)
            decomp = root / 'build/changed-decomp'; (decomp / 'src/overlay').mkdir(parents=True)
            source = decomp / 'src/overlay/current.c'
            source.write_text('int originalExample(int value) {\n    return value + 1;\n}\n')
            story = root / 'build/changed-story'; story.mkdir()
            (story / 'new-story.py').write_text('from dw import *\nsay("A new story.")\n')
            (build / 'exe/SLUS_010.32.elf.map').write_text(
                ' .text.originalExample\n                0x80102340 0x20 /work/build/us/psx/gcc/src/overlay/current.c.o\n')
            args = types.SimpleNamespace(decomp=decomp, story=story, build=build, output=root / 'edits.json')
            with patch.object(proof, 'ROOT', root), \
                 patch.object(proof.subprocess, 'check_output', return_value='pin\n'), \
                 patch.object(proof.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, source.read_text())):
                proof.prepare(args)
            edits = json.loads(args.output.read_text())
            self.assertEqual(edits['code']['symbol'], 'originalExample')
            self.assertEqual(edits['code']['baseline']['address'], 0x80102340)
            self.assertNotEqual(edits['code']['before'], edits['code']['after'])
            self.assertNotEqual(edits['story']['before'], edits['story']['after'])
            self.assertIn('__asm__ volatile ("nop; nop;', source.read_text())
            self.assertIn('A fresh tale begins here.', (story / 'new-story.py').read_text())

    def test_overlay_function_tracks_its_actual_program_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'exe').mkdir()
            (root / 'exe/SLUS_010.32.elf.map').write_text(
                '.BTL 0x80064000 0x1234\n'
                ' .text.movedFunction 0x80065000 0x24 /work/build/us/psx/gcc/src/btl/current.c.o\n')
            self.assertEqual(proof.functions(root)['movedFunction']['file'], 'BTL_REL.BIN')

    def test_xa_output_hashes_regenerate_edc_without_ignoring_movie_data(self):
        writer = proof.audit.iw
        movie = bytearray(b'x' * (2 * writer.XA))
        movie[2] = movie[6] = 0x20  # Form 2: writer zeroes its EDC.
        movie[writer.XA + 2] = movie[writer.XA + 6] = 0  # Mixed Form 1.
        entries = [types.SimpleNamespace(kind='file', path='MOVIE', xa=True, lba=100,
                                        size=len(movie), nsec=2)]
        layout = types.SimpleNamespace(entries=entries)
        expected = writer.form2(100, movie[:writer.XA])[16:] + writer.form1(
            101, movie[writer.XA:writer.XA+8], movie[writer.XA+8:writer.XA+8+writer.DATA])[16:]
        with patch.object(writer, 'plan'):
            got = proof.emitted_sums(writer, layout, {'MOVIE': bytes(movie)}, bytes(12 * writer.XA))
            self.assertEqual(got['MOVIE'], dict(size=len(expected), sha1=hashlib.sha1(expected).hexdigest()))
            self.assertNotEqual(got['MOVIE']['sha1'], hashlib.sha1(movie).hexdigest())
            movie[20] ^= 1
            changed = proof.emitted_sums(writer, layout, {'MOVIE': bytes(movie)}, bytes(12 * writer.XA))
            self.assertNotEqual(got['MOVIE']['sha1'], changed['MOVIE']['sha1'])

    def test_cannot_edit_outside_private_build_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(proof, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'private scratch tree'):
                    proof.scratch(root / 'main-checkout')


if __name__ == '__main__':
    unittest.main()
