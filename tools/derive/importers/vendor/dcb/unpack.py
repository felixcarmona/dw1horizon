"""Unpack the packed records of the battle model files, in plain Python.

The game's routine (`unpack(src, heap)`, 0x8001bff8 in SLUS_013.28; 0x8001bfa4
in SLES_039.00, 0x8001c23c in SLPS_031.01) rewritten from its code: LZSS over
a 4 KB window, whose literals and match lengths are Huffman coded with a tree
sent in the stream and replaced every 4096 symbols. Nothing here needs the
executable; dcb/decompress.py keeps the unicorn runner of the original code
as a reference (`python -m dcb.decompress check`).

Bits (0x8001bca4 reads n, 0x8001bc38 one) come MSB first from each byte, one
byte after another; past the end of the input they read as 0.

    u32 size       two 16-bit reads, high half first: the unpacked size
    then symbols until `size` bytes are out:
        every 4096 symbols (and before the first) a new tree (0x8001bd60),
        in preorder: bit 1 = node (left subtree, then right subtree),
        bit 0 = leaf, 9-bit value. Nodes are numbered 0x110, 0x111, ...;
        from 0x21f on a node is not built and reads as -1 (only in bad data).
        A symbol: from the root, bit 1 = right, 0 = left, while the value
        is >= 0x110 (a node number).
        value < 0x100  literal byte (-1, from a tree overflow, is byte 0xff)
        value >= 0x100 match: length value - 0xfd (3..18 for 0x100..0x10f),
                       then a 12-bit window position (absolute, not a
                       distance): copy `length` bytes from it, one by one
                       (an overlapping copy repeats).
    Every byte out also goes into the window at the write position, which
    starts at 0xfee; the window starts zeroed.

Edge cases kept as the game (under unicorn) gives them:
  - A match may run past `size`; the game writes the extra bytes after its
    buffer. The result is `size` rounded up to 4 bytes (the allocation, as
    the reference runner returns it): bytes past `size` are what the last
    match wrote there, or 0.
  - The game clears only window[0:0xfee]; the last 18 bytes keep whatever an
    earlier unpack left. The reference runner starts from zeroed RAM, so they
    are 0 here too. It does not matter: none of the 1728 packed records of
    F.DRV reads them before writing them.
  - The node arrays are not cleared between trees: a leaf value >= 0x110
    (a 9-bit value can be up to 0x1ff) is taken for a node number and walked
    through whatever that node last held (0 at the start). Kept, for
    exactness; real data does not do it.

Speed: symbols are decoded with an 8-bit lookup table built per tree (the
value and the bits used, or the node reached after 8 bits), so the common
case costs one table read per symbol, not one per bit.
"""

NODE0 = 0x110          # first node number; values below it are leaves
NODES = 0x220          # size of the game's node arrays
NODE_END = 0x21f       # first node number not built
WINDOW = 0x1000
TABLE_BITS = 8


class _Bits:
    """MSB-first bit reader with peek/skip."""

    def __init__(self, data):
        self.data = bytes(data) + b"\0" * 8
        self.end = len(data)
        self.pos = 0                     # in bits

    def peek(self, n):
        p = self.pos
        i = p >> 3
        if i >= self.end:                # past the end: zeros
            return 0
        w = int.from_bytes(self.data[i:i + 4], "big")
        return (w >> (32 - (p & 7) - n)) & ((1 << n) - 1)

    def read(self, n):
        v = self.peek(n)
        self.pos += n
        return v


def _read_tree(bits, left, right, state):
    """0x8001bd60: one subtree in preorder; returns its value or node."""
    if not bits.read(1):
        return bits.read(9)
    node = state[0]
    state[0] = node + 1
    if node >= NODE_END:
        return -1
    left[node] = _read_tree(bits, left, right, state)
    right[node] = _read_tree(bits, left, right, state)
    return node


def _build_table(root, left, right):
    """For every 8-bit prefix: (value, bits used) when the walk from the root
    ends within 8 bits, else (node reached, -1)."""
    table = []
    for prefix in range(1 << TABLE_BITS):
        v, used = root, 0
        while v >= NODE0 and used < TABLE_BITS:
            bit = (prefix >> (TABLE_BITS - 1 - used)) & 1
            v = right[v] if bit else left[v]
            used += 1
        table.append((v, used) if v < NODE0 else (v, -1))
    return table


def unpack(data):
    """Unpack one record (bytes) as the game does; see the module docstring."""
    bits = _Bits(data)
    size = bits.read(16) << 16
    size |= bits.read(16)
    out = bytearray()
    window = bytearray(WINDOW)
    left = [0] * NODES
    right = [0] * NODES
    r = 0xfee
    count = WINDOW                      # symbols since the tree was read
    table = None
    while len(out) < size:
        if count == WINDOW:
            root = _read_tree(bits, left, right, [NODE0])
            table = _build_table(root, left, right)
            count = 0
        v, used = table[bits.peek(TABLE_BITS)]
        if used >= 0:
            bits.pos += used
        else:                           # longer code: on bit by bit
            bits.pos += TABLE_BITS
            while v >= NODE0:
                v = right[v] if bits.read(1) else left[v]
        count += 1
        if v < 0x100:
            b = v & 0xff
            out.append(b)
            window[r] = b
            r = (r + 1) & 0xfff
        else:
            pos = bits.read(12)
            for i in range(v - 0xfd):
                b = window[(pos + i) & 0xfff]
                out.append(b)
                window[r] = b
                r = (r + 1) & 0xfff
    alloc = (size + 3) & ~3
    out = out[:alloc]
    return bytes(out) + b"\0" * (alloc - len(out))
