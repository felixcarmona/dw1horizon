"""Offline mesh clearance fitting, shared by flight authoring and condition overlays."""
import mmd


class MeshHover:
    def __init__(self, model, skeleton):
        self.skeleton = skeleton
        self.verts = {b: [v[:3] for v in model.tmd.obj_verts(o)]
                      for b, (o, _) in enumerate(skeleton) if o >= 0}

    def floor(self, pose):
        """Lowest mesh Y relative to the world floor (Y grows downwards)."""
        matrices = {}

        def world(b):
            if b not in matrices:
                v = list(pose[b])
                if b == 0:
                    v[6:9] = [0, 0, 0]  # root travel belongs to the entity
                r = mmd.rot_matrix(*v[3:6])
                local = [[r[i][j] * v[j] / 4096 for j in range(3)] + [v[6 + i]]
                         for i in range(3)] + [[0, 0, 0, 1]]
                parent = self.skeleton[b][1]
                matrices[b] = mmd.mat_mul(world(parent), local) if parent >= 0 else local
            return matrices[b]

        return pose[0][7] + max(world(b)[1][3] + sum(world(b)[1][j] * v[j] for j in range(3))
                                for b in self.verts for v in self.verts[b])

    def settle(self, frames, low, high, body=1):
        """Compress actual clearance while keeping its phase and every joint rotation."""
        if self.skeleton[body][1] != 0:
            raise ValueError('hover carrier must be a child of the root')
        heights = [-self.floor(p) for p in frames]
        bottom, top = min(heights), max(heights)
        gain = min(1.0, (high - low) / max(1.0, top - bottom))
        for pose, height in zip(frames, heights):
            target = low + (height - bottom) * gain
            pose[body][7] = round(pose[body][7] + height - target)
