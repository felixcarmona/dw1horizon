"""RSP stop events must not shift memory replies in the profiling tools."""
import unittest
from tools.dev import duckstation as ds
from tools.dev.fps.curlingdscheck import BatchGDB


def packet(value):
    raw = value.encode()
    return b'$'+raw+b'#%02x' % (sum(raw)&255)


class Socket:
    def __init__(self, replies):
        self.replies = replies
        self.sent = []

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, size):
        value, self.replies = self.replies, b''
        return value

    def setsockopt(self, *args):
        pass


def connection(cls, replies):
    value = cls.__new__(cls)
    value.buf = b''
    value.s = Socket(replies)
    return value


class Protocol(unittest.TestCase):
    def test_memory_reply_after_async_stop(self):
        g = connection(ds.GDB, packet('S05')+packet('01020304'))
        self.assertEqual(g.read(0x80010000, 4), bytes.fromhex('01020304'))
        self.assertEqual(g.s.sent.count(b'+'), 2)

    def test_stop_is_returned_to_continue(self):
        g = connection(ds.GDB, packet('S05'))
        self.assertEqual(g.cmd('c'), 'S05')
        self.assertEqual(g.s.sent.count(b'+'), 1)

    def test_batch_keeps_reply_order_across_async_stop(self):
        g = connection(BatchGDB, packet('0100')+packet('S05')+packet('0200'))
        self.assertEqual(g.batch(['m80010000,2', 'm80010002,2']), ['0100', '0200'])
        self.assertEqual(g.s.sent.count(b'+'), 3)

    def test_overlay_upload_stays_within_packet_limit(self):
        data = bytes(range(256)) * 300
        g = connection(ds.GDB, packet('OK') * 100)
        g.write(0x80052ae0, data)
        restored = bytearray()
        for request in g.s.sent:
            if not request.startswith(b'$M'):
                continue
            self.assertLess(len(request), 8192)
            header, payload = request[2:request.rindex(b'#')].split(b':', 1)
            address, size = (int(v, 16) for v in header.split(b','))
            self.assertEqual(address, 0x80052ae0 + len(restored))
            chunk = bytes.fromhex(payload.decode())
            self.assertEqual(len(chunk), size)
            restored.extend(chunk)
        self.assertEqual(restored, data)

    def test_disconnect_does_not_spin(self):
        g = connection(ds.GDB, b'')
        with self.assertRaises(ConnectionError):
            g.cmd('?')
