#!/usr/bin/env python3
"""Digimon World's technique effect chunks (ETCHI/EFEDAT.EFE): header, script disassembly and assembly.

A chunk is 0x5000 bytes: a 0x34-byte header, then the scripts and their variables, the
UV animations, the sub-effect table, a TMD and a TIM. Offsets in the header and in the
scripts count from the end of the header ("base"). Only the bytes up to the TMD's end
stay in the effect heap after loading; the TIM is uploaded to VRAM and then overwritten.

Scripts are 16-bit words run by a stack machine (src/btl/battle_effect.c,
BTL_runEFEScript). The low byte of the first word is the opcode; the high byte carries
the variable width (bits 8-11: 0x4 int32, 0x2 int16, else int8), the operator or the
comparison (bits 12-15), or, for opcode 14, the sub-opcode. A variable operand is a
pair (offset, where): where 0 = the running instance (EfeInstance: +0 frame, +4
position, +0x10 rotation, then free space), else the chunk base.

Usage (from the repository root):
  python3 tools/efescript.py extracted/ETCHI/EFEDAT.EFE 63          header and disassembly of chunk 63
"""
import argparse
import struct
import sys

CHUNK = 0x5000
HEADER = 0x34
FIELDS = ('startScript', 'initScript', 'uvAnims', 'uvAnimsEnd', 'subEffects', 'tmdStart', 'tmdEnd',
          'timStart', 'timEnd', 'dataEnd', 'unk28', 'numSubEffects', 'effectId')

# the sub-opcodes of opcode 14 (BTL_EFE_SUB_OPCODES); each takes its arguments from the data stack
SUB = {0: 'checkTechCompatibility', 1: 'initializeUVAnim', 2: 'initializeSubEffectInstructions', 3: 'drawTMD',
       4: 'renderCenteredSprite', 5: 'initializeEFETransform', 6: 'checkCollisionWithDefaultPower', 7: 'rotateVector',
       8: 'setTransformToTargetBone', 9: 'addAttackObjectToTarget', 10: 'getScatteredSpawnPosition',
       11: 'discardOperandPair', 12: 'interpolateVector', 13: 'steerTransformTowardPoint',
       14: 'copyTargetEntityPosition', 15: 'setModelObjectColor', 16: 'addParticleEmitter',
       17: 'selectNextTargetEntity', 18: 'createFlash', 19: 'addCloudEffect', 20: 'renderScreenSprite',
       21: 'projectPositionToScreen', 22: 'renderParticleFlashSprite', 23: 'getTargetDigimonSize',
       24: 'renderProjectedSprite', 25: 'calculatePolarOffset', 26: 'copyFromParentTransform',
       27: 'addSourceEntityParticleFX', 28: 'playSound', 29: 'setTransformToBoneOffset',
       30: 'renderScrollingBackground', 31: 'renderParallaxSprites', 32: 'setTransformToSourceBone',
       33: 'rotateTransformTowardPoint', 34: 'checkTargetCollision', 35: 'getUVAnimTimer',
       36: 'applyHomingMovement', 37: 'getSourceDigimonSize', 38: 'sine', 39: 'cosine', 40: 'interpolateValue',
       41: 'randomInRange', 42: 'printDebugValue', 43: 'vectorEulerAngles', 44: 'findHitEntity',
       45: 'normalizeRotationAngles', 46: 'setTargetToHitEntity', 47: 'vectorLength', 48: 'copyVector',
       49: 'addVectors', 50: 'subtractVectors', 51: 'multiplyVectors', 52: 'divideVectors', 53: 'maskVectors',
       54: 'shiftVectorsRight', 55: 'centerTransformOnEntities', 56: 'getTargetBoneTransform',
       57: 'rotateVectorByAngles', 58: 'normalizeRotationAngles2', 59: 'combineRotations', 60: 'renderLine',
       61: 'copyToParentTransform', 62: 'getSourceBoneTransform', 63: 'setupFixedCamera',
       64: 'restoreCameraView', 65: 'render2DTexturedQuad', 66: 'renderWireframeGrid', 67: 'discardOperand',
       68: 'renderWireframeBox', 69: 'setTransformToBoneMatrix', 70: 'render3DTexturedQuad',
       71: 'multiplyVectorByScalar', 72: 'divideVectorByScalar', 73: 'maskVectorByScalar',
       74: 'convertToViewSpace', 75: 'selectRandomTargetEntity', 76: 'getCameraRotation', 77: 'drawTMDYXZ',
       78: 'loadClutColors', 79: 'drawTMDScreenSpace', 80: 'addClutLoadPrim', 81: 'getViewportDistance',
       82: 'renderRadialWaves', 83: 'initializeRibbonPoints', 84: 'tickRibbonPoints', 85: 'renderRibbonStrip',
       86: 'renderRingTube', 87: 'renderScreenOverlay', 88: 'faceTargetEntity', 89: 'applyLineAttackHit',
       90: 'applyRadiusAttackHit', 91: 'applyBoxAttackHit', 92: 'renderScreenFade', 93: 'disableMapLayer',
       94: 'getViewportDistance2', 95: 'markFinished', 96: 'isTargetUnhit'}
