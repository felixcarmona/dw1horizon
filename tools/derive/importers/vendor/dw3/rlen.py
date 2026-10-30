"""RLEN: the game's run-length compression (format documented by markisha64/ddw3)."""
import struct


def unrlen(data, offset=0):
    """Decode an RLEN block starting at `offset` ("RLEN" magic, u32 output size)."""
    if data[offset:offset + 4] != b"RLEN":
        raise ValueError("not RLEN data")
    size = struct.unpack_from("<I", data, offset + 4)[0]
    out = bytearray()
    p = offset + 8
    while len(out) < size:
        op = data[p]
        p += 1
        if op < 0x80:
            out += data[p:p + op]
            p += op
        else:
            out += bytes([data[p]]) * (op - 0x80)
            p += 1
    return bytes(out)
