"""Presented-frame video expansion must preserve refresh timing and fixed holds."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'tools/dev/presented_frames.py'
FRAME_BYTES = 320 * 240 * 2


class PresentedFrames(unittest.TestCase):
    def render(self, fixed=None):
        with tempfile.TemporaryDirectory(prefix='frame capture ') as td:
            raw = Path(td) / 'game.raw'
            frames = [bytes([n]) * FRAME_BYTES for n in (1, 2, 3)]
            raw.write_bytes(b''.join(frames))
            Path(str(raw) + '.vbl').write_text('10 12 15')
            argv = [str(CAPTURE), 'mp4', str(raw), str(Path(td) / 'video.mp4')]
            if fixed is not None:
                argv.append(str(fixed))
            with patch.object(sys, 'argv', argv), patch('subprocess.run') as run:
                runpy.run_path(str(CAPTURE), run_name='__main__')
            call = run.call_args
            self.assertTrue(call.kwargs['check'])
            self.assertIn('60', call.args[0])
            self.assertIn('bgr555le', call.args[0])
            return Path(str(raw) + '.60').read_bytes(), frames

    def test_refresh_counts_expand_actual_presented_frames(self):
        video, frames = self.render()
        self.assertEqual(video, frames[0] * 2 + frames[1] * 3 + frames[2])

    def test_fixed_hold_overrides_refresh_deltas(self):
        video, frames = self.render(4)
        self.assertEqual(video, frames[0] * 4 + frames[1] * 4 + frames[2])


if __name__ == '__main__':
    unittest.main()