OPERATORS = ('set', 'add', 'sub', 'mul', 'div', 'mod', 'shl', 'shr')
COMPARISONS = ('==', '!=', '<', '<=', '>', '>=')
# opcode: (mnemonic, size in bytes, ends the flow)
OPS = {0: ('ld', 6, False), 1: ('ldv', 6, False), 2: ('rand', 2, False), 3: ('ldx', 10, False),
       4: ('op', 6, False), 5: ('stop', 2, True), 6: ('stop', 2, True), 7: ('br', 10, False), 8: ('stop', 2, True),
       9: ('jmp', 4, True), 10: ('push', 6, False), 11: ('pushv', 6, False), 12: ('pusha', 6, False),
       13: ('call', 6, False), 14: ('sub', 2, False), 15: ('ret', 2, True), 16: ('pop', 6, False),
       17: ('spawn', 12, False)}


def header(chunk):
    return dict(zip(FIELDS, struct.unpack_from('<13i', chunk, 0)))


def width(word, shift=8):
    w = (word >> shift) & 0xF
    return 'i32' if w == 4 else 'i16' if w == 2 else 'i8'


def var(off, where):
    return f'{"inst" if where == 0 else "base"}+{off:#x}'


def decode(base, pc):
    """(text, size, ends, jump targets) of the instruction at base offset pc."""
    w = struct.unpack_from('<8h', base + b'\0' * 16, pc)
    word = w[0] & 0xFFFF
    op = word & 0xFF
    if op not in OPS:
        return f'.word {word:#06x}', 2, True, []
    name, size, ends = OPS[op]
    targets = []
    if op == 0:
        t = f'ld {w[1]}'
    elif op == 1:
        t = f'ldv.{width(word)} {var(w[1], w[2])}'
    elif op == 2:
        t = 'rand'
    elif op == 3:
        t = f'ldx.{width(word)} base+{w[1]:#x}[{width(word, 12)} {var(w[3], w[4])}]'
    elif op == 4:
        t = f'{OPERATORS[(word >> 12) & 7]}.{width(word)} {var(w[1], w[2])}, R'
    elif op == 7:
        t = f'if {var(w[1], w[2])}.{width(word)} {COMPARISONS[(word >> 12) % 6]} R goto {w[3]:#x}'
        targets = [w[3] & 0xFFFF]
    elif op == 9:
        t = f'jmp {w[1] & 0xFFFF:#x}'
        targets = [w[1] & 0xFFFF]
    elif op == 10:
        t = f'push {w[1]}'
    elif op == 11:
        t = f'pushv.{width(word)} {var(w[1], w[2])}'
    elif op == 12:
        t = f'pusha {var(w[1], w[2])}'
    elif op == 13:
        t = f'call {w[1] & 0xFFFF:#x}'
        targets = [w[1] & 0xFFFF]
    elif op == 14:
        s = word >> 8
        t = f'sub {SUB.get(s, s)}'
    elif op == 16:
        t = f'pop {var(w[1], w[2])}'
    elif op == 17:
        t = f'spawn n={w[1]} instances=base+{w[2]:#x} stride={w[4]:#x} (w3={w[3]})'
    else:
        t = name
    return t, size, ends, targets


