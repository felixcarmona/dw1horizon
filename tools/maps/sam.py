# SPDX-License-Identifier: MIT
"""Prompted SAM without torchvision's image/automatic-mask dependencies.

Load the pinned upstream modeling, builder and predictor modules, bypassing its
package initializer (which imports automatic_mask_generator and torchvision NMS).
Our resizing adapter implements the predictor's small transform interface with
Horizon's exact 8-bit bilinear resampler. No upstream source is modified.
"""

import importlib
import importlib.util
import sys
from types import ModuleType


class ResizeLongestSide:
    def __init__(self, target_length):
        self.target_length = target_length

    @staticmethod
    def get_preprocess_shape(height, width, target):
        scale = target / max(height, width)
        return int(height * scale + 0.5), int(width * scale + 0.5)

    def apply_image(self, image):
        import numpy as np
        from tools.image import Image

        height, width = self.get_preprocess_shape(*image.shape[:2], self.target_length)
        return np.array(Image.fromarray(image).resize((width, height), Image.BILINEAR))

    def apply_coords(self, coords, original_size):
        result = coords.astype(float).copy()
        height, width = self.get_preprocess_shape(*original_size, self.target_length)
        result[..., 0] *= width / original_size[1]
        result[..., 1] *= height / original_size[0]
        return result

    def apply_boxes(self, boxes, original_size):
        return self.apply_coords(boxes.reshape(-1, 2, 2), original_size).reshape(-1, 4)

    def apply_image_torch(self, image):
        from torch.nn.functional import interpolate

        size = self.get_preprocess_shape(*image.shape[-2:], self.target_length)
        return interpolate(image, size, mode="bilinear", align_corners=False, antialias=True)

    def apply_coords_torch(self, coords, original_size):
        result = coords.float().clone()
        height, width = self.get_preprocess_shape(*original_size, self.target_length)
        result[..., 0] *= width / original_size[1]
        result[..., 1] *= height / original_size[0]
        return result

    def apply_boxes_torch(self, boxes, original_size):
        return self.apply_coords_torch(boxes.reshape(-1, 2, 2), original_size).reshape(-1, 4)


def _load():
    if "segment_anything" not in sys.modules:
        spec = importlib.util.find_spec("segment_anything")
        if spec is None:
            raise ImportError("SAM is optional: run tools/maps/setup-sam.sh first")
        package = ModuleType("segment_anything")
        package.__path__ = list(spec.submodule_search_locations)
        package.__spec__ = spec
        sys.modules["segment_anything"] = package
        transforms = ModuleType("segment_anything.utils.transforms")
        transforms.ResizeLongestSide = ResizeLongestSide
        sys.modules[transforms.__name__] = transforms
    builder = importlib.import_module("segment_anything.build_sam")
    predictor = importlib.import_module("segment_anything.predictor")
    return builder.sam_model_registry, predictor.SamPredictor


def __getattr__(name):
    if name not in ("sam_model_registry", "SamPredictor"):
        raise AttributeError(name)
    registry, predictor = _load()
    globals().update(sam_model_registry=registry, SamPredictor=predictor)
    return globals()[name]
