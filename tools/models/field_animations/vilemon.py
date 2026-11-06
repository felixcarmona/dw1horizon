"""Ogremon's loose arm swing over Vilemon's existing slow-walk footwork."""
import copy
import hashlib
from pathlib import Path
import numeric as np
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.channels import replace_channels
from tools.models.field_animations.war_greymon import set_rotation

SOURCE = 'd42b5aa8fe73767db0160273da40eb328f2086ecf6fee1aea340809aa54ed133'
DONOR = 'CHDAT/MMD1/OGRE.MMD'
DONOR_SHA256 = 'bfa85dd81b8ea257d52722c7623e4548970e4365ed00bcd0da13e154c36da88f'

def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != 21:
        raise ValueError('Vilemon requires the reviewed paced 21-bone model')
    mmd.exe().add_type(295, skeleton)
    old = mmd.MMD.parse(data, 21)
    old.type = 295
    if hashlib.sha256(Path(mmd.EXTRACTED,DONOR).read_bytes()).hexdigest() != DONOR_SHA256:
        raise ValueError('Ogremon differs from the reviewed native reference')
    donor = mmd.MMD.load(str(Path(mmd.EXTRACTED) / DONOR), 34)
    frames, loop, _ = animsheet.slot_frames(old, 21, 2)
    native, _, _ = animsheet.slot_frames(donor, 18, 2)
    def world(model, pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096]*3 + [0]*6
        return np.array(mmd.bone_matrices(model, pose))
    reference = world(donor, native[0])
    samples = copy.deepcopy(frames)
    history = {}
    pairs = [(16, 5), (17, 6), (13, 8), (14, 9)]
    for tick, pose in enumerate(samples):
        # The retained feet take four complete strides in this 60-tick clip.
        phase = (tick % 15) * (len(native)-1) * 4096 // 15
        index, fraction = divmod(phase, 4096)
        target = world(donor, interpolate_pose(native[index], native[index+1], fraction))
        source = world(old, frames[tick])
        for bone, native_bone in pairs:
            delta = target[native_bone,:3,:3] @ reference[native_bone,:3,:3].T
            parent = world(old, pose)[skeleton[bone][1],:3,:3]
            set_rotation(pose, bone, parent.T @ delta @ source[bone,:3,:3], history)
    samples[-1] = copy.deepcopy(samples[0])
    channels = {(bone,c) for bone,_ in pairs for c in (3,4,5)}
    animation = replace_channels(old.anims.anims[old.anims.table[2]], samples, loop, 21, channels)
    result = copy.deepcopy(old)
    result.anims.table[2] = len(result.anims.anims)
    result.anims.anims.append(animation)
    encoded = result.build()
    actual = mmd.MMD.parse(encoded,21)
    assert changed_programs(old,actual) == [2]
    assert old.tmd.build() == actual.tmd.build()
    decoded, newloop, _ = animsheet.slot_frames(actual,21,2)
    assert len(decoded)==len(frames) and newloop==loop
    for before,after in zip(frames,decoded):
        for bone in range(21):
            for channel in range(9):
                if (bone,channel) not in channels:
                    assert before[bone][channel]==after[bone][channel],(bone,channel)
    storage = motionstorage.require(encoded,21)
    return encoded, dict(species=295,source_sha256=SOURCE,output_sha256=hashlib.sha256(encoded).hexdigest(),
        donor=DONOR,donor_sha256=hashlib.sha256(Path(mmd.EXTRACTED,DONOR).read_bytes()).hexdigest(),
        changed_slots=[2],changed_channels=sorted(channels),stride_ticks=15,
        feet_body_wings_grip_run_care_battle_exact=True,storage=storage)