def code_pointers(base, insts):
    """Script addresses pushed with pusha base+X just before sub initializeSubEffectInstructions."""
    out = []
    for pc in sorted(insts):
        t = insts[pc][0]
        if t == 'sub initializeSubEffectInstructions':
            prev = [p for p in sorted(insts) if p < pc][-2:]
            for p in prev:
                if insts[p][0].startswith('pusha base+'):
                    out.append(int(insts[p][0].split('+')[1], 16))
    return out


def disassemble(chunk):
    """{pc: (text, size)} of every instruction reachable from the start and init scripts and from the script
    addresses the scripts hand to their sub-effects."""
    h = header(chunk)
    base = chunk[HEADER:]
    todo = [h['startScript'], h['initScript']]
    insts = {}
    while todo:
        pc = todo.pop()
        while 0 <= pc < len(base) - 2 and pc not in insts:
            text, size, ends, targets = decode(base, pc)
            insts[pc] = (text, size)
            todo += targets
            if ends:
                break
            pc += size
        for p in code_pointers(base, insts):
            if p not in insts:
                todo.append(p)
    return insts


def listing(chunk):
    h = header(chunk)
    lines = [f'{k} {v:#x}' for k, v in h.items()]
    labels = {h['startScript']: 'start', h['initScript']: 'init'}
    insts = disassemble(chunk)
    prev_end = None
    for pc in sorted(insts):
        if prev_end is not None and pc != prev_end:
            lines.append('')
        if pc in labels:
            lines.append(f'{labels[pc]}:')
        text, size = insts[pc]
        lines.append(f'  {pc:#06x}  {text}')
        prev_end = pc + size
    return '\n'.join(lines)


# ----------------------------------------------------------------- assembly

class Asm:
    """A tiny assembler for new scripts: methods emit instructions, labels are resolved at the end."""

    def __init__(self, origin):
        self.origin = origin              # base offset of the first byte
        self.out = bytearray()
        self.labels = {}
        self.fixups = []                  # (byte position, label)

    def here(self):
        return self.origin + len(self.out)

    def label(self, name):
        self.labels[name] = self.here()

    def _w(self, *words):
        for x in words:
            self.out += struct.pack('<H', x & 0xFFFF)

    def _ref(self, label, word_index):
        self.fixups.append((len(self.out) + 2 * word_index, label))

    @staticmethod
    def _width(w):
        return {'i32': 0x400, 'i16': 0x200, 'i8': 0}[w]

    def ld(self, value):
        self._w(0, value, 0)

    def ldv(self, off, where, w='i32'):
        self._w(1 | self._width(w), off, where)

    def ldx(self, table, index_off, index_where, w='i16', iw='i32'):
        """R = table[index] (table at a base offset, index a variable)."""
        self._w(3 | self._width(w) | self._width(iw) << 4, table, 0, index_off, index_where)

    def op(self, operator, off, where, w='i32'):
        self._w(4 | self._width(w) | OPERATORS.index(operator) << 12, off, where)

    def br(self, cmp, off, where, label, w='i32'):
        """goto label if var <cmp> R."""
        self._ref(label, 3)
        self._w(7 | self._width(w) | COMPARISONS.index(cmp) << 12, off, where, 0, 0)

    def jmp(self, label):
        self._ref(label, 1)
        self._w(9, 0)

    def push(self, value):
        self._w(10, value, 0)

    def pushv(self, off, where, w='i32'):
        self._w(11 | self._width(w), off, where)

    def pusha(self, off, where):
        self._w(12, off, where)

    def pusha_label(self, label):
        self._ref(label, 1)
        self._w(12, 0, 1)

    def call(self, label):
        self._ref(label, 1)
        self._w(13, 0, 0)

    def sub(self, name):
        code = next(k for k, v in SUB.items() if v == name)
        self._w(14 | code << 8)

    def ret(self):
        self._w(15)

    def pop(self, off, where):
        self._w(16, off, where)

    def bytes(self):
        out = bytearray(self.out)
        for pos, label in self.fixups:
            struct.pack_into('<H', out, pos, self.labels[label] & 0xFFFF)
        return bytes(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('efedat')
    p.add_argument('chunk', type=int)
    a = p.parse_args(argv)
    data = open(a.efedat, 'rb').read()
    print(listing(data[a.chunk * CHUNK:(a.chunk + 1) * CHUNK]))


if __name__ == '__main__':
    sys.exit(main())
