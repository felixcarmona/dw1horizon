"""Put the player's patched disc inside Horizon Play for Android (docs/player.md): one APK that starts the game with
nothing to choose. The disc never leaves the player's computer: the patcher writes this APK next to the disc it built.

    python3 tools/patcher/apk.py TEMPLATE.apk DISC.bin OUT.apk [--key KEY.json]

The template is Horizon Play's own APK. Its entries are copied as they are (META-INF signatures dropped), the disc is
added stored and page aligned as assets/horizon.bin (the app reads it in place), and the result is signed with APK
Signature Scheme v2 (Android 7+). The key is kept in KEY.json (made on first use) so that a later APK from the same
computer installs over the earlier one and keeps the saves. Standard library only, so it runs in the web patcher too.
"""
import argparse
import hashlib
import json
import os
import random
import struct
import sys
import time
import zipfile

DISC_ENTRY = 'assets/horizon.bin'
CHUNK = 1 << 20
SIG_RSA_PKCS1_SHA256 = 0x0103
V2_BLOCK_ID = 0x7109871A


# ---- RSA and a self-signed certificate, with no library ----

def _probable_prime(bits, rng):
    small = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]
    while True:
        n = rng.getrandbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if any(n % p == 0 for p in small):
            continue
        d, s = n - 1, 0
        while d % 2 == 0:
            d, s = d // 2, s + 1
        for _ in range(40):
            x = pow(rng.randrange(2, n - 1), d, n)
            if x in (1, n - 1):
                continue
            for _ in range(s - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                break
        else:
            return n


def _der(tag, body):
    n = len(body)
    if n < 0x80:
        size = bytes([n])
    else:
        b = n.to_bytes((n.bit_length() + 7) // 8, 'big')
        size = bytes([0x80 | len(b)]) + b
    return bytes([tag]) + size + body


def _int(v):
    b = v.to_bytes(v.bit_length() // 8 + 1, 'big')
    return _der(0x02, b)


def _seq(*parts):
    return _der(0x30, b''.join(parts))


def _oid(dotted):
    a = [int(x) for x in dotted.split('.')]
    out = bytes([a[0] * 40 + a[1]])
    for v in a[2:]:
        enc = [v & 0x7F]
        v >>= 7
        while v:
            enc.append(0x80 | (v & 0x7F))
            v >>= 7
        out += bytes(reversed(enc))
    return _der(0x06, out)


_RSA_ALG = _seq(_oid('1.2.840.113549.1.1.1'), b'\x05\x00')
_SHA256_RSA = _seq(_oid('1.2.840.113549.1.1.11'), b'\x05\x00')
_SHA256_PREFIX = bytes.fromhex('3031300d060960864801650304020105000420')


def _sign(key, message):
    n, d = key['n'], key['d']
    k = (n.bit_length() + 7) // 8
    t = _SHA256_PREFIX + hashlib.sha256(message).digest()
    em = b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
    return pow(int.from_bytes(em, 'big'), d, n).to_bytes(k, 'big')


def public_key_der(key):
    rsa = _seq(_int(key['n']), _int(key['e']))
    return _seq(_RSA_ALG, _der(0x03, b'\x00' + rsa))


def new_key(bits=2048):
    rng = random.SystemRandom()
    e = 65537
    while True:
        p, q = _probable_prime(bits // 2, rng), _probable_prime(bits // 2, rng)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e and (p * q).bit_length() == bits:
            break
    key = {'n': p * q, 'e': e, 'd': pow(e, -1, phi)}
    name = _seq(_der(0x31, _seq(_oid('2.5.4.3'), _der(0x0C, b'Digimon World Horizon'))))
    now = time.gmtime()
    start = time.strftime('%Y%m%d%H%M%SZ', now).encode()
    end = ('%04d' % (now.tm_year + 50) + time.strftime('%m%d%H%M%SZ', now)).encode()
    tbs = _seq(_der(0xA0, _int(2)), _int(rng.getrandbits(63) + 1), _SHA256_RSA, name,
               _seq(_der(0x18, start), _der(0x18, end)), name, public_key_der(key))
    key['cert'] = _seq(tbs, _SHA256_RSA, _der(0x03, b'\x00' + _sign(key, tbs)))
    return key


def load_key(path):
    """The key in `path`, made and saved there the first time."""
    if path and os.path.exists(path):
        with open(path) as f:
            j = json.load(f)
        return {'n': int(j['n'], 16), 'e': j['e'], 'd': int(j['d'], 16), 'cert': bytes.fromhex(j['cert'])}
    key = new_key()
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + '.new'
        with open(tmp, 'w') as f:
            json.dump({'n': '%x' % key['n'], 'e': key['e'], 'd': '%x' % key['d'], 'cert': key['cert'].hex()}, f)
        os.replace(tmp, path)
    return key


# ---- the zip: template entries copied raw, the disc added stored and aligned ----

def _copy(src, dst, n, progress=None):
    while n > 0:
        b = src.read(min(n, CHUNK))
        if not b:
            raise ValueError('short read')
        dst.write(b)
        n -= len(b)
        if progress:
            progress(len(b))


def _write_zip(template, disc, out, progress=None):
    """Writes the unsigned APK to `out` (a file open for w+b); returns the central directory's offset."""
    central = []
    with open(template, 'rb') as t, zipfile.ZipFile(template) as z:
        for info in z.infolist():
            if info.filename.startswith('META-INF/') or info.filename == DISC_ENTRY:
                continue
            t.seek(info.header_offset)
            head = t.read(30)
            nlen, xlen = struct.unpack('<HH', head[26:30])
            t.seek(info.header_offset + 30 + nlen + xlen)
            align = 4 if info.compress_type == zipfile.ZIP_STORED else 1
            if info.filename.endswith('.so') and info.compress_type == zipfile.ZIP_STORED:
                align = 16384
            central.append(_entry(out, info.filename.encode(), info.compress_type, info.CRC, info.compress_size,
                                  info.file_size, info.date_time, align,
                                  lambda o, info=info: _copy(t, o, info.compress_size)))
    size = os.path.getsize(disc)
    crc = 0
    with open(disc, 'rb') as d:
        while True:
            b = d.read(CHUNK)
            if not b:
                break
            crc = zipfile.crc32(b, crc)
            if progress:
                progress(len(b) // 2)
    with open(disc, 'rb') as d:
        central.append(_entry(out, DISC_ENTRY.encode(), zipfile.ZIP_STORED, crc, size, size, time.localtime()[:6],
                              4096, lambda o: _copy(d, o, size, progress and (lambda n: progress(n - n // 2)))))
    cd = out.tell()
    for c in central:
        out.write(c)
    out.write(struct.pack('<IHHHHIIH', 0x06054B50, 0, 0, len(central), len(central), out.tell() - cd, cd, 0))
    return cd


def _entry(out, name, method, crc, csize, usize, dt, align, write_data):
    if csize >= 0xFFFFFFFF or out.tell() >= 0xFFFFFFFF:
        raise ValueError('the disc is too large for an APK')
    offset = out.tell()
    dostime = (dt[3] << 11) | (dt[4] << 5) | (dt[5] // 2)
    dosdate = ((max(dt[0], 1980) - 1980) << 9) | (dt[1] << 5) | dt[2]
    pad = (-(offset + 30 + len(name))) % align
    out.write(struct.pack('<IHHHHHIIIHH', 0x04034B50, 20, 0, method, dostime, dosdate, crc, csize, usize,
                          len(name), pad) + name + b'\x00' * pad)
    write_data(out)
    return struct.pack('<IHHHHHHIIIHHHHHII', 0x02014B50, 20, 20, 0, method, dostime, dosdate, crc, csize, usize,
                       len(name), 0, 0, 0, 0, 0, offset) + name


# ---- APK Signature Scheme v2 ----

def _lp(b):
    return struct.pack('<I', len(b)) + b


def _digest(f, sections, progress=None):
    chunks = []
    for start, data_or_len in sections:
        if isinstance(data_or_len, bytes):
            view = [data_or_len[i:i + CHUNK] for i in range(0, len(data_or_len), CHUNK)]
            for b in view:
                chunks.append(hashlib.sha256(b'\xa5' + struct.pack('<I', len(b)) + b).digest())
            continue
        f.seek(start)
        left = data_or_len
        while left:
            b = f.read(min(left, CHUNK))
            chunks.append(hashlib.sha256(b'\xa5' + struct.pack('<I', len(b)) + b).digest())
            left -= len(b)
            if progress:
                progress(len(b))
    return hashlib.sha256(b'\x5a' + struct.pack('<I', len(chunks)) + b''.join(chunks)).digest()


def sign_v2(f, cd, key, progress=None):
    """Signs the unsigned APK open in `f` (central directory at `cd`), inserting the APK Signing Block before it."""
    f.seek(cd)
    rest = f.read()
    eocd = rest.rindex(b'PK\x05\x06')
    central, end = rest[:eocd], rest[eocd:]
    digest = _digest(f, [(0, cd), (None, central), (None, end)], progress)
    signed = (_lp(_lp(struct.pack('<I', SIG_RSA_PKCS1_SHA256) + _lp(digest)))
              + _lp(_lp(key['cert'])) + _lp(b''))
    signer = (_lp(signed) + _lp(_lp(struct.pack('<I', SIG_RSA_PKCS1_SHA256) + _lp(_sign(key, signed))))
              + _lp(public_key_der(key)))
    value = _lp(_lp(signer))
    pair = struct.pack('<QI', 4 + len(value), V2_BLOCK_ID) + value
    size = len(pair) + 8 + 16
    block = struct.pack('<Q', size) + pair + struct.pack('<Q', size) + b'APK Sig Block 42'
    end = end[:16] + struct.pack('<I', cd + len(block)) + end[20:]
    f.seek(cd)
    f.write(block + central + end)
    f.truncate()


def build(template, disc, out, key_path=None, progress=None):
    """The APK with `disc` inside, at `out`. `progress(n)` is called with byte counts (about 3x the disc in total)."""
    size = os.path.getsize(disc)
    if size == 0 or size % 2352:
        raise ValueError(f'{disc} is not a raw disc image (.bin, 2352-byte sectors)')
    key = load_key(key_path)
    tmp = out + '.part'
    try:
        with open(tmp, 'w+b') as f:
            cd = _write_zip(template, disc, f, progress)
            sign_v2(f, cd, key, progress)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('template')
    ap.add_argument('disc')
    ap.add_argument('out')
    ap.add_argument('--key', help='the signing key file (made if missing; default: a new key each time)')
    a = ap.parse_args(argv)
    build(a.template, a.disc, a.out, a.key)
    print(f'{a.out} ({os.path.getsize(a.out) // (1 << 20)} MB)')


if __name__ == '__main__':
    sys.exit(main())
