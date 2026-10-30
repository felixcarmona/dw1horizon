
from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.dev import emulator as emu
from tools.dev.snapshot import protobuf_complete, wait_complete


def varint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    return bytes(out + bytes([value]))


def snapshot_fixture():
    fields = {1: b'PCSX-Redux SaveState', 3: b'x' * 32768,
              4: b'cpu', 5: b'vram', 6: b'spu', 7: b'sio', 15: b'cdrom'}
    return b''.join(varint(field * 8 + 2) + varint(len(value)) + value
                    for field, value in fields.items())


class SaveCompletionTests(unittest.TestCase):
    def test_stable_but_truncated_file_is_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'partial.state'
            path.write_bytes(snapshot_fixture()[:4096])
            with self.assertRaises(TimeoutError):
                wait_complete(path, timeout=.04, interval=.005, stable_seconds=.01)

    def test_missing_components_and_wrong_header_rejected(self):
        with self.assertRaises(ValueError):
            protobuf_complete(b'\x0a\x13PCSX-Redux SaveState')
        with self.assertRaises(ValueError):
            protobuf_complete(snapshot_fixture().replace(b'PCSX-Redux', b'Badx-Redux'))

    def test_both_cli_save_paths_wait_for_async_tail(self):
        data = snapshot_fixture()
        for command in ('save', 'seq'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'complete.state'
                done = threading.Event()
                workers = []

                def fake_api(*args, **kwargs):
                    path.write_bytes(data[:4096])

                    def finish():
                        time.sleep(.03)
                        with path.open('ab') as stream:
                            stream.write(data[4096:])
                        done.set()

                    worker = threading.Thread(target=finish)
                    worker.start()
                    workers.append(worker)
                    return ('ok ' + str(path)).encode()

                argv = ['emu.py', 'save', str(path)] if command == 'save' else [
                    'emu.py', 'seq', 'save ' + str(path)]
                with patch.object(emu, 'api', fake_api), patch('sys.argv', argv), \
                        contextlib.redirect_stdout(io.StringIO()):
                    emu.main()
                self.assertTrue(done.is_set())
                self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),
                                 hashlib.sha256(data).digest())
                for worker in workers:
                    worker.join()


if __name__ == '__main__':
    unittest.main()
